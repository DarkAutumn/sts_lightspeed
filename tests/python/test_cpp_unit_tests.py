"""Run the in-tree C++ unit_tests executable as part of pytest.

The C++ executable lives at build_native/unit_tests (plain CMake build)
or build/<wheel_tag>/unit_tests (scikit-build-core editable build).
We discover whichever is present.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_unit_tests_executable() -> Path | None:
    candidates = [
        _REPO_ROOT / "build_native" / "unit_tests",
        _REPO_ROOT / "build" / "unit_tests",
    ]
    build_root = _REPO_ROOT / "build"
    if build_root.exists():
        for sub in build_root.iterdir():
            if sub.is_dir():
                candidates.append(sub / "unit_tests")
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    return None


def test_cpp_unit_tests_executable_runs() -> None:
    exe = _find_unit_tests_executable()
    if exe is None:
        pytest.skip(
            "unit_tests executable not built. Run: cmake --build build_native "
            "--target unit_tests"
        )
    result = subprocess.run(
        [str(exe)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(_REPO_ROOT),
    )
    sys.stderr.write(result.stderr)
    sys.stdout.write(result.stdout)
    assert result.returncode == 0, (
        f"C++ unit_tests exited with {result.returncode}; "
        f"see stderr above for failing assertions"
    )
