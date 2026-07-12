"""Token bucket 限流器。每个上游独立桶，控制请求频率。

用法：
    limiter = RateLimiter({"eastmoney": 1.0, "ths": 3.0})
    with limiter.acquire("eastmoney"):
        requests.get(...)

eastmoney: 1次/s（防封IP）
ths: 3次/s
mootdx/tencent: 不限（不封IP）
"""

from __future__ import annotations

import random
import threading
import time
from contextlib import contextmanager


class _Bucket:
    """单个令牌桶。"""

    def __init__(self, rate: float, burst: int = 1):
        self.rate = rate  # 每秒产生的令牌数
        self.burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> float:
        """获取一个令牌，返回等待时间。"""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return 0.0
                wait = (1.0 - self._tokens) / self.rate
            if time.monotonic() + wait > deadline:
                raise TimeoutError(f"限流器等待超时 ({timeout}s)")
            time.sleep(wait)


class RateLimiter:
    """多桶限流器。"""

    def __init__(self, rates: dict[str, float] | None = None):
        """
        rates: {"eastmoney": 1.0, "ths": 3.0} — 每秒最大请求数
        """
        if rates is None:
            rates = {"eastmoney": 1.0, "ths": 3.0}
        self._buckets = {name: _Bucket(rate) for name, rate in rates.items()}

    @contextmanager
    def acquire(self, upstream: str):
        """上下文管理器，自动等待+防抖。"""
        bucket = self._buckets.get(upstream)
        if bucket is None:
            # 未注册的上游不限流（如 mootdx/tencent）
            yield
            return
        wait = bucket.acquire()
        # 防抖：加一点随机延迟
        if wait > 0 or True:
            time.sleep(random.uniform(0.05, 0.15))
        yield

    def wait(self, upstream: str) -> None:
        """手动等待一个令牌。"""
        bucket = self._buckets.get(upstream)
        if bucket:
            bucket.acquire()


# 全局实例，供所有模块共享
limiter = RateLimiter()
