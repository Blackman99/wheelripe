"""Upstream tracking links. No network: every GitHub answer comes from a fixture."""
import io
import json
import pathlib
import urllib.error
from urllib.parse import parse_qs, urlsplit

import pytest

from wheelripe import cli, index, mcp, report, tracking
from wheelripe.check import BLOCKED, run
from wheelripe.inputs import Dep
from wheelripe.tags import Python, make_platform
from wheelripe.tracking import Tracker, github_repo, pick, score

from .conftest import fake_fetch

SEARCH = json.loads((pathlib.Path(__file__).parent / "fixtures" / "github-search.json").read_text("utf-8"))
PLATS = [make_platform(k) for k in ("linux-x86_64", "macos-arm64", "windows-amd64")]
PY315, PY315T = Python.parse("3.15"), Python.parse("3.15t")


def item(number, title, state="open", pr=False, merged=None, reason=None, comments=0, repo="acme/slowpoke"):
    it = {"html_url": f"https://github.com/{repo}/{'pull' if pr else 'issues'}/{number}", "number": number,
          "title": title, "state": state, "state_reason": reason, "comments": comments}
    if pr:
        it["pull_request"] = {"merged_at": merged}
    return it


class FakeGitHub:
    """Records every request; answers from ``repos`` (``{"owner/name": [items]}``)."""

    def __init__(self, repos=None, status=200, headers=None, raise_exc=None):
        self.repos = repos or {}
        self.status = status
        self.headers = headers or {}
        self.raise_exc = raise_exc
        self.calls = []

    def __call__(self, url, headers, timeout):
        q = parse_qs(urlsplit(url).query)["q"][0]
        self.calls.append((q, dict(headers)))
        if self.raise_exc:
            raise self.raise_exc
        if self.status != 200:
            return self.status, self.headers, b'{"message": "API rate limit exceeded"}'
        repo = q.split()[0][len("repo:"):]
        return 200, {"x-ratelimit-remaining": "9"}, json.dumps({"items": self.repos.get(repo, [])}).encode()


SLOWPOKE = {"acme/slowpoke": [
    item(7, "Lazy imports on Python 3.15+"),
    item(9, "Please build Python 3.15 wheels | cp315", comments=4),
    item(3, "Support Python 3.15", pr=True, state="closed", merged=None),  # closed unmerged: ignored
]}


# -- relevance --------------------------------------------------------------------------------

def test_github_repo():
    assert github_repo("https://github.com/numpy/numpy") == "numpy/numpy"
    assert github_repo("https://gitlab.com/acme/x") is None
    assert github_repo("https://github.com/sponsors/someone") is None
    assert github_repo(None) is None


@pytest.mark.parametrize("title,py,ok", [
    ("Python 3.15 support including binary wheels", PY315, True),
    ("[Feature Request] Python 3.15 wheels (cp315)", PY315, True),
    ("Add 3.15 to CI", PY315, True),
    ("Support free-threaded python", PY315T, True),
    ("Support free-threaded python", PY315, False),        # a GIL build does not wait on this
    ("Add Free-Threaded Python Support in 3.14", PY315T, False),  # another Python
    ("MAINT: lazy imports on Python 3.15+ (PEP 810)", PY315, False),
    ("BUG: Python 3.15 crashes when importing random", PY315, False),
    ("TST: test_extending failures on free-threaded Windows wheel build", PY315T, False),
    ("[CI] bump test dependency optree 0.20.0 for Python 3.15 and 3.15t", PY315T, False),
    ("Release 3.15.2", PY315, False),
    ("Fix #315 in the parser", PY315, False),
    ("Python 3.150 is not a thing", PY315, False),
])
def test_score(title, py, ok):
    assert (score(title, py) > 0) is ok, (title, score(title, py))


def test_pick_real_github_answers():
    # recorded answers of the GitHub search API for the 3.15t query (tests/fixtures/github-search.json)
    ck = SEARCH["confluentinc/confluent-kafka-python"]["items"]
    best, others = pick(ck, PY315T)
    assert best["number"] == 2396 and best["state"] == "open" and best["kind"] == "issue"
    assert "3.15t" in best["title"] and others == 2
    assert pick(ck, PY315)[0]["number"] in (2299, 2373)  # a GIL target prefers the plain 3.15 issues
    torch, _ = pick(SEARCH["pytorch/pytorch"]["items"], PY315T)
    assert torch["number"] == 184352 and torch["title"] == "Python 3.15 support for PyTorch"


def test_pick_merged_only_when_fully_blocked():
    items = [item(5, "Build cp315 wheels with cibuildwheel 3.3", pr=True, state="closed",
                  merged="2026-10-20T00:00:00Z"),
             item(4, "CI: add free-threaded Windows wheels", pr=True, state="closed", merged="2024-01-01T00:00:00Z")]
    best, _ = pick(items, PY315T)
    assert best["number"] == 5 and best["state"] == "merged" and best["kind"] == "pr"  # #4 names no version
    assert pick(items, PY315T, open_only=True) == (None, 0)


