"""Lop HTTP dung chung: retry, gioi han toc do theo domain, tu doan encoding."""
from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504, 521, 522, 524}


class RateLimiter:
    """Bao dam moi domain chi bi goi cach nhau it nhat `delay` giay."""

    def __init__(self):
        self._lock = threading.Lock()
        self._next = {}

    def wait(self, host: str, delay: float):
        if delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            due = max(now, self._next.get(host, 0.0))
            self._next[host] = due + delay
        gap = due - time.monotonic()
        if gap > 0:
            time.sleep(gap)


class Http:
    def __init__(self, delay=0.4, retries=4, timeout=25, proxy="", ua=DEFAULT_UA):
        self.delay = float(delay)
        self.retries = int(retries)
        self.timeout = int(timeout)
        self.limiter = RateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi,vi-VN;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    # ---------- lay du lieu ----------
    def get(self, url: str, *, referer: str = "", stream=False, timeout=None):
        host = urlparse(url).netloc
        headers = {"Referer": referer} if referer else None
        last = None
        for attempt in range(self.retries + 1):
            self.limiter.wait(host, self.delay)
            try:
                r = self.session.get(
                    url, headers=headers, timeout=timeout or self.timeout,
                    stream=stream, allow_redirects=True,
                )
                if r.status_code in RETRY_STATUS:
                    last = requests.HTTPError(f"HTTP {r.status_code} tai {url}")
                else:
                    r.raise_for_status()
                    return r
            except requests.RequestException as exc:
                last = exc
            if attempt < self.retries:
                time.sleep(min(8.0, 0.8 * (2 ** attempt)))
        raise last if last else RuntimeError("khong lay duoc " + url)

    def text(self, url: str, **kw) -> str:
        r = self.get(url, **kw)
        enc = (r.encoding or "").lower()
        if not enc or enc in ("iso-8859-1", "ascii"):
            r.encoding = r.apparent_encoding or "utf-8"
        return r.text

    def soup(self, url: str, **kw) -> BeautifulSoup:
        return BeautifulSoup(self.text(url, **kw), "lxml")

    def bytes(self, url: str, **kw) -> bytes:
        return self.get(url, **kw).content

    def alive(self, url: str, timeout=8) -> bool:
        """Kiem tra 1 domain con song khong (dung de do mirror)."""
        try:
            self.session.get(url, timeout=timeout, allow_redirects=True)
            return True
        except requests.RequestException:
            return False
