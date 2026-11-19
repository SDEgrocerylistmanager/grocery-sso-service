import threading
import time
from typing import Optional


class StateStore:
    """Keeps the login "state" and PKCE verifier between /login and /callback."""

    def __init__(self, ttl_seconds: int = 600):
        self._ttl = ttl_seconds
        self._items = {}  # state -> (code_verifier, expires_at)
        self._lock = threading.Lock()

    def save(self, state: str, code_verifier: str) -> None:
        with self._lock:
            self._purge()
            self._items[state] = (code_verifier, time.monotonic() + self._ttl)

    def pop(self, state: str) -> Optional[str]:
        # A state is single-use: it is removed as soon as it is read
        with self._lock:
            self._purge()
            item = self._items.pop(state, None)
        return item[0] if item else None

    def _purge(self) -> None:
        now = time.monotonic()
        for key in [k for k, (_, exp) in self._items.items() if exp < now]:
            del self._items[key]
