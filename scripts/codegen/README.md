# scripts/codegen/

Historical code-generation inputs from the ben-w-smith fork's
implementation push for Silent/Defect/Watcher.

The `*_attacks.cpp` / `*_skills.cpp` / `*_powers.cpp` files here are
**not compilable** — they are bare `case CardId::FOO: { ... }` fragments
that the `inject_*.py` and `apply_all.py` scripts spliced into
`src/combat/BattleContext.cpp` to extend `playCardEffect()`.

The `get_*_cards.py` scripts scrape Slay-the-Spire wiki / data for card
metadata; the `fix_*.py` scripts patch the in-tree source after each
injection.

All of these are preserved for historical / regen reference. They are
not in any build target and should not be moved into `src/`.

If you need to regenerate (e.g. you find a card-effect bug and want to
batch-fix), see `apply_all.py` for the entry point.
