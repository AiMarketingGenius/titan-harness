"""Mobile Command v2 — pure-stdlib data models shared across modules.

Extracted from `lib/mobile_cmd_auth.py` so storage adapters
(`lib/mobile_cmd_stores.py`) can import the data shapes without pulling in
the WebAuthn / pyjwt / pywebpush dependency chain. Keeping these in their
own module also documents the cross-module data contract clearly.

Stable as of Step 6.3-b. Adding fields = forward-compatible (defaults).
Removing fields = breaking; bump the module version + migrate callers.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: uuid.UUID
    operator_id: uuid.UUID
    token_hash: bytes
    family_id: uuid.UUID
    issued_at: _dt.datetime
    expires_at: _dt.datetime
    used_at: _dt.datetime | None
    revoked_at: _dt.datetime | None