def test_long_titles_are_shortened():
    best, _ = pick([item(1, "Python 3.15 wheels " + "please " * 30)], PY315)
    assert len(best["title"]) <= tracking.TITLE_MAX and best["title"].endswith("…")


# -- wiring into reports --------------------------------------------------------------------

def check(*deps, gh=None, py="3.15", **kw):
    gh = gh if gh is not None else FakeGitHub(SLOWPOKE)
    rep = run([Dep(*d) for d in deps], fake_fetch, Python.parse(py), PLATS, tracker=Tracker(opener=gh, **kw))
    return rep, gh


def test_blocked_package_gets_its_issue_everywhere():
    rep, gh = check(("slowpoke", "3.1.0"), ("oldpin", "1.0.0"), ("fastpkg", "1.0.0"))
    assert len(gh.calls) == 1 and gh.calls[0][0].startswith("repo:acme/slowpoke in:title 3.15 OR cp315")
    r = {x.name: x for x in rep.results}
    assert r["slowpoke"].status == BLOCKED
    assert r["slowpoke"].tracking == {"search": "https://github.com/acme/slowpoke/issues?q=3.15%20in%3Atitle",
                                      "url": "https://github.com/acme/slowpoke/issues/9", "number": 9,
                                      "kind": "issue", "state": "open",
                                      "title": "Please build Python 3.15 wheels | cp315"}
    assert r["oldpin"].tracking is None  # bumps are yours to do, nothing to wait for
    txt = report.text(rep, stream=io.StringIO())
    assert "tracking: open issue #9 · Please build Python 3.15 wheels | cp315" in txt
    assert "https://github.com/acme/slowpoke/issues/9" in txt and "upstream:" not in txt
    md = report.markdown(rep)
    assert "<br>tracking: open issue [#9](https://github.com/acme/slowpoke/issues/9) · Please build Python " \
           "3.15 wheels \\| cp315 |" in md
    gh_out = report.github(rep)
    assert "::error title=wheelripe BLOCKED slowpoke::" in gh_out
    assert "tracking: open issue https://github.com/acme/slowpoke/issues/9 · Please build" in gh_out
    assert json.loads(report.to_json(rep))["packages"][0]["tracking"]["number"] == 9
    assert not rep.warnings


def test_nothing_found_says_so_and_links_the_search():
    rep, _ = check(("slowpoke", "3.1.0"), gh=FakeGitHub({}))
    assert rep.results[0].tracking == {"search": "https://github.com/acme/slowpoke/issues?q=3.15%20in%3Atitle"}
    assert "upstream: https://github.com/acme/slowpoke · no open issue or PR about 3.15 found" in \
        report.text(rep, stream=io.StringIO())
    assert "no open [issue or PR about 3.15](https://github.com/acme/slowpoke/issues?q=3.15%20in%3Atitle)" in \
        report.markdown(rep)


def test_freethreaded_query_and_wording():
    rep, gh = check(("slowpoke", "3.1.0"), gh=FakeGitHub({}), py="3.15t")
    assert gh.calls[0][0] == "repo:acme/slowpoke in:title 3.15 OR cp315 OR free-threaded OR free-threading OR nogil"
    assert "no open issue or PR about 3.15t found" in report.text(rep, stream=io.StringIO())


def test_partly_fixed_package_only_links_open_items():
    gh = FakeGitHub({"acme/halfway": [item(2, "Python 3.15 wheels", pr=True, state="closed",
                                           merged="2026-10-01T00:00:00Z", repo="acme/halfway")]})
    rep, _ = check(("halfway", "1.0"), gh=gh)
    assert rep.results[0].status == BLOCKED and rep.results[0].tracking == {
        "search": "https://github.com/acme/halfway/issues?q=3.15%20in%3Atitle"}


def test_merged_fix_is_reported_as_unreleased():
    gh = FakeGitHub({"acme/slowpoke": [item(11, "Build Python 3.15 wheels", pr=True, state="closed",
                                            merged="2026-10-20T00:00:00Z")]})
    rep, _ = check(("slowpoke", "3.1.0"), gh=gh)
    assert "tracking: merged PR #11 · Build Python 3.15 wheels · fixed upstream, waiting for a release" in \
        report.text(rep, stream=io.StringIO())


def test_no_lookup_for_glibc_floor_or_non_github():
    rep, gh = check(("newglibc", "1.0"), ("gitlabbed", "1.0"))
    assert gh.calls == []
    r = {x.name: x for x in rep.results}
    assert r["newglibc"].status == BLOCKED and r["newglibc"].tracking is None
    assert "upstream: https://gitlab.com/acme/gitlabbed" in report.text(rep, stream=io.StringIO())


def test_one_search_per_repo():
    gh = FakeGitHub(SLOWPOKE)
    tr = Tracker(opener=gh)
    for _ in range(2):
        run([Dep("slowpoke", "3.1.0")], fake_fetch, PY315, PLATS, tracker=tr)
    assert len(gh.calls) == 1


# -- failures never change the verdict ------------------------------------------------------

