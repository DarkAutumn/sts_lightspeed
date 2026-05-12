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


def test_shared_agent_rejected_at_runtime() -> None:
    """Phase 4 review-fix^2 guarantee: if a user shares one Agent
    instance across threads (the wrong pattern), the second concurrent
    playout call must fail loudly with RuntimeError, not silently
    produce corrupt results.

    Implementation: bindings wrap Agent.playout in an AgentBusyGuard
    that compare_exchange's an atomic flag and throws on contention.
    """
    shared_agent = sts.Agent()
    shared_agent.simulation_count_base = 200
    shared_agent.print_logs = False

    seen_runtime_error = threading.Event()
    barrier = threading.Barrier(2)

    def worker(seed: int) -> None:
        gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, 0)
        try:
            barrier.wait(timeout=5.0)
            shared_agent.playout(gc)
        except RuntimeError as exc:
            if "not reentrant" in str(exc):
                seen_runtime_error.set()

    threads = [
        threading.Thread(target=worker, args=(s,))
        for s in (4001, 4002)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)
        assert not t.is_alive(), "worker hung — re-entrance guard deadlocked"

    assert seen_runtime_error.is_set(), (
        "Sharing one Agent across two threads must surface a "
        "RuntimeError on the loser. None was observed — either the "
        "guard isn't engaging or the timing missed the overlap."
    )


def test_agent_config_property_rejected_during_playout() -> None:
    """Phase 4 review-fix^3 guarantee: mutating Agent config properties
    (simulation_count_base, print_logs, etc.) from another thread while
    that Agent is in a playout call must also throw RuntimeError, not
    silently corrupt a running simulation by changing knobs midway.

    This is the property-write equivalent of the playout re-entrance
    test above.
    """
    shared_agent = sts.Agent()
    shared_agent.simulation_count_base = 300
    shared_agent.print_logs = False

    seen_runtime_error = threading.Event()
    stop_playout = threading.Event()

    def playout_worker() -> None:
        # simulation_count_base=300 keeps the playout long enough
        # (~50-100 ms) that the writer thread has many overlap windows.
        gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 5001, 0)
        try:
            shared_agent.playout(gc)
        finally:
            stop_playout.set()

    def writer_worker() -> None:
        # Keep trying until either the guard rejects us OR the playout
        # finishes. We do NOT use a fixed iteration count — on a fast
        # machine that could complete before the playout's busy guard
        # is acquired, producing a spurious failure. On a slow machine
        # the playout could outlast 200 iterations.
        while not stop_playout.is_set():
            try:
                shared_agent.simulation_count_base = 999
            except RuntimeError as exc:
                if "not reentrant" in str(exc):
                    seen_runtime_error.set()
                    return

    threads = [
        threading.Thread(target=playout_worker),
        threading.Thread(target=writer_worker),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)
        assert not t.is_alive(), "worker hung — config guard deadlocked"

    assert seen_runtime_error.is_set(), (
        "Writing a config property while playout was running must "
        "raise RuntimeError. None was observed — either the property "
        "isn't guarded or the writer thread never overlapped with the "
        "guarded region (sign of a test-design bug, not a code bug)."
    )


@pytest.mark.freethreading
def test_throughput_scales_under_freethreading() -> None:
    """Phase 4.5 micro-benchmark.

    On a free-threaded interpreter we expect playout throughput at
    8 threads to be at least 3.0× a single-threaded baseline.
    Conservative threshold (real measured speedup on a 10C/20T host
    is >= 5× but we allow headroom for noisy / shared host).

    Skipped under stock-GIL interpreters since the GIL serializes
    everything and any speedup would be from epoch / heat effects only.

    Measurement design: we take the *best of N repetitions* for both
    serial and parallel timings to reject single-preemption noise. Each
    timed window also runs enough work that wall-clock is comfortably
    above scheduler-jitter scale (~100 ms+).
    """
    if sys._is_gil_enabled():  # type: ignore[attr-defined]
        pytest.skip("GIL enabled — true parallelism not expected")

    # Total work per timed window. Tuned so that even a "fast" host
    # spends more than 100 ms in each window — well above scheduler
    # noise. Each playout is ~20 ms on this host.
    n_serial = 16
    n_parallel = 128  # 16 per thread × 8 threads
    repetitions = 3

    # Warmup — exercise the .so cold paths and let CPU governors settle.
    for s in range(95, 99):
        _run_playout(s)

    serial_best = float("inf")
    for rep in range(repetitions):
        base = 2_000_000 + rep * 1_000
        seeds = list(range(base, base + n_serial))
        t0 = time.perf_counter()
        for s in seeds:
            _run_playout(s)
        dt = time.perf_counter() - t0
        serial_best = min(serial_best, dt)
    serial_throughput = n_serial / serial_best

    parallel_best = float("inf")
    for rep in range(repetitions):
        base = 3_000_000 + rep * 10_000
        seeds = list(range(base, base + n_parallel))
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_run_playout, seeds))
        dt = time.perf_counter() - t0
        parallel_best = min(parallel_best, dt)
    parallel_throughput = n_parallel / parallel_best

    speedup = parallel_throughput / serial_throughput
    print(
        f"\nthroughput: serial={serial_throughput:.1f} pl/s "
        f"parallel(8t)={parallel_throughput:.1f} pl/s "
        f"speedup={speedup:.2f}x "
        f"(serial_best={serial_best*1000:.1f}ms over {n_serial} pl, "
        f"parallel_best={parallel_best*1000:.1f}ms over {n_parallel} pl)"
    )
    assert speedup >= 3.0, (
        f"Free-threaded build did not deliver expected speedup. "
        f"Got {speedup:.2f}x at 8 threads (target >= 3.0x). "
        f"Either a global lock leaked back in, or the C++ path holds "
        f"a mutex it didn't used to."
    )
