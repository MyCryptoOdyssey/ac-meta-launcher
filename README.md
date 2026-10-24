# AC Meta Launcher

An in-game window for Asheron's Call (End of Retail ACEmulator servers) that lists VirindiTank
metas in tabs (**Quest, KTs, Crafting, Misc, My Metas**) and loads the one you pick. It ships
with a bundle of 139 community metas and the build tool that produces that bundle.

- A Decal plugin with a VirindiViewService window: works with UtilityBelt 0.2.7 and 1.0.
- Fellowship metas use the **fellowship leader** instead of "whoever carries an Egg".
- **My Metas** shows every other `.met` in your VirindiTank folder.
- One-click **Load**, **Stop VTank / Start VTank**, and buttons for a meta's own chat commands (`!continue`, ...).

**Download:** see [Releases](../../releases) for a ready-to-install zip.

> **Status: beta (0.1.0).** Tested on one setup so far. Bug reports welcome via Issues.

## Disclaimer
- This is an unofficial fan project. It is not affiliated with or endorsed by Turbine, Warner Bros.,
  Daybreak, the ACEmulator project, Decal, Virindi, or the UtilityBelt team. Asheron's Call is a
  trademark of its respective owner.
- **Automation is not allowed on every server.** Check your server's rules before running metas;
  you are responsible for how you use them.
- Metas move, fight, loot, recall and talk to NPCs on your behalf and can get characters killed,
  stuck, or into places they shouldn't be. Watch them, especially on first runs.
- Provided **as is, without warranty of any kind** (see [LICENSE](LICENSE)). Metas marked
  **draft** were never published by their author and may be incomplete.

## Install (players)
Requires Decal, VirindiTank (which brings VirindiViewService) and UtilityBelt (0.2.7 or 1.0).
Close all AC clients first. (These steps are also in `INSTALL.txt` inside the release zip.)

1. Copy everything in the zip's `VirindiTank/` folder into your VirindiTank folder (usually `C:\Games\VirindiPlugins\VirindiTank`).
2. Copy the `MetaLauncher/` folder to `C:\Games\Decal Plugins\MetaLauncher\`.
3. Register it with Decal: double-click `MetaLauncher.reg` in that folder (Windows asks for permission).
   If you put the folder somewhere else, edit the `Path` line in the .reg first.
4. Open Decal's plugin list and make sure **Meta Launcher** is ticked (Decal keeps on/off per Windows user).
5. Fully restart the AC client (Decal loads plugins at launch). After login the **Meta Launcher** window appears.

## Using it
- Pick a tab, click a meta, read the yellow requirement lines, click **Load**.
- Most metas are fellowship metas: form the fellowship first and keep **Whole fellowship** ticked
  (sends `/ub bc /vt meta load ...` to all your clients). The fellowship leader leads.
- Many quest metas need a **portal tie to a Town Network portal** (Primary Portal Tie).
- Buttons such as `!continue` send the meta's own chat commands (fellowship chat where the meta expects it).
- **Stop VTank / Start VTank** send `/vt stop` / `/vt start` (the loaded meta stays loaded).
- **My Metas** lists every other `.met` in your VirindiTank folder; metas you add there show up at next login.
- **After a quest, switch to:** select any meta and click **Use selected**. Quest metas load it when
  they finish (they end with `/vt meta load` of UtilityBelt's `defaultMeta`).
- Loading turns on UtilityBelt's `VTank.PatchExpressionEngine`, which these metas need.
- Errors are written to `MetaLauncher\errors.txt` and mentioned in chat.

## What the build changes
Upstream metas are kept **unmodified** under `metas/`. `tools/build.py` applies these patches when it compiles:

| Patch | What | Why |
|---|---|---|
| `egg-leader` | `ItemCountGE 1 {Egg}` -> `Expr {getfellowshipisleader[]==1}`, `ItemCountLE 0 {Egg}` -> `...==0` | Leader is the fellowship leader; no one has to carry an Egg |

Verified: the patch changes only those lines (no other line differs across the 136 metas with source),
and with patches off the build reproduces 84 of the 103 upstream `.met` files byte for byte (the other 19
are ones whose upstream `.af` source is newer than the shipped `.met`). `build/report.md` lists every
meta, its tab, requirements and the patches applied.

## Repository layout
| Path | What |
|---|---|
| `metas/ragnar/` | FlyingRagnar's metas, unmodified, pinned commit (see `sources.json`) |
| `plugin/MetaLauncher/` | the Decal plugin (C#, .NET Framework 4.8) |
| `tools/build.py` | patch + compile metas with metaf, write the catalog, build the plugin |
| `tools/package.py` | zip `dist/` into a release |
| `tools/get-metaf.ps1` | fetch and build the metaf converter |
| `tabs.json` | which tab each meta goes in (rules + overrides) |

## Build (maintainers)
Needs Python 3, git, the .NET 8 SDK, and Decal + VirindiViewService installed (the plugin builds
against their DLLs; set `DecalDir` / `VVSDir` in `plugin/MetaLauncher/MetaLauncher.csproj` if yours differ).
```
powershell -File tools/get-metaf.ps1
python tools/build.py
python tools/package.py 0.1.0
```

## Credits and licenses
- Launcher and build tools: MIT, see [LICENSE](LICENSE).
- Bundled metas: FlyingRagnar (in-game credits: Sun Invictus), MIT, see [metas/ragnar/LICENSE](metas/ragnar/LICENSE).
- metaf by Eskarina of Morningthaw/Coldeve, GPL-3.0: used as a build tool, not redistributed.

Full details in [CREDITS.md](CREDITS.md).
