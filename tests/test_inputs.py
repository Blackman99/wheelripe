import json
import textwrap

import pytest

from wheelripe.inputs import InputError, collect, parse_file


def write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body))
    return p


def test_requirements(tmp_path):
    write(tmp_path, "base.txt", "six==1.16.0\n")
    p = write(tmp_path, "requirements.txt", """\
        # comment
        -r base.txt
        --index-url https://example.invalid/simple
        numpy==1.26.4 \\
            --hash=sha256:abc
        pandas>=2  # trailing comment
        pywin32==306; sys_platform == "win32"
        -e ./local
        git+https://github.com/x/y.git
        """)
    deps = parse_file(p)
    by = {d.name: d for d in deps}
    assert by["six"].version == "1.16.0"
    assert by["numpy"].version == "1.26.4"
    assert by["pandas"].version is None and by["pandas"].specifier == ">=2"
    assert "win32" in by["pywin32"].marker
    assert len(deps) == 4


def test_uv_lock(tmp_path):
    p = write(tmp_path, "uv.lock", """\
        version = 1
        [[package]]
        name = "myapp"
        version = "0.1.0"
        source = { editable = "." }
        [[package]]
        name = "numpy"
        version = "2.1.0"
        source = { registry = "https://pypi.org/simple" }
        [[package]]
        name = "gitdep"
        version = "1.0"
        source = { git = "https://github.com/x/y" }
        """)
    deps = parse_file(p)
    assert [(d.name, d.version) for d in deps] == [("numpy", "2.1.0")]


def test_poetry_lock(tmp_path):
    p = write(tmp_path, "poetry.lock", """\
        [[package]]
        name = "orjson"
        version = "3.10.0"
        [[package]]
        name = "local"
        version = "0.0.1"
        [package.source]
        type = "directory"
        url = "../local"
        """)
    assert [(d.name, d.version) for d in parse_file(p)] == [("orjson", "3.10.0")]


def test_pylock(tmp_path):
    p = write(tmp_path, "pylock.toml", """\
        lock-version = "1.0"
        created-by = "uv"
        [[packages]]
        name = "attrs"
        version = "25.1.0"
        [[packages]]
        name = "colorama"
        version = "0.4.6"
        marker = "sys_platform == 'win32'"
        [[packages]]
        name = "mine"
        directory = { path = "." }
        """)
    deps = parse_file(p)
    assert [(d.name, d.version) for d in deps] == [("attrs", "25.1.0"), ("colorama", "0.4.6")]
    assert deps[1].marker


def test_pipfile_lock(tmp_path):
    p = tmp_path / "Pipfile.lock"
    p.write_text(json.dumps({"default": {"requests": {"version": "==2.32.0"}},
                             "develop": {"pytest": {"version": "==8.0.0", "markers": "python_version >= '3.8'"}}}))
    assert sorted((d.name, d.version) for d in parse_file(p)) == [("pytest", "8.0.0"), ("requests", "2.32.0")]


def test_pyproject(tmp_path):
    p = write(tmp_path, "pyproject.toml", """\
        [project]
        name = "x"
        dependencies = ["numpy>=2", "attrs==25.1.0"]
        [project.optional-dependencies]
        fast = ["orjson"]
        [dependency-groups]
        dev = ["pytest", {include-group = "other"}]
        """)
    deps = parse_file(p)
    assert [d.name for d in deps] == ["numpy", "attrs", "orjson", "pytest"]
    assert deps[1].version == "25.1.0"


def test_collect_dir_autodetect_prefers_lock(tmp_path):
    write(tmp_path, "requirements.txt", "six==1.16.0\n")
    write(tmp_path, "uv.lock", '[[package]]\nname="a"\nversion="1"\nsource={registry="x"}\n')
    deps, sources = collect([str(tmp_path)])
    assert [d.name for d in deps] == ["a"]
    assert sources[0].endswith("uv.lock")


def test_collect_specs_and_errors(tmp_path):
    deps, sources = collect(["numpy==1.26.4", "six"])
    assert deps[0].version == "1.26.4" and deps[1].version is None
    with pytest.raises(InputError):
        collect([str(tmp_path / "nope.txt")])
    with pytest.raises(InputError):
        collect([str(tmp_path)])
