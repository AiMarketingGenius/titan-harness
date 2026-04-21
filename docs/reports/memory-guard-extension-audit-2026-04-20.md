# Memory Guard Extension Audit — 2026-04-20

## Scope

Audit only. No rebuild attempted tonight.

## Located Artifacts

1. Canonical repo source candidate
   - `/opt/titan-harness/deploy/aimg-extension-fixes`
   - `manifest.json` version: `0.1.13`

2. Product-package ZIP
   - `/opt/amg-memory-product/dist/AI_MEMORY_GUARD_v0.1.7.zip`
   - packaged `manifest.json` version: `0.1.7`

3. Public-site downloadable ZIP
   - `/opt/aimemoryguard-site/ai-memory-guard-extension-ct0416-07.zip`
   - packaged `manifest.json` version: `0.1.0`

## Findings

### 1. The extension exists, but the artifact chain is split across three different version lines.

- Repo source tree is ahead at `0.1.13`
- Product dist ZIP is behind at `0.1.7`
- Public-site ZIP is far behind at `0.1.0`

This means there is no single obvious "current build" artifact on the VPS.

### 2. The public-site ZIP is stale relative to both the product ZIP and the repo source.

Compared with the repo source, the public-site ZIP is missing newer files and features including:

- `copilot.js`
- `einstein-demo-claims.json`
- `ui/cross-llm-inject.js`
- `ui/einstein-status.js`
- `ui/einstein-status.css`
- `ui/einstein-summary.js`
- `ui/exchange-detector.js`
- test harness files

This suggests the downloadable ZIP on the site is not aligned with the active development branch.

### 3. The packaged product ZIP is newer than the public ZIP, but still behind repo source.

`AI_MEMORY_GUARD_v0.1.7.zip` includes:

- Copilot support
- cross-LLM inject assets
- Einstein summary assets

But it still lags the repo source at `0.1.13`, which now contains additional UI/status files and newer service-worker/UI state.

### 4. Supporting docs are also version-skewed.

- `deploy/aimg-extension-fixes/README.md` still describes a partial `v0.1.2` ship
- `deploy/aimg-extension-fixes/test-harness/LIVE_SMOKE_CHECKLIST.md` expects extension `v0.1.6`
- repo manifest is already `v0.1.13`

Operationally, the extension source, package artifacts, and test docs are no longer describing the same build.

## Current State Assessment

- Source code exists and looks actively maintained
- A packaged build exists
- A stale public/download artifact also exists
- Test harness material exists for live smoke verification
- No single artifact tonight can be called the clean canonical release without ambiguity

## Recommended Next Move

1. Declare one source of truth for release builds:
   - likely `/opt/titan-harness/deploy/aimg-extension-fixes`
2. Generate a fresh ZIP from that source
3. Replace or remove the stale `v0.1.0` ZIP from `/opt/aimemoryguard-site`
4. Update README + smoke checklist so docs match the actual packaged version
5. Run the live smoke checklist on logged-in real sessions before any external/demo use

## Bottom Line

The extension is not missing; it is fragmented. The main problem tonight is version drift between source, packaged artifact, and public download surface, not absence of an MV3 build.
