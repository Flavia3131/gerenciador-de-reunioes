"""Limitador de taxa em memória (janela deslizante) — freia força bruta em login/cadastro."""
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self):
        self.hits = defaultdict(deque)

    def check(self, key, limit, window):
        """0 se permitido; senão, segundos até poder tentar de novo."""
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return int(window - (now - q[0])) + 1
        q.append(now)
        return 0
