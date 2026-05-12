"""pytest config for sts_lightspeed.

Adds the build directory to sys.path so the compiled `slaythespire`
module is importable in tests without requiring `pip install -e .` first.

Picks the build dir whose extension suffix matches the running interpreter
so we don't accidentally pull a stock-3.14 .so into a 3.14t test session
(or vice versa).
"""
from __future__ import annotations

import importlib.machinery
import sys
import sysconfig
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _candidate_build_dirs():
    yield _REPO_ROOT / "build"
    build_root = _REPO_ROOT / "build"
    if build_root.exists():
        for sub in build_root.iterdir():
            if sub.is_dir():
                yield sub


def _abi_suffixes() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split EXTENSION_SUFFIXES into (ABI-specific, generic) buckets.

    `importlib.machinery.EXTENSION_SUFFIXES` includes the bare `.so` as
    a catch-all on Linux; matching against it would accept a stale
    wrong-ABI build dir (e.g. a 3.14 stock .so picked up under a 3.14t
    interpreter). We try the ABI-specific suffixes first and only fall
    back to generic `.so` if nothing matches.
    """
    all_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES) or (".so",)
    specific = tuple(s for s in all_suffixes if s != ".so" and s.startswith("."))
    generic = tuple(s for s in all_suffixes if s == ".so")
    if not specific and not generic:
        return ((".so",), ())
    return specific, generic


def _matches(so_path: Path, suffixes: tuple[str, ...]) -> bool:
    name = so_path.name
    return any(name.endswith(suf) for suf in suffixes)


def pytest_configure(config: pytest.Config) -> None:
    # Add the Python package dir
    python_dir = _REPO_ROOT / "python"
    if python_dir.is_dir():
        sys.path.insert(0, str(python_dir))
    specific, generic = _abi_suffixes()
    # Pass 1: ABI-specific suffix match (e.g. cpython-314t-* under 3.14t).
    for d in _candidate_build_dirs():
        for so in d.glob("slaythespire*.so"):
            if specific and _matches(so, specific):
                sys.path.insert(0, str(d))
                return
    # Pass 2: generic .so fallback. Only used when no ABI-specific build
    # exists — protects against accidentally importing a 3.14 .so from
    # a 3.14t test session.
    for d in _candidate_build_dirs():
        for so in d.glob("slaythespire*.so"):
            if generic and _matches(so, generic):
                sys.path.insert(0, str(d))
                return
    raise pytest.UsageError(
        "Could not find compiled slaythespire extension. Run cmake build "
        "or `uv pip install -e .` before pytest."
    )


@pytest.fixture(scope="session")
def is_freethreaded() -> bool:
    return not getattr(sys, "_is_gil_enabled", lambda: True)()


@pytest.fixture(scope="session")
def python_impl() -> str:
    return sysconfig.get_config_var("EXT_SUFFIX") or ""
