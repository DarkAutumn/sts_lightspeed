"""pytest config for sts_lightspeed.

Adds the build directory to sys.path so the compiled `slaythespire`
module is importable in tests without requiring `pip install -e .` first.
"""
from __future__ import annotations

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


def pytest_configure(config: pytest.Config) -> None:
    # Add the Python package dir
    python_dir = _REPO_ROOT / "python"
    if python_dir.is_dir():
        sys.path.insert(0, str(python_dir))
    # Then locate the compiled extension
    for d in _candidate_build_dirs():
        for so in d.glob("slaythespire*.so"):
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
