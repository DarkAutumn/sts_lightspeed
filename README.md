# sts_lightspeed

For tree search and simulation of the popular rogue-like deckbuilder
game Slay The Spire.

**This is the DarkAutumn fork** — a hand-merged superset of
`ben-w-smith/sts_lightspeed` extended for free-threaded Python and
in-process RL training. Upstream features (all four characters, all
relics, full combat simulation) are preserved; this fork adds a
Python API, pybind11 bindings, a free-threaded build (3.14t), a
Gym-friendly `BattleContext` surface, and a sync harness against the
live Steam game. See `docs/ARCHITECTURE.md` and `CHANGELOG.md` for
the full provenance and patch history.

## Features

- C++17, builds with GCC and Clang
- Standalone — no dependency on the Steam build
- Designed to be 100% RNG-accurate to the live game
  (CommunicationMod sync harness in `integration/`)
- Playable in console
- ~1M random IRONCLAD playouts in 5 s with 16 threads
- Loading from save files (combat-only)
- Tree search (best result given RNG state)
- **Python bindings** via pybind11
  (`import slaythespire` or `import sts_lightspeed`)
- **Free-threaded Python support** (3.14t, `mod_gil_not_used()`).
  GIL released around every binding that touches `BattleContext` /
  `GameContext`.

## Build

The C++ engine builds with CMake + Ninja:

```bash
git submodule update --init --recursive
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

Targets: `main`, `test`, `small-test`, `unit_tests`, `stress_test`,
`slaythespire` (the Python extension `.so`).

### Python wheel (scikit-build-core + uv)

The recommended workflow uses [`uv`](https://docs.astral.sh/uv/) for
environment management:

```bash
# Free-threaded Python 3.14
uv python install cpython-3.14.5rc1+freethreaded
uv venv --python 3.14t
uv pip install -e .
```

`pip install -e .` rebuilds the C++ extension on every change via
scikit-build-core. The wheel installs `slaythespire.<abi>.so` and the
thin Python shim `sts_lightspeed/` that re-exports it under a stable
name.

```python
import sts_lightspeed as sts
gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed=1, ascension=0)
print(gc.deck.size, [str(c.id) for c in gc.deck][:3])
```

### Sanitizer builds

`docs/TESTING.md` and Phase 12 of `CHANGELOG.md` document the
`build_tsan/` and `build_asan/` Clang-driven sanitizer configurations.
Quick recipe:

```bash
mkdir build_tsan && cd build_tsan
cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_CXX_COMPILER=clang++ \
  -DCMAKE_CXX_FLAGS='-fsanitize=thread -fno-omit-frame-pointer -O1 -g' \
  -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=thread' \
  ..
ninja unit_tests stress_test
TSAN_OPTIONS='halt_on_error=1' ./stress_test 8 1000 1
```

## Testing

Three test surfaces, all kept green:

| Layer | How to run |
|---|---|
| C++ unit (1325 assertions) | `build_native/unit_tests` |
| C++ MT stress | `build_tsan/stress_test 8 1000 1` |
| Python (smoke, bindings, threading, parity) | `uv run --python 3.14t pytest tests/python -q` |
| CommunicationMod sync harness (live game) | `integration/run_tests.py` (manual, requires Steam jar) |

The CommunicationMod sync harness is **NOT** in CI but is the
authoritative parity gate. See `docs/TESTING.md`.

## Implementation progress

- All enemies
- All relics
- All Ironclad cards
- All Silent cards (incl. NIGHTMARE engine, Phase 9.x.5)
- All Defect cards (incl. full orb system)
- All Watcher cards
- All colorless cards
- Everything outside of combat / all acts

Known gaps and pre-existing engine bugs are tracked in
`docs/KNOWN_ISSUES.md`.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — engine layout,
  binding surface, sync-harness design
- [`docs/TESTING.md`](docs/TESTING.md) — test layers, sanitizer
  builds, sync-harness operation
- [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) — current open
  engine bugs, sync-harness divergences, ISSUE numbering
- [`CHANGELOG.md`](CHANGELOG.md) — chronological per-phase change log

## Origin and licensing

This fork builds on:
- `gamerpuppy/sts_lightspeed` — the original tree-search simulator
  (IRONCLAD-only)
- `ben-w-smith/sts_lightspeed` — extends to all four characters
  (current base)
- `jdc5549/sts_lightspeed` — full `BattleContext` Python bindings
  (ported)
- `langsfang/sts_lightspeed` — `Player::relicBits` widening (ported)
- `BoxedCoffee/sts_lightspeed` — RNG parity fixes
  (selective cherry-picks; see Phase 10 in CHANGELOG)
- `SimoneBarbaro/sts_lightspeed` — battle observation encoder
  (ported and parameterized over the full card enum)

License: same as upstream.

