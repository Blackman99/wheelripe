import pytest

from wheelripe.tags import Python, compatible, make_platform, parse_wheel_filename, platform_ok

LINUX = make_platform("linux-x86_64")


def ok(fname, py, plat=LINUX):
    return compatible(parse_wheel_filename(fname), Python.parse(py), plat)


# PEP 803 "Compatibility Overview" table, columns: 3.14, 3.14t, 3.15, 3.15t, 3.16, 3.16t
PEP803 = {
    "cp314-cp314": [1, 0, 0, 0, 0, 0],
    "cp314-cp314t": [0, 1, 0, 0, 0, 0],
    "cp314-abi3": [1, 0, 1, 0, 1, 0],
    "cp314-abi3t": [0, 1, 0, 1, 0, 1],  # (*) cannot be built, but the tag is defined
    "cp314-abi3.abi3t": [1, 1, 1, 1, 1, 1],
    "cp315-cp315": [0, 0, 1, 0, 0, 0],
    "cp315-cp315t": [0, 0, 0, 1, 0, 0],
    "cp315-abi3": [0, 0, 1, 0, 1, 0],
    "cp315-abi3t": [0, 0, 0, 1, 0, 1],
    "cp315-abi3.abi3t": [0, 0, 1, 1, 1, 1],
}
TARGETS = ["3.14", "3.14t", "3.15", "3.15t", "3.16", "3.16t"]


@pytest.mark.parametrize("tag", sorted(PEP803))
def test_pep803_table(tag):
    got = [int(ok(f"x-1.0-{tag}-manylinux_2_28_x86_64.whl", t)) for t in TARGETS]
    assert got == PEP803[tag]


def test_pure_and_none():
    assert ok("six-1.16.0-py2.py3-none-any.whl", "3.15")
    assert ok("six-1.16.0-py2.py3-none-any.whl", "3.15t")
    assert not ok("old-1.0-py2-none-any.whl", "3.15")
    assert ok("x-1.0-py315-none-any.whl", "3.15")
    assert not ok("x-1.0-py316-none-any.whl", "3.15")
    assert ok("x-1.0-cp315-none-manylinux_2_17_x86_64.whl", "3.15")
    assert not ok("x-1.0-cp314-none-manylinux_2_17_x86_64.whl", "3.15")


def test_old_abi3_works_on_new_gil_only():
    assert ok("cryptography-46-cp39-abi3-manylinux_2_28_x86_64.whl", "3.15")
    assert not ok("cryptography-46-cp39-abi3-manylinux_2_28_x86_64.whl", "3.15t")


def test_manylinux_glibc():
    p = make_platform("linux-x86_64", glibc="2.28")
    assert platform_ok("manylinux_2_28_x86_64", p)
    assert not platform_ok("manylinux_2_34_x86_64", p)
    assert platform_ok("manylinux2014_x86_64", p)
    assert platform_ok("manylinux1_x86_64", p)
    assert not platform_ok("manylinux_2_28_aarch64", p)
    assert not platform_ok("musllinux_1_2_x86_64", p)
    assert platform_ok("linux_x86_64", p)
    assert ok("a-1-cp315-cp315-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", "3.15", p)


def test_musllinux():
    p = make_platform("musllinux-x86_64")
    assert platform_ok("musllinux_1_1_x86_64", p)
    assert platform_ok("musllinux_1_2_x86_64", p)
    assert not platform_ok("musllinux_1_3_x86_64", p)
    assert not platform_ok("manylinux_2_17_x86_64", p)


def test_macos():
    arm = make_platform("macos-arm64", macos="14")
    intel = make_platform("macos-x86_64", macos="13")
    assert platform_ok("macosx_11_0_arm64", arm)
    assert platform_ok("macosx_14_0_arm64", arm)
    assert not platform_ok("macosx_15_0_arm64", arm)
    assert platform_ok("macosx_10_9_universal2", arm)
    assert not platform_ok("macosx_10_9_x86_64", arm)
    assert platform_ok("macosx_10_9_x86_64", intel)
    assert platform_ok("macosx_10_13_universal2", intel)
    assert not platform_ok("macosx_14_0_x86_64", intel)
    assert not platform_ok("macosx_11_0_arm64", intel)


def test_windows():
    assert platform_ok("win_amd64", make_platform("windows"))
    assert not platform_ok("win32", make_platform("windows"))
    assert platform_ok("win32", make_platform("windows-x86"))
    assert platform_ok("win_arm64", make_platform("windows-arm64"))


def test_parse_python():
    assert Python.parse("3.15t") == Python(3, 15, True)
    assert Python.parse("cp315") == Python(3, 15, False)
    assert str(Python.parse("315t")) == "3.15t"
    with pytest.raises(ValueError):
        Python.parse("three")


def test_unknown_platform():
    with pytest.raises(ValueError):
        make_platform("amiga")


def test_not_a_wheel():
    assert parse_wheel_filename("x-1.0.tar.gz") is None
    assert parse_wheel_filename("bad.whl") is None
