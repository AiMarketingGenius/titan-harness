# Titan KB — 05 Lumina Dependency (when Lumina review is mandatory, cannot be skipped)

## Rule zero

**Lumina is the gatekeeper on ALL visual + CRO + client-facing copy work.** Her review happens BEFORE the dual-validator (Gemini Flash + Grok Fast). Skipping Lumina is a P10 violation.

## Files that REQUIRE Lumina approval before commit

Any change to files under these paths is blocked by the Lumina-gate pre-commit hook unless a Lumina approval record exists at `/opt/amg-docs/lumina/approvals/{YYYY-MM-DD}_{artifact_hash}.yaml` with `overall_score >= 9.3`:

- `deploy/**/*.html`, `**/*.css`, `**/*.jsx`, `**/*.tsx`, `**/*.svg`, `**/*.png` under client-facing paths
- `portal/`, `site/`, `marketing/`, `revere-*`, `chamber-*`
- `plans/agents/kb/lumina/` (changes to Lumina's own KB — self-review logged)
- Any file containing `client_facing: true` in its frontmatter

## Files EXEMPT from Lumina gate (internal only)

- `lib/`, `bin/`, `scripts/`, `config/`, `sql/`, `infra/`
- `plans/` (except client-facing subtrees above)
- `.git/`, `.github/`, `CLAUDE.md`, `MEMORY.md`, `RADAR.md`, `MIRROR_STATUS.md`, `INVENTORY.md`
- `library_of_alexandria/`
- `*.md` files under `plans/doctrine/`, `plans/research/`, `plans/deployments/`, `plans/agents/` (these are internal docs; content never shown to clients directly)

## Lumina review process (mandatory sequence)

1. **Titan produces deliverable.** Artifact staged locally, brand-audit doc exists (per `02_brand_standards.md`), trade-secret scan clean.

2. **Titan invokes Lumina.** Format:
   ```
   agent_context_loader(agent_name='lumina', client_id='{client}', query='Review {artifact}. Scope: visual + CRO. Design-system comparison. Score 5 dimensions.')
   ```
   Pass the full artifact bundle (HTML + CSS + JS + any assets) + the brand-audit doc + the client context (who is this for, what's the conversion goal).

3. **Lumina returns WRITTEN critique** with specific fixes per dimension:
   - Authenticity (uses real client brand? or placeholder?)
   - Hierarchy (where does the eye land first? flows to intended CTA?)
   - Craft (typography pairing, spacing, color depth, micro-interactions)
   - Responsiveness (375px mobile → 2560px widescreen all polished?)
   - Accessibility (WCAG AA? ARIA? keyboard nav? contrast?)
   - Overall score on 0-10 scale

4. **Iterate until Lumina scores ≥ 9.3** with NO dimension below 8.5.

5. **Log Lumina approval** at `/opt/amg-docs/lumina/approvals/{YYYY-MM-DD}_{hash}.yaml`:
   ```yaml
   artifact_path: deploy/revere-demo/index.html
   artifact_sha256: <hash>
   lumina_score: 9.4
   lumina_subscores:
     authenticity: 9.5
     hierarchy: 9.5
     craft: 9.0
     responsiveness: 9.5
     accessibility: 9.5
   critique_summary: <1-paragraph>
   approved_at: 2026-04-17T04:00:00Z
   approved_by: lumina
   ```

6. **Run dual-validator** (Gemini Flash + Grok Fast) on the Lumina-approved artifact. Both ≥ 9.3. If either fails, iterate (may require another Lumina round if the failure is craft-related).

7. **Commit.** Pre-commit hook verifies the Lumina approval record exists for the artifact hash.

## Lumina calls that are NOT gated (internal drafts)

- Lumina's own KB development (while building her own agent KB, she's not gating herself)
- Internal-only HTML/CSS (e.g., operator dashboards at `operator.aimarketinggenius.io` behind basic auth) — Lumina review recommended but not enforcement-blocked
- Rapid-prototyping in `/tmp/` or uncommitted local branches — gate fires on commit, not local save

## When to escalate to premium Lumina (Gemini Pro or Claude direct)

Default Lumina runs via the agent_context_loader → claude.ai project. Premium escalation ONLY when:

- Lumina's first-round score is <8.0 on any dimension (design has fundamental issues, needs architecture-level review)
- Artifact is a board pitch / investor deck / press release (external-audience reputation-critical)
- Artifact is the first-ever deployment to a new vertical (chamber, restaurant, med spa, etc.) — template for all future clients in that vertical

Premium route: dispatch Lumina call through Gemini Pro with the same rubric, compare to baseline Lumina output, ship whichever is stricter.

## The 2026-04-17 failure that created this rule

Revere demo v3 shipped without Lumina review:
- Trade-secret leaks (Atlas / beast / HostHatch / 140-lane)
- Placeholder "RC" monogram + invented navy+gold palette
- 7 identical agent icons

Solon caught all three. Had Lumina been in the loop (her KB alone would have flagged #2 and #3 instantly; `01_trade_secrets.md` + Titan KB would have flagged #1), none of these would have shipped.

Going forward: Lumina is called FIRST on any visual / client-facing artifact. No shortcut. No "looks fine" pass.

## Lumina's own scope (what she owns internally)

Per `plans/doctrine/PROJECT_BACKED_BUSINESS_UNIT_TEMPLATE.md`, Lumina is:
- Layer 2 subscriber agent (client-facing conversion consultant)
- Internal design-system + CRO gatekeeper on every client-facing deliverable
- Owner of `/opt/amg-docs/lumina/design-system/` (tokens, components, references)
- Owner of `/opt/amg-docs/lumina/approvals/` (audit trail)

She is called TWICE per deliverable: once as a client-facing consultation, once as the internal gate. Same agent, two invocation contexts.

## Cost note

Per P10 2026-04-17 tier rule, Lumina runs on Gemini 2.5 Flash by default (~$0.003 per review call). Cache hit rate on her design-system KB >80% within 5-min windows. Reviewing 20 artifacts/day ≈ $0.06. Cheap. No reason to skip for cost.
