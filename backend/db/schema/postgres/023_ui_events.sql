-- Client-side UI interaction events (button/link clicks, in-app navigation).
-- Complements audit_log_events: that table captures every HTTP request the
-- backend handles; this one captures interactions that never reach the backend,
-- so platform usage can be inspected and optimised. Values are masked client- and
-- server-side (identifiers reduced to :id, query strings to keys) — see
-- routers/ui_events.py.
CREATE TABLE IF NOT EXISTS ui_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    occurred_at TIMESTAMPTZ,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    user_email TEXT,
    user_role TEXT,
    event_type TEXT NOT NULL,
    category TEXT,
    label TEXT,
    target_id TEXT,
    path TEXT,
    to_path TEXT,
    href TEXT,
    component TEXT,
    session_id TEXT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    remote_ip TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_ui_events_created_at
    ON ui_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ui_events_user_email
    ON ui_events (user_email);

CREATE INDEX IF NOT EXISTS idx_ui_events_event_type
    ON ui_events (event_type);

CREATE INDEX IF NOT EXISTS idx_ui_events_session_id
    ON ui_events (session_id);
