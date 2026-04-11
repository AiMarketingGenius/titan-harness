-- P11 Fast Mode + Blaze Mode — fast_mode_events table
CREATE TABLE IF NOT EXISTS fast_mode_events (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id     text,
  instance_id    text,
  event_type     text CHECK (event_type IN ('session_start','toggle_off','toggle_on','exception_skip')),
  from_state     text,
  to_state       text,
  reason         text,
  task_type      text,
  ts             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fast_mode_events_session_idx ON fast_mode_events(session_id);
CREATE INDEX IF NOT EXISTS fast_mode_events_ts_idx ON fast_mode_events(ts DESC);
