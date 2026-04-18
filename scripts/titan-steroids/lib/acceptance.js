// lib/acceptance.js — evaluate a class's acceptance_criteria array against a
// probe result.
//
// Supported types (subset of DR spec §1.2 — expand as more probes land):
//   regex_match       — JSONPath value matches regex
//   json_path_exists  — JSONPath resolves to a non-null value
//   numeric_range     — JSONPath value is a number in [min, max]
//
// llm_judge is out of scope for MVP; returns pending.

'use strict';

function jsonPath(obj, path) {
  if (!path || path === '$' || path === '.') return obj;
  // Very small subset: dot notation + bracket indexing.
  // Supports: $.status, $.a.b.c, $.arr[0].x
  const parts = path.replace(/^\$\.?/, '').split(/\.|\[/);
  let cur = obj;
  for (let p of parts) {
    if (p === '') continue;
    if (p.endsWith(']')) p = p.slice(0, -1);
    if (cur == null) return undefined;
    if (/^\d+$/.test(p)) cur = cur[Number(p)];
    else cur = cur[p];
  }
  return cur;
}

function evalCriterion(result, c) {
  const v = jsonPath(result, c.path);
  switch (c.type) {
    case 'regex_match': {
      if (typeof v !== 'string') return { ok: false, reason: `path ${c.path} not string: ${typeof v}` };
      const re = new RegExp(c.value);
      return { ok: re.test(v), reason: re.test(v) ? 'match' : `${v} !~ ${c.value}` };
    }
    case 'json_path_exists':
      return { ok: v !== undefined && v !== null, reason: v === undefined ? `path ${c.path} missing` : 'present' };
    case 'numeric_range': {
      if (typeof v !== 'number') return { ok: false, reason: `path ${c.path} not number: ${typeof v}` };
      const [min, max] = c.value || [null, null];
      const okMin = min === null || v >= min;
      const okMax = max === null || v <= max;
      return { ok: okMin && okMax, reason: `${v} ${okMin && okMax ? 'in' : 'OUT of'} [${min}, ${max}]` };
    }
    case 'llm_judge':
      return { ok: false, reason: 'llm_judge not implemented in MVP', pending: true };
    default:
      return { ok: false, reason: `unknown criterion type: ${c.type}` };
  }
}

function evaluate(result, criteria) {
  const rows = (criteria || []).map((c) => ({ criterion: c, eval: evalCriterion(result, c) }));
  const failed = rows.filter((r) => r.criterion.strict !== false && !r.eval.ok && !r.eval.pending);
  return {
    passed: failed.length === 0,
    rows,
    failures: failed,
  };
}

module.exports = { evaluate, evalCriterion, jsonPath };
