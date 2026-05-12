"""Phase 4 thread-safety + parallelism tests.

These exercise the in-process multithreaded execution path. They run
under both stock 3.14 (GIL on) and 3.14t (GIL off), but the throughput
test only asserts a speedup target under 3.14t — under stock 3.14 we
expect threading to *not* help and only assert correctness, not perf.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import slaythespire as sts


def _run_playout(seed: int) -> tuple[int, int, int]:
    """Drive a single Agent.playout() to completion. Returns
    (outcome, floor_num, deck_size) — a stable fingerprint that catches
    determinism drift between the single- and multi-threaded executions.
    """
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, 0)
    agent = sts.Agent()
    agent.simulation_count_base = 50
    agent.print_logs = False
    agent.playout(gc)
    return int(gc.outcome), int(gc.floor_num), len(gc.deck)


@pytest.mark.freethreading
def test_freethreaded_interpreter() -> None:
    """Sanity check: under .venv-3.14t this should report GIL off."""
    gil_enabled = sys._is_gil_enabled()  # type: ignore[attr-defined]
    if "t-x86_64" in (sys.implementation.cache_tag or ""):
        assert gil_enabled is False, (
            "Running under cache_tag implying free-threaded build but "
            "GIL is reported as enabled. Did something turn it back on?"
        )


def test_threaded_playouts_match_serial() -> None:
    """N=8 threads × disjoint seeds — each thread's playout result must
    match a serial reference. Validates that nothing in the C++ path
    has hidden mutable global state that would be corrupted by parallel
    Agent.playout() calls.
    """
    seeds = [1 << 20 | i for i in range(8)]
    serial = [_run_playout(s) for s in seeds]
    with ThreadPoolExecutor(max_workers=8) as ex:
        parallel = list(ex.map(_run_playout, seeds))
    assert serial == parallel, (
        f"Determinism drift between serial and threaded playouts.\n"
        f"  serial:   {serial}\n  parallel: {parallel}"
    )


def test_threaded_playouts_independent_seeds_diverge() -> None:
    """Different seeds must produce at least some different fingerprints
    under multithreading. Guards against the inverse failure mode where
    a shared RNG would homogenize every thread's result.
    """
    seeds = list(range(100, 116))
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(_run_playout, seeds))
    unique = {r for r in results}
    assert len(unique) > 1, (
        f"All 16 playouts with distinct seeds produced identical "
        f"fingerprints — RNG state may be shared across threads. "
        f"results={results}"
    )


@pytest.mark.freethreading
def test_throughput_scales_under_freethreading() -> None:
    """Phase 4.5 micro-benchmark.

    On a free-threaded interpreter we expect playout throughput at
    8 threads to be at least 3.5× a single-threaded baseline.
    Conservative threshold (real measured speedup on a 10C/20T host
    should be >= 5× but we allow headroom for noisy CI / shared host).

    Skipped under stock-GIL interpreters since the GIL serializes
    everything and any speedup would be from epoch / heat effects only.
    """
    if sys._is_gil_enabled():  # type: ignore[attr-defined]
        pytest.skip("GIL enabled — true parallelism not expected")

    n_per_thread = 4
    seeds_single = list(range(2000, 2000 + n_per_thread))
    seeds_parallel = list(range(3000, 3000 + n_per_thread * 8))

    # Warmup (don't time the first call — interpreter / .so cold)
    _run_playout(99)

    t0 = time.perf_counter()
    for s in seeds_single:
        _run_playout(s)
    serial_dt = time.perf_counter() - t0
    serial_throughput = n_per_thread / serial_dt

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(_run_playout, seeds_parallel))
    parallel_dt = time.perf_counter() - t0
    parallel_throughput = (n_per_thread * 8) / parallel_dt

    speedup = parallel_throughput / serial_throughput
    print(
        f"\nthroughput: serial={serial_throughput:.2f} pl/s "
        f"parallel(8t)={parallel_throughput:.2f} pl/s "
        f"speedup={speedup:.2f}x "
        f"(serial_dt={serial_dt:.2f}s parallel_dt={parallel_dt:.2f}s)"
    )
    assert speedup >= 3.5, (
        f"Free-threaded build did not deliver expected speedup. "
        f"Got {speedup:.2f}x at 8 threads (target >= 3.5x). "
        f"Either a global lock leaked back in, or the C++ path holds "
        f"a mutex it didn't used to."
    )