def test_rate_limit_stops_lookups_and_warns_once():
    gh = FakeGitHub(status=403, headers={"x-ratelimit-remaining": "0"})
    tr = Tracker(opener=gh)
    rep = run([Dep("slowpoke", "3.1.0")], fake_fetch, PY315, PLATS, tracker=tr)
    assert rep.results[0].status == BLOCKED and rep.results[0].tracking is None
    assert tr("acme/other", PY315) is None and len(gh.calls) == 1  # no more requests after the limit
    (w,) = tr.warnings()
    assert w.startswith("upstream lookup: GitHub search rate limit reached (10 searches a minute without a token")
    assert "acme/other" in w and "verdicts are unaffected" in w
    assert "::warning title=wheelripe upstream::upstream lookup: GitHub search rate limit" in report.github(rep)


def test_offline_degrades_quietly(monkeypatch, capsys):
    gh = FakeGitHub(raise_exc=urllib.error.URLError("Name or service not known"))
    monkeypatch.delenv("WHEELRIPE_NO_TRACKING")
    monkeypatch.setattr(index, "PyPI", lambda index=None: fake_fetch)
    monkeypatch.setattr(cli, "Tracker", lambda: Tracker(opener=gh))
    assert cli.main(["slowpoke==3.1.0", "fastpkg==1.0.0"]) == 1  # same exit code as without the lookup
    out, err = capsys.readouterr()
    assert "BLOCKED  slowpoke 3.1.0" in out and "upstream: https://github.com/acme/slowpoke" in out
    assert "no open issue" not in out  # we did not look, so we do not claim there is none
    assert "warning: upstream lookup: could not reach api.github.com (Name or service not known)" in err
    assert cli.main(["fastpkg==1.0.0"]) == 0


def test_github_errors_and_renamed_repos():
    for status in (500, 422):
        tr = Tracker(opener=FakeGitHub(status=status))
        assert tr("acme/slowpoke", PY315) is None
        assert bool(tr.warnings()) is (status == 500)


def test_token_is_sent_only_to_github_and_dropped_when_rejected(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_secret")
    seen = []

    def opener(url, headers, timeout):
        seen.append((urlsplit(url).netloc, headers.get("Authorization")))
        if headers.get("Authorization"):
            return 401, {}, b'{"message": "Bad credentials"}'
        return 200, {}, json.dumps({"items": SLOWPOKE["acme/slowpoke"]}).encode()

    tr = Tracker(opener=opener)
    rep = run([Dep("slowpoke", "3.1.0")], fake_fetch, PY315, PLATS, tracker=tr)
    assert seen == [("api.github.com", "Bearer ghs_secret"), ("api.github.com", None)]
    assert rep.results[0].tracking["number"] == 9
    assert rep.warnings == ["GITHUB_TOKEN was rejected by api.github.com; searched without it"]
    assert "ghs_secret" not in report.to_json(rep) + report.markdown(rep) + report.github(rep)


def test_gh_token_fallback(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "gho_x")
    assert Tracker().token == "gho_x"
    monkeypatch.setenv("GITHUB_TOKEN", "")
    assert Tracker().token == "gho_x"


# -- opting out -----------------------------------------------------------------------------

def test_cli_no_tracking_flag_and_env(monkeypatch, capsys):
    gh = FakeGitHub(SLOWPOKE)
    monkeypatch.setattr(index, "PyPI", lambda index=None: fake_fetch)
    monkeypatch.setattr(cli, "Tracker", lambda: Tracker(opener=gh))
    monkeypatch.delenv("WHEELRIPE_NO_TRACKING")
    cli.main(["slowpoke==3.1.0", "--no-tracking"])
    assert gh.calls == []
    cli.main(["slowpoke==3.1.0", "-f", "json"])
    assert len(gh.calls) == 1
    capsys.readouterr()
    monkeypatch.setenv("WHEELRIPE_NO_TRACKING", "1")
    cli.main(["slowpoke==3.1.0", "-f", "json"])
    assert len(gh.calls) == 1
    assert "tracking" not in json.loads(capsys.readouterr().out)["packages"][0]


def test_mcp_tracking(monkeypatch):
    monkeypatch.delenv("WHEELRIPE_NO_TRACKING")
    gh = FakeGitHub(SLOWPOKE)
    tr = Tracker(opener=gh)
    on = mcp.call_tool("check_python_upgrade", {"requirements": ["slowpoke==3.1.0"]}, fake_fetch, tr)
    assert on["structuredContent"]["packages"][0]["tracking"]["url"] == "https://github.com/acme/slowpoke/issues/9"
    assert "tracking: open issue [#9]" in on["content"][0]["text"]
    off = mcp.call_tool("check_python_upgrade", {"requirements": ["slowpoke==3.1.0"], "tracking": False},
                        fake_fetch, Tracker(opener=FakeGitHub(raise_exc=AssertionError("called"))))
    assert "tracking" not in off["structuredContent"]["packages"][0]
    schema = mcp.TOOLS[0]["inputSchema"]["properties"]["tracking"]
    assert schema["type"] == "boolean" and schema["default"] is True
