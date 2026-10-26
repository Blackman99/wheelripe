"""Upstream tracking: find the issue or PR where a blocked package's project discusses wheels
for the target Python, so you know what to subscribe to instead of what to build.

Read-only and best effort. One GitHub issue search per upstream repository (derived from
the project's ``project_urls`` on PyPI), unauthenticated unless ``GITHUB_TOKEN`` or
``GH_TOKEN`` is set; the token is sent to api.github.com only and never printed. A lookup
that fails (offline, rate limit, renamed repo) leaves the verdict untouched: the result
simply has no tracking link and the run gets one warning. Statuses never depend on it.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlencode

from .pypi import UA
from .tags import Python

API = "https://api.github.com/search/issues"
TITLE_MAX = 72

# (status, headers, body); raises OSError / urllib.error.URLError when the network is down
Opener = Callable[[str, Dict[str, str], float], Tuple[int, Dict[str, str], bytes]]


def _urlopen(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read() or b""


def github_repo(url: Optional[str]) -> Optional[str]:
    """``https://github.com/numpy/numpy`` -> ``numpy/numpy``; None for GitLab, Codeberg, ..."""
    m = re.match(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", url or "")
    if not m or m.group(1).lower() in ("sponsors", "orgs", "apps", "topics"):
        return None
    return f"{m.group(1)}/{m.group(2)}"


# -- relevance -------------------------------------------------------------------------------

_WORDS = [  # (pattern, weight): what makes a title about *shipping* for the new Python
    (r"wheel", 6), (r"binar", 4), (r"publish|upload|pypi", 3), (r"\bbuild\b|cibuildwheel|manylinux|abi3", 3),
    (r"support|compat", 2), (r"\badd(s|ing)?\b|\benable", 2), (r"\bci\b|\btest", 1),
]
# bug reports and internals that merely mention the version are not what you wait on
_NOISE = (r"crash|segfault|access violation|deprecat|warning|lazy import|\bleak|\bflaky|\brace\b"
          r"|^\s*(tst|bug|doc|docs|maint|chore|refactor|perf|style)\b\s*[:(]")
_TAGGED = r"^\s*\[[^\]]+\]|\bbump\b|dependenc"  # "[dynamo] ...", "bump optree for 3.15": dev chores


def _version_re(target: Python) -> str:
    v = rf"{target.major}\.{target.minor}"
    return rf"(?<![\d.]){v}(?![\d])|\b(?:cp|py){target.nodot}t?\b"


def _focus_re(target: Python) -> str:
    """The version is the subject: "Python 3.15 support", "wheels for 3.15", "3.15 / 3.15t"."""
    v = rf"{target.major}\.{target.minor}t?"
    return (rf"(?<![\d.]){v}(?:\s*(?:and|/|,|&)\s*{v})?(?=\s*(?:$|[)\]:,.!?(]|support|wheels?|compat|"
            rf"builds?\b|binar|release|is\b|has\b|drops|free))")


def score(title: str, target: Python) -> int:
    """0 when the title is not about wheels/support for ``target``; higher is more relevant."""
    t = title.lower()
    mentions = re.search(_version_re(target), t)
    ft = re.search(r"free[- ]?thread|nogil|no-gil|\bcp3\d+t\b|\b3\.\d+t\b", t)
    if not mentions and not (target.freethreaded and ft):
        return 0
    if not mentions and re.search(r"(?<![\d.])3\.\d{1,2}(?!\d)|\bcp3\d{1,2}t?\b", t):
        return 0  # "free-threading support in 3.14": about another Python
    if re.search(_NOISE, t):
        return 0
    hits = sorted((w for p, w in _WORDS if re.search(p, t)), reverse=True)
    s = hits[0] + len(hits) - 1 if hits else 0  # the strongest word, plus one per extra signal
    if s < 2:
        return 0  # "lazy imports on Python 3.15+", "test fix for 3.15": not what you are waiting for
    if mentions:
        s += 3
        if re.search(_focus_re(target), t):
            s += 4
    if re.search(_TAGGED, t):
        s -= 3
    if target.freethreaded and ft:
        s += 3
    elif not target.freethreaded and ft and not re.search(r"wheel", t):
        s -= 2  # a GIL build does not wait on free-threading work
    return max(s, 0)


def _state(item: dict) -> Optional[str]:
    """open / merged / closed (completed); None for things that will not help you."""
    pr = item.get("pull_request")
    if item.get("state") == "open":
        return "open"
    if pr is not None:
        return "merged" if pr.get("merged_at") else None
    return "closed" if item.get("state_reason") in (None, "completed") else None


def pick(items: Sequence[dict], target: Python, open_only: bool = False) -> Tuple[Optional[dict], int]:
    """Best tracking item and how many other relevant *open* ones there are.

    A merged PR or closed issue only counts when it names the target version and
    ``open_only`` is off: then no release has the wheel yet, so the fix is unreleased.
    """
    ranked = []
    for it in items:
        st = _state(it)
        title = it.get("title") or ""
        sc = score(title, target)
        if not st or not sc:
            continue
        if st != "open" and (open_only or not re.search(_version_re(target), title.lower())):
            continue
        ranked.append(((0 if st == "open" else 1, -sc, -int(it.get("comments") or 0), int(it.get("number") or 0)),
                       it, st))
    if not ranked:
        return None, 0
    ranked.sort(key=lambda x: x[0])
    _, it, st = ranked[0]
    others = sum(1 for _, _, s2 in ranked[1:] if s2 == "open")
    title = re.sub(r"\s+", " ", it.get("title") or "").strip()
    out = {"url": it.get("html_url"), "number": it.get("number"),
           "kind": "pr" if it.get("pull_request") is not None else "issue", "state": st,
           "title": title if len(title) <= TITLE_MAX else title[:TITLE_MAX - 1].rstrip() + "…"}
    return out, others


def search_url(repo: str, target: Python) -> str:
    """The same search for a human, on github.com."""
    q = f"{target.major}.{target.minor} in:title"
    return f"https://github.com/{repo}/issues?q={quote(q)}"


def query(repo: str, target: Python) -> str:
    v = f"{target.major}.{target.minor}"
    terms = [v, f"cp{target.nodot}"]
    if target.freethreaded:
        terms += ["free-threaded", "free-threading", "nogil"]
    return f"repo:{repo} in:title " + " OR ".join(terms)


# -- lookups ---------------------------------------------------------------------------------


class Tracker:
    """``tracker(repo, target)`` -> tracking dict or None. Never raises."""

    def __init__(self, token: Optional[str] = None, opener: Optional[Opener] = None,
                 timeout: float = 10.0, env=None):
        env = os.environ if env is None else env
        self.token = token if token is not None else (env.get("GITHUB_TOKEN") or env.get("GH_TOKEN") or None)
        self.opener = opener or _urlopen
        self.timeout = timeout
        self._lock = threading.Lock()
        self._cache: Dict[Tuple[str, str, bool], Optional[dict]] = {}
        self.stopped: Optional[str] = None  # why lookups stopped (offline, rate limit)
        self.skipped: List[str] = []
        self.failed: List[str] = []
        self.notes: List[str] = []

    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": UA, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def __call__(self, repo: str, target: Python, open_only: bool = False) -> Optional[dict]:
        key = (repo.lower(), str(target), open_only)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            if self.stopped:
                self.skipped.append(repo)
                return None
        res = self._lookup(repo, target, open_only)
        with self._lock:
            self._cache[key] = res
        return res

    def _lookup(self, repo: str, target: Python, open_only: bool) -> Optional[dict]:
        url = f"{API}?{urlencode({'q': query(repo, target), 'per_page': '30'})}"
        for attempt in (1, 2):
            try:
                status, headers, body = self.opener(url, self._headers(), self.timeout)
            except (OSError, ValueError) as e:  # URLError, timeouts, DNS: assume offline for the rest
                with self._lock:
                    if not self.stopped:
                        self.stopped = f"could not reach api.github.com ({getattr(e, 'reason', e)})"
                    self.failed.append(repo)
                return None
            if status == 401 and self.token and attempt == 1:
                with self._lock:
                    self.notes.append("GITHUB_TOKEN was rejected by api.github.com; searched without it")
                    self.token = None
                continue
            break
        if status in (403, 429) and (headers.get("x-ratelimit-remaining") == "0" or status == 429
                                     or b"rate limit" in body.lower()):
            with self._lock:
                if not self.stopped:
                    self.stopped = "GitHub search rate limit reached" + (
                        "" if self.token else " (10 searches a minute without a token; set GITHUB_TOKEN for 30)")
                self.failed.append(repo)
            return None
        if status == 422:  # repo renamed, private or gone: nothing to link, not an error worth a warning
            return None
        if status != 200:
            with self._lock:
                self.failed.append(repo)
            return None
        try:
            items = json.loads(body.decode("utf-8")).get("items") or []
        except (ValueError, AttributeError):
            with self._lock:
                self.failed.append(repo)
            return None
        best, others = pick(items, target, open_only)
        out = {"search": search_url(repo, target)}
        if best:
            out.update(best)
            if others:
                out["others"] = others
        return out

    def warnings(self) -> List[str]:
        out = list(dict.fromkeys(self.notes))
        missed = list(dict.fromkeys(self.failed + self.skipped))
        if missed:
            names = ", ".join(missed[:4]) + (f" and {len(missed) - 4} more" if len(missed) > 4 else "")
            why = self.stopped or "GitHub search did not answer"
            out.append(f"upstream lookup: {why}; no tracking link for {names}. "
                       "The verdicts are unaffected (--no-tracking turns the lookup off).")
        return out


def annotate(results, target: Python, tracker: Callable, workers: int = 4) -> None:
    """Fill ``Result.tracking`` for blocked packages hosted on GitHub."""
    from .check import BLOCKED, EXCLUDED, READY  # local import: check imports nothing from here

    todo: Dict[Tuple[str, bool], list] = {}
    for r in results:
        if r.status not in (BLOCKED, EXCLUDED):
            continue
        hard = [p for p in r.platforms.values() if p.status in (BLOCKED, EXCLUDED)]
        if hard and all(p.note[:1].isdigit() for p in hard):
            continue  # wheels exist, just for a newer glibc/macOS: a flag fixes it, not upstream
        repo = github_repo(r.upstream)
        if repo:
            # wheels exist for some target (ready, or a newer release has them): an old merged
            # "add 3.15 wheels" PR is already released, so only an open item can explain the rest
            partial = any(p.status == READY or p.fix for p in r.platforms.values())
            job = todo.setdefault((repo.lower(), partial), [repo, partial, []])
            job[2].append(r)
    if not todo:
        return
    jobs = list(todo.values())
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(jobs)))) as ex:
        found = list(ex.map(lambda job: tracker(job[0], target, job[1]), jobs))
    for (repo, _, rs), t in zip(jobs, found):
        for r in rs:
            r.tracking = t
