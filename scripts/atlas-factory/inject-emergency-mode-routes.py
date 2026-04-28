"""DIR-2026-04-28-002a Step 3.3 — Inject emergency-mode routes.

Inject the 3 emergency-mode routes into /opt/amg-mcp-server/src/index.js
right before the existing /static/doc09 route. Idempotent: if routes already
present, exits 0 with no-op message. Backs up original.
"""
import datetime
import pathlib
import shutil
import sys

SRC = pathlib.Path('/opt/amg-mcp-server/src/index.js')
ROUTES = pathlib.Path('/tmp/emergency-mode-routes.js')


def main() -> int:
    if not SRC.exists():
        print(f'ABORT: {SRC} not found')
        return 2
    if not ROUTES.exists():
        print(f'ABORT: {ROUTES} not found — scp the routes file first')
        return 2

    original = SRC.read_text()
    if '/api/emergency/signal' in original:
        print('SKIP: emergency routes already injected')
        return 0

    backup = SRC.with_suffix(
        f'.js.bak.dir-002a-step3.3-{datetime.datetime.utcnow():%Y%m%dT%H%M%SZ}'
    )
    shutil.copy(SRC, backup)

    routes = ROUTES.read_text()

    # The routes file already imports createHmac + timingSafeEqual at the top.
    # If the existing index.js already has 'createHmac' (from judge-gate-routes
    # phase 1 inject), we strip the duplicate import. Otherwise, leave it.
    import_line = "import { createHmac, timingSafeEqual } from 'node:crypto';\n"
    if 'createHmac' in original and 'timingSafeEqual' in original:
        routes_clean = routes.replace(import_line, '')
    elif 'createHmac' in original:
        # add only timingSafeEqual to the existing import
        original = original.replace(
            "import { createHash } from 'node:crypto';",
            "import { createHash } from 'node:crypto';\nimport { createHmac, timingSafeEqual } from 'node:crypto';",
            1,
        )
        routes_clean = routes.replace(import_line, '')
    else:
        # fully missing — leave routes file with full import block at top.
        # Move import to the existing import region.
        routes_clean = routes.replace(import_line, '')
        original = original.replace(
            "import Fastify from 'fastify';",
            "import Fastify from 'fastify';\n" + import_line,
            1,
        )

    # Use rfind so we insert BEFORE the actual app.get('/static/doc09', ...)
    # route, not before a stray code-reference inside a prior docstring/comment
    # (the judge-gate-routes injection left an orphan 'app.get("/static/doc09",
    # ...)`.' line earlier in the file; matching that breaks parse).
    needle = 'app.get("/static/doc09"'
    i = original.rfind(needle)
    if i < 0:
        print('ABORT: insertion anchor /static/doc09 not found')
        return 2
    # Walk backwards to start of the line for clean insertion.
    line_start = original.rfind('\n', 0, i) + 1
    patched = original[:line_start] + routes_clean + '\n\n' + original[line_start:]
    SRC.write_text(patched)
    print(f'PATCHED OK + backup at {backup}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
