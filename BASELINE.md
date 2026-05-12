# Baseline

Records the state of the simulator at each phase boundary, for
regression-gate comparison.

## Phase 1 — Pristine baseline (2026-05-12)

- Toolchain: gcc 16.1.1, cmake 4.3.2, ninja 1.13.2, Python 3.14.4 (default).
- pybind11: v2.11.1 (bundled). **Will need ≥2.13.6 for free-threading.**
- nlohmann/json: bundled, requires `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`.
- C++ targets built clean: `main`, `test`, `small-test`,
  `slaythespire.cpython-314-x86_64-linux-gnu.so`.
- Integration test `python integration/run_tests.py --quick --no-game --seed 12345`:
  **PASS** (1 / 1, 50 steps, IRONCLAD).

### Patches applied to make the pristine fork build under gcc 16

GCC 16 / libstdc++ stopped transitively including `<algorithm>` from
the common containers. Added `#include <algorithm>` to:

- `include/game/Random.h`
- `src/combat/Actions.cpp`
- `src/combat/BattleContext.cpp`
- `src/combat/CardInstance.cpp`
- `src/combat/CardManager.cpp`
- `src/combat/MonsterSpecific.cpp`
- `src/game/Map.cpp`
- `src/sim/search/BattleScumSearcher2.cpp`
- `src/sim/search/ScumSearchAgent2.cpp`
- `src/sim/search/SimpleAgent.cpp`

These are pure header-inclusion fixes, no behavior change.

### Sync-harness baseline divergence counts

**Status:** Harness is Linux-ready (Phase 1.5 autopilot half done); live
baseline measurement is deferred — it requires the user to launch the
game interactively. Counts will be filled in once
`integration/run_sync_baseline.sh` is run with the live game.

| Character | Scenarios | Live runs | Divergences |
|---|---|---|---|
| IRONCLAD | 8 | _pending user_ | _pending user_ |
| SILENT | n/a | _phase 9a_ | _phase 9a_ |
| DEFECT | n/a | _phase 9b_ | _phase 9b_ |
| WATCHER | n/a | _phase 9c_ | _phase 9c_ |

## Phase 4 — Free-threaded build wiring (2026-05-12)

- pybind11 already at v2.13.6 since `29a833b`.
- `PYBIND11_MODULE(slaythespire, m, py::mod_gil_not_used())` declares
  the module supports the free-threaded build (no GIL re-enable on
  3.14t import).
- `py::call_guard<py::gil_scoped_release>()` added to:
  `Agent.playout`, `Agent.playout_battle`, `GameContext.pick_reward_card`,
  `GameContext.skip_reward_cards`, `GameContext.get_card_reward`,
  module-level `play_card`, module-level `potion`.
- 3.14t venv lives at `.venv-3.14t/`. Wheel produced:
  `slaythespire.cpython-314t-x86_64-linux-gnu.so`. Stock 3.14 still
  builds `cpython-314-*.so` in parallel; both can coexist in
  `build/<wheel-tag>/`.

### Threading micro-benchmark (Phase 4.5)

Measured on this host (Intel i9-10900X, 10C/20T):

| Mode | Threads | Throughput | Speedup |
|---|---|---|---|
| 3.14 (GIL on)   | 1 | (skipped — GIL serializes) | — |
| 3.14t (no GIL)  | 1 | 96 playouts/s | 1.00× |
| 3.14t (no GIL)  | 8 | 487 playouts/s | **5.06×** |

Threshold: ≥ 3.5× (assertion in `test_threading.py::test_throughput_scales_under_freethreading`).
Numbers come from short `Agent.simulation_count_base=50` playouts;
real PPO-driven workloads will be different shapes but the *parallel
scaling factor* is what we care about.
