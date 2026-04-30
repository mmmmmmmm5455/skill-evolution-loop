"""
Token-bucket rate limiter for Skill Evolution Loop.
Prevents API abuse across concurrent evolution loops.
"""
import time
import json
import threading
from pathlib import Path

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "thresholds.json"
    with open(config_path) as f:
        return json.load(f)["rate_limit"]

class TokenBucket:
    def __init__(self, rate: int, per_seconds: int):
        self.rate = rate
        self.per_seconds = per_seconds
        self.tokens = rate
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * (self.rate / self.per_seconds)
        self.tokens = min(self.rate, self.tokens + new_tokens)
        self.last_refill = now

class RateLimiter:
    def __init__(self):
        cfg = load_config()
        self.websearch_minute = TokenBucket(cfg["websearch_per_minute"], 60)
        self.websearch_hour = TokenBucket(cfg["websearch_per_hour"], 3600)
        self.github_minute = TokenBucket(cfg["github_per_minute"], 60)
        self.backoff_cfg = {
            "initial_ms": cfg["backoff_initial_ms"],
            "max_ms": cfg["backoff_max_ms"],
            "multiplier": cfg["backoff_multiplier"]
        }

    def can_websearch(self) -> bool:
        return self.websearch_minute.consume() and self.websearch_hour.consume()

    def can_github(self) -> bool:
        return self.github_minute.consume()

    def backoff_ms(self, attempt: int) -> int:
        delay = self.backoff_cfg["initial_ms"] * (self.backoff_cfg["multiplier"] ** attempt)
        return min(delay, self.backoff_cfg["max_ms"])

_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
