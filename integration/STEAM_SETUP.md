# Steam / ModTheSpire setup on Linux for sts_lightspeed sync testing

This document captures the verified, working configuration on a native
Linux Steam install of Slay the Spire for use with the
`integration/` sync harness.

## Verified install (this machine — Arch Linux, native Linux StS)

- Game install:
  `~/.local/share/Steam/steamapps/common/SlayTheSpire/`
  - `desktop-1.0.jar`  (StS game jar)
  - `mts-launcher.jar` (Steam-side ModTheSpire launcher)
  - bundled JRE in `jre/`
- Mods (installed via Steam Workshop subscription):
  - ModTheSpire: `~/.local/share/Steam/steamapps/workshop/content/646570/1605060445/ModTheSpire.jar`
  - BaseMod: `~/.local/share/Steam/steamapps/workshop/content/646570/1605833019/BaseMod.jar`
  - CommunicationMod: `~/.local/share/Steam/steamapps/workshop/content/646570/2131373661/CommunicationMod.jar`

## ModTheSpire config directory on Linux

`ConfigUtils.CONFIG_DIR` resolves to `$HOME/.config/ModTheSpire/` (confirmed
by decompiling `com/evacipated/cardcrawl/modthespire/lib/ConfigUtils.class`
from the workshop install — it picks `.config` under `IS_OS_LINUX`).

So CommunicationMod's config file is at:

```
~/.config/ModTheSpire/CommunicationMod/config.properties
```

(Note: macOS uses `~/Library/Preferences/ModTheSpire/...`; the harness's
original `setup_communication_mod.sh` hardcoded the macOS path.)

## Configure CommunicationMod to launch the bridge

Run this once (after at least one launch of StS via ModTheSpire so the
directory exists; the script will create the directory if needed):

```bash
./integration/setup_communication_mod.sh
```

This writes:

```
command=python <repo>/integration/harness/communication_bridge.py --state-dir /tmp/sts_bridge
runAtGameStart=true
```

## Launch Slay the Spire with mods

Steam by default launches `SlayTheSpire.exe` (a stub on Linux) or
`desktop-1.0.jar` directly. To use the mods, launch via ModTheSpire.

**Option A — Steam launch option (recommended):**

In Steam → Slay the Spire → Properties → Launch Options, set:

```
java -jar "%STEAM_DIR%/steamapps/workshop/content/646570/1605060445/ModTheSpire.jar" --mods CommunicationMod,BaseMod %command%
```

(Adjust the path as needed; Steam expands `%STEAM_DIR%`.)

**Option B — direct CLI:**

```bash
cd ~/.local/share/Steam/steamapps/common/SlayTheSpire
java -jar ~/.local/share/Steam/steamapps/workshop/content/646570/1605060445/ModTheSpire.jar --mods CommunicationMod,BaseMod
```

The ModTheSpire UI will appear. Tick CommunicationMod (and BaseMod is
required by CommunicationMod). Click Play.

## Run the sync harness

In a separate terminal:

```bash
cd ~/work/git/sts_lightspeed
source .venv/bin/activate   # or use uv run
PYTHONPATH=build python integration/run_tests.py --quick --seed 12345
```

If everything is wired correctly, the test runner will connect to the
bridge at `/tmp/sts_bridge/` and drive the live game in lockstep with
the simulator, comparing states at each step.

## Troubleshooting

- **"Failed to connect to game"** — the bridge files at `/tmp/sts_bridge/`
  aren't being written. Check that CommunicationMod is enabled in the
  ModTheSpire UI, and that `config.properties` has the correct path.
- **`config.properties` missing** — launch StS through ModTheSpire at
  least once with CommunicationMod selected; ModTheSpire creates the
  directory on first save. Then run `setup_communication_mod.sh`.
- **Bridge locked by another process** — `rm /tmp/sts_bridge/.coordinator/lock`
  or `sts-bridge lock-status` to diagnose.
