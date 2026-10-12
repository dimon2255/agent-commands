"""Server-side sessions for the shop API.

The admin console can revoke every session of a user (revoke_all_for_user),
so the server must be able to find and delete sessions by user.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

SESSION_TTL_SECONDS = 30 * 60


@dataclass
class Session:
    session_id: str
    user_id: int
    roles: list[str]
    expires_at: float = field(default_factory=lambda: time.time() + SESSION_TTL_SECONDS)


# Process-local store: every replica keeps its own copy.
_SESSIONS: dict[str, Session] = {}


def create_session(user_id: int, roles: list[str]) -> Session:
    session = Session(secrets.token_urlsafe(32), user_id, roles)
    _SESSIONS[session.session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    session = _SESSIONS.get(session_id)
    if session is None or session.expires_at < time.time():
        _SESSIONS.pop(session_id, None)
        return None
    session.expires_at = time.time() + SESSION_TTL_SECONDS  # sliding expiry
    return session


def revoke_all_for_user(user_id: int) -> int:
    doomed = [sid for sid, s in _SESSIONS.items() if s.user_id == user_id]
    for sid in doomed:
        del _SESSIONS[sid]
    return len(doomed)
