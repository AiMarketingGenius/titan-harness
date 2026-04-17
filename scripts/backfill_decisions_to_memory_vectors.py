#!/usr/bin/env python3
"""
Backfill op_decisions rows into op_memory_vectors.

Bug diagnosed 2026-04-17 (CT-0416-29): log_decision writes to op_decisions
with an embedding, but op_search_memory queries op_memory_vectors — a
different table decisions never get written to. Result: 1350 decisions
accumulated since April 3 but search_memory returns only 2 test rows from
that day.

This script:
  1. Pages through op_decisions with embeddings, upserts into op_memory_vectors
  2. For decisions with NULL embedding, re-embeds via Ollama + inserts
  3. Uses op_decisions.id as op_memory_vectors.id → idempotent rerun
  4. chunk_type = 'decision' so the rows are tagged correctly

Run on HostHatch (has SUPABASE_SERVICE_ROLE_KEY + Ollama on localhost).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

SB_URL = 'https://egoazyasyrhslluossli.supabase.co'
SB_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
EMBED_MODEL = os.environ.get('EMBED_MODEL', 'nomic-embed-text')

if not SB_KEY:
    sys.stderr.write('ERROR: SUPABASE_SERVICE_ROLE_KEY not set\n')
    sys.exit(2)

HEADERS_READ = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Accept': 'application/json',
}
HEADERS_WRITE = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=minimal',
}


def sb_get(path):
    req = urllib.request.Request(f'{SB_URL}/rest/v1/{path}', headers=HEADERS_READ)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_upsert(table, rows):
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f'{SB_URL}/rest/v1/{table}', data=body, headers=HEADERS_WRITE, method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        sys.stderr.write(f'HTTP {e.code}: {e.read().decode()[:500]}\n')
        return e.code


def ollama_embed(text):
    body = json.dumps({'model': EMBED_MODEL, 'prompt': text[:8000]}).encode()
    req = urllib.request.Request(
        f'{OLLAMA_URL}/api/embeddings',
        data=body, headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
        return data.get('embedding')


def summarize(text, max_chars=180):
    """First sentence / truncation summary."""
    t = (text or '').strip()
    if len(t) <= max_chars:
        return t
    # cut at first newline / period after max_chars*0.7
    head = t[:max_chars]
    for sep in ['\n', '. ']:
        idx = head.rfind(sep)
        if idx > max_chars // 2:
            return head[:idx].strip() + '…'
    return head.strip() + '…'


def build_chunk(row, embedding):
    content_parts = [row['decision_text']]
    if row.get('rationale'):
        content_parts.append(f"\n\nRationale: {row['rationale']}")
    if row.get('tags'):
        content_parts.append(f"\nTags: {', '.join(row['tags'])}")
    content = ''.join(content_parts)

    return {
        'id': row['id'],  # reuse op_decisions id → idempotent upsert
        'content': content,
        'summary': summarize(row['decision_text']),
        'embedding': f"[{','.join(str(x) for x in embedding)}]",
        'project_tag': row.get('project_source'),
        'project_id': row.get('project_source'),
        'chunk_type': 'decision',
        'operator_id': 'OPERATOR_AMG',
        'model_name': 'nomic-embed-text',
        'embedding_dim': len(embedding),
        'created_at': row['created_at'],
        'topic_tags': row.get('tags') or [],
        'status': 'active',
        'pinned': False,
        'muted': False,
    }


def page_decisions(has_embedding: bool, page_size=200):
    """Yield decisions in created_at asc order for idempotent paging."""
    filter_ = 'embedding=not.is.null' if has_embedding else 'embedding=is.null'
    offset = 0
    while True:
        rows = sb_get(
            f'op_decisions?select=id,decision_text,rationale,project_source,tags,created_at,embedding'
            f'&{filter_}&order=created_at.asc&limit={page_size}&offset={offset}'
        )
        if not rows:
            return
        for r in rows:
            yield r
        if len(rows) < page_size:
            return
        offset += page_size


def parse_embedding_string(s):
    """op_decisions.embedding comes back as a string like '[0.1,0.2,...]'."""
    if not s:
        return None
    if isinstance(s, list):
        return s
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        return [float(x) for x in s[1:-1].split(',') if x.strip()]
    return None


def main():
    print('== Phase 1: backfill rows WITH existing embedding ==')
    done = 0
    skipped = 0
    batch = []
    for row in page_decisions(has_embedding=True, page_size=200):
        emb = parse_embedding_string(row.get('embedding'))
        if not emb or len(emb) != 768:
            skipped += 1
            continue
        batch.append(build_chunk(row, emb))
        if len(batch) >= 100:
            status = sb_upsert('op_memory_vectors', batch)
            if status not in (200, 201, 204):
                sys.stderr.write(f'  batch upsert failed: {status}\n')
                sys.exit(3)
            done += len(batch)
            print(f'  upserted {done} rows')
            batch = []
    if batch:
        status = sb_upsert('op_memory_vectors', batch)
        if status not in (200, 201, 204):
            sys.stderr.write(f'  final batch upsert failed: {status}\n')
            sys.exit(3)
        done += len(batch)
        print(f'  upserted {done} rows (final)')
    print(f'  phase 1 done: {done} upserted, {skipped} skipped (bad embedding shape)')

    print('\n== Phase 2: re-embed + backfill rows WITH NULL embedding ==')
    phase2_done = 0
    phase2_fail = 0
    batch = []
    for row in page_decisions(has_embedding=False, page_size=100):
        text = (row['decision_text'] or '') + ' ' + (row.get('rationale') or '')
        try:
            emb = ollama_embed(text)
        except Exception as e:
            sys.stderr.write(f'  ollama failed for {row["id"][:8]}: {e}\n')
            phase2_fail += 1
            continue
        if not emb or len(emb) != 768:
            phase2_fail += 1
            continue
        batch.append(build_chunk(row, emb))
        if len(batch) >= 50:
            status = sb_upsert('op_memory_vectors', batch)
            if status not in (200, 201, 204):
                sys.stderr.write(f'  phase2 batch upsert failed: {status}\n')
                sys.exit(3)
            phase2_done += len(batch)
            print(f'  re-embedded + upserted {phase2_done} rows')
            batch = []
    if batch:
        status = sb_upsert('op_memory_vectors', batch)
        if status not in (200, 201, 204):
            sys.stderr.write(f'  phase2 final upsert failed: {status}\n')
            sys.exit(3)
        phase2_done += len(batch)
    print(f'  phase 2 done: {phase2_done} re-embedded+upserted, {phase2_fail} failed')

    print(f'\n== TOTAL: {done + phase2_done} decisions now searchable ==')


if __name__ == '__main__':
    main()
