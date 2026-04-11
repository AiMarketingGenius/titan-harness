-- P1 Baseline Metrics — schema migration
-- Phase P1 of PERFORMANCE_OPTIMIZATION_MEGA_PROMPT.md
-- Adapted from war-room spec: tool_log column adds dropped because the
-- actual LLM/phase telemetry lives in mp_runs + tasks + war_room_exchanges.
-- Baselines are computed from those sources and stored here.

CREATE TABLE IF NOT EXISTS baseline_snapshots (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_name   text NOT NULL,               -- 'P0', 'weekly_2026-04-14', etc.
  run_at          timestamptz NOT NULL DEFAULT now(),
  window_days     int NOT NULL,
  is_frozen       boolean NOT NULL DEFAULT false,
  policy_capacity jsonb,                       -- snapshot of POLICY_CAPACITY_* at run time
  metrics         jsonb NOT NULL,              -- aggregated metrics (see schema in README)
  source_counts   jsonb,                       -- row counts per source table for audit
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS baseline_snapshots_name_idx ON baseline_snapshots(snapshot_name);
CREATE INDEX IF NOT EXISTS baseline_snapshots_frozen_idx ON baseline_snapshots(is_frozen) WHERE is_frozen = true;

CREATE TABLE IF NOT EXISTS baseline_regressions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at    timestamptz NOT NULL DEFAULT now(),
  snapshot_id    uuid REFERENCES baseline_snapshots(id),
  metric_path    text NOT NULL,                -- e.g. "mp_runs.avg_duration_ms"
  baseline_value numeric,
  current_value  numeric,
  delta_pct      numeric,
  severity       text CHECK (severity IN ('info','warn','regression')),
  slack_posted   boolean DEFAULT false,
  notes          text
);

CREATE INDEX IF NOT EXISTS baseline_regressions_detected_idx ON baseline_regressions(detected_at DESC);

-- Enforce only ONE frozen P0 snapshot at a time
CREATE UNIQUE INDEX IF NOT EXISTS baseline_snapshots_p0_unique
  ON baseline_snapshots(snapshot_name) WHERE snapshot_name = 'P0';
