"""Inject the 6 judge-gate routes into /opt/amg-mcp-server/src/index.js
right before the existing /static/doc09 route. Backs up original."""
import pathlib, shutil, datetime
src = pathlib.Path('/opt/amg-mcp-server/src/index.js')
backup = src.with_suffix(f'.js.bak.tier1-gate-phase1-{datetime.datetime.utcnow():%Y%m%dT%H%M%SZ}')
shutil.copy(src, backup)

original = src.read_text()
routes = pathlib.Path('/tmp/judge-gate-routes.js').read_text()

# Idempotency guard: if already injected, skip.
if '/api/judgments/submit' in original:
    print('SKIP: routes already injected')
    raise SystemExit(0)

# Move the createHash import into the existing import block at top of file.
# We inject the import at the top of the file (after the first import line).
import_line = "import { createHash } from 'node:crypto';\n"
# Strip the duplicate import from the routes block to avoid re-importing.
routes_clean = routes.replace(import_line, '')

# Add import near the top, after other imports, idempotently.
if "from 'node:crypto'" not in original and 'createHash' not in original:
    original = original.replace(
        "import Fastify from 'fastify';",
        "import Fastify from 'fastify';\n" + import_line,
        1,
    )

needle = 'app.get("/static/doc09"'
i = original.find(needle)
if i < 0:
    raise SystemExit('ABORT: insertion anchor /static/doc09 not found')
patched = original[:i] + routes_clean + '\n\n' + original[i:]
src.write_text(patched)
print('PATCHED OK + backup at', backup)
