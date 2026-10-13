"""Minimal PyPI JSON API client (stdlib only)."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional

from . import __version__

DEFAULT_INDEX = "https://pypi.org/pypi"
UA = f"wheelripe/{__version__} (+https://github.com/Blackman99/wheelripe)"

Fetcher = Callable[[str], Optional[dict]]


class PyPI:
    """Fetch ``{index}/{name}/json``; results are memoised per run."""

    def __init__(self, index: Optional[str] = None, timeout: float = 30.0):
        self.index = (index or os.environ.get("WHEELRIPE_INDEX") or DEFAULT_INDEX).rstrip("/")
        self.timeout = timeout
        self._cache: Dict[str, Optional[dict]] = {}
        self._lock = threading.Lock()

    def project(self, name: str) -> Optional[dict]:
        with self._lock:
            if name in self._cache:
                return self._cache[name]
        data = self._get(f"{self.index}/{name}/json")
        with self._lock:
            self._cache[name] = data
        return data

    __call__ = project

    def _get(self, url: str) -> Optional[dict]:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        last: Optional[Exception] = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                last = e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
        raise RuntimeError(f"PyPI request failed for {url}: {last}")
