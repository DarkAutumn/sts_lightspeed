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


def _abi_suffixes() -> tuple[str, ...]:
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    if not suffixes:
        return (".so",)
    return suffixes


def _extension_matches_abi(so_path: Path, abi_suffixes: tuple[str, ...]) -> bool:
    name = so_path.name
    return any(name.endswith(suf) for suf in abi_suffixes)


def pytest_configure(config: pytest.Config) -> None:
    # Add the Python package dir
    python_dir = _REPO_ROOT / "python"
    if python_dir.is_dir():
        sys.path.insert(0, str(python_dir))
    abi_suffixes = _abi_suffixes()
    fallback: Path | None = None
    for d in _candidate_build_dirs():
        for so in d.glob("slaythespire*.so"):
            if _extension_matches_abi(so, abi_suffixes):
                sys.path.insert(0, str(d))
                return
            if fallback is None:
                fallback = d
    if fallback is not None:
        sys.path.insert(0, str(fallback))
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
