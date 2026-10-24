"""Build the meta bundle: patch metaf sources, compile .met files, write the launcher catalog.

    python tools/build.py            # build everything into dist/
    python tools/build.py --no-patch # compile upstream sources unchanged (for comparison)

Inputs:  sources.json, tabs.json, metas/<source>/**   (upstream files, never edited in place)
Outputs: build/af/<Meta>.af        patched metaf source actually compiled
         build/report.md           what was patched / warnings per meta
         build/catalog.json        machine-readable catalog
         dist/VirindiTank/          .met + .utl files to copy into the VirindiTank folder
         dist/Decal Plugins/MetaLauncher/   the Decal plugin, catalog.tsv, registry file
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METAF = ROOT / "tools" / "metaf-bin" / "metaf.exe"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
PLUGIN_PROJ = ROOT / "plugin" / "MetaLauncher" / "MetaLauncher.csproj"
PLUGIN_GUID = "4c1e5f0a-7d2b-4a8e-9b6f-3e2d1c0b9a87"   # must match [assembly: Guid] in the plugin
DECAL_SURROGATE = "{71A69713-6593-47EC-0002-0000000DECA1}"  # Decal's host for .NET plugins
INSTALL_DIR = r"C:\Games\Decal Plugins\MetaLauncher"


# ---------------------------------------------------------------- patches
# Each patch takes the metaf text and returns (new_text, number_of_changes).
# Patches must be exact and conservative: anything they don't recognise is left alone.

EGG_GE = re.compile(r"ItemCountGE\s+1\s+\{Egg\}")
EGG_LE = re.compile(r"ItemCountLE\s+0\s+\{Egg\}")
EGG_ECHO = re.compile(r"(Expects|Requires) one character to be leader and have an egg")


def patch_egg_leader(text):
    """Leader = fellowship leader, instead of 'whoever carries an item named exactly Egg'."""
    text, a = EGG_GE.subn("Expr {getfellowshipisleader[]==1}", text)
    text, b = EGG_LE.subn("Expr {getfellowshipisleader[]==0}", text)
    text, _ = EGG_ECHO.subn(r"\1 the fellowship leader to lead the group", text)
    return text, a + b


PATCHES = [("egg-leader", patch_egg_leader)]


# ---------------------------------------------------------------- analysis

CHAT_CMD = re.compile(r'ChatMatch\s*\{([^}]*?)"(![A-Za-z]+)')
LOOT_LOAD = re.compile(r"/vt loot load ([^}\s]+\.utl)", re.I)
META_LOAD = re.compile(r"/vt meta load ([A-Za-z0-9_\-]+)\}", re.I)
AUTHOR = re.compile(r"echo\[[^\]]{0,80}? by ([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)\s*,")


def chat_commands(text):
    """Commands the meta listens for, with the exact line the launcher must send.
    Patterns that require [Fellowship] only hear fellowship chat, so those go out with /f."""
    found = {}
    for prefix, cmd in CHAT_CMD.findall(text):
        fellow = "Fellowship" in prefix
        if cmd not in found or fellow:
            found[cmd] = ("/f " if fellow else "") + cmd
    return [{"cmd": c, "send": found[c]} for c in sorted(found)]


def humanize(stem):
    s = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Z])", " ", stem)
    s = re.sub(r"\bV ?(\d+)$", r"v\1", s)
    return s


def analyse(text):
    # metaf files start with a keyword list for editor auto-completion; it names every function
    text = "\n".join(l for l in text.splitlines() if not l.startswith("~~ FOR AUTO-COMPLETION"))
    authors = [a for a in AUTHOR.findall(text) if a in ("Sun Invictus",) or " " in a]
    return {
        "fellowship": bool(re.search(r"getfellowship|/ub bc", text)),
        "tn_tie": "Primary Portal Recall" in text or "Secondary Portal Recall" in text,
        "aphus": "aphus" in text.lower(),
        "egg": len(EGG_GE.findall(text)) + len(EGG_LE.findall(text)),
        "chat_commands": chat_commands(text),
        "loot_profiles": sorted(set(LOOT_LOAD.findall(text))),
        "returns_to_default_meta": "getgvar[defaultMeta]" in text,
        "loads_metas": sorted(set(META_LOAD.findall(text))),
        "credited": authors[0] if authors else None,
    }


# ---------------------------------------------------------------- helpers

def metaf(src, dst):
    r = subprocess.run([str(METAF), str(src), str(dst)], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    if r.returncode != 0 or not Path(dst).exists():
        raise RuntimeError((r.stdout + r.stderr).strip()[-400:])


def read_text(p):
    with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()  # newline="" keeps CRLF exactly as upstream wrote it


def write_text(p, s):
    p.write_text(s, encoding="utf-8", errors="surrogateescape", newline="")


def pick_tab(rel, name, tabs_cfg):
    if name in tabs_cfg["overrides"]:
        return tabs_cfg["overrides"][name]
    for rule in tabs_cfg["rules"]:
        if re.search(rule["match"], rel):
            return rule["tab"]
    return "Misc"


def tsv_field(s):
    return str(s).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_catalog_tsv(path, tabs, catalog):
    """One meta per line, read by the plugin (no JSON library needed on .NET Framework).
    Line 1: #tabs<TAB>Quest<TAB>KTs...   Then: tab, name, title, status, author, fellowship,
    needs_tn_tie, commands (label=send;label=send), notes (joined with ' | ')."""
    lines = ["#tabs\t" + "\t".join(tabs)]
    for e in catalog:
        cmds = ";".join(f"{c['cmd']}={c['send']}" for c in e["chat_commands"])
        row = [e["tab"], e["name"], e["title"], e["status"], e["author"],
               "1" if e["fellowship"] else "0", "1" if e["needs_tn_tie"] else "0",
               cmds, " | ".join(e["notes"])]
        lines.append("\t".join(tsv_field(x) for x in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reg(path):
    """Registry entry Decal reads to load the plugin (same shape Decal keeps for any .NET plugin)."""
    key = r"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Decal\Plugins\{" + PLUGIN_GUID + "}"
    path.write_text("\n".join([
        "Windows Registry Editor Version 5.00", "",
        f"[{key}]",
        '@="Meta Launcher"',
        '"Assembly"="MetaLauncher.dll"',
        '"Path"="' + INSTALL_DIR.replace("\\", "\\\\") + '"',
        '"Object"="MetaLauncher.PluginCore"',
        f'"Surrogate"="{DECAL_SURROGATE}"',
        '"Enabled"=dword:00000001', ""]), encoding="utf-16", newline="\r\n")


def build_plugin(out_dir):
    r = subprocess.run(["dotnet", "build", str(PLUGIN_PROJ), "-c", "Release", "-nologo", "-v", "q",
                        "-o", str(BUILD / "plugin")], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-500:])
    shutil.copy2(BUILD / "plugin" / "MetaLauncher.dll", out_dir / "MetaLauncher.dll")


HAS_STATES = re.compile(r"^\s*STATE:", re.M)


def find_metas(src_dir):
    """Yield (path, status).
    published: upstream shipped a .met. Built from the sibling .af when it has states (upstream
               edits the .af first; several shipped .met files are older than their .af).
    draft:     .af with states but no published .met (upstream says some are incomplete)."""
    for p in sorted(src_dir.rglob("*")):
        if "navs" in p.relative_to(src_dir).parts[:-1]:
            continue
        if p.suffix == ".met":
            af = p.with_suffix(".af")
            yield (af if af.exists() and HAS_STATES.search(read_text(af)) else p), "published"
        elif p.suffix == ".af" and not p.with_suffix(".met").exists() and HAS_STATES.search(read_text(p)):
            yield p, "draft"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-patch", action="store_true")
    args = ap.parse_args()
    if not METAF.exists():
        sys.exit("metaf.exe not found - run tools/get-metaf.ps1 first")

    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    tabs_cfg = json.loads((ROOT / "tabs.json").read_text(encoding="utf-8"))
    for d in (BUILD, DIST):
        shutil.rmtree(d, ignore_errors=True)
    (BUILD / "af").mkdir(parents=True)
    (BUILD / "tmp").mkdir()
    vt = DIST / "VirindiTank"
    vt.mkdir(parents=True)
    plugin_dir = DIST / "Decal Plugins" / "MetaLauncher"
    plugin_dir.mkdir(parents=True)

    catalog, report, errors, skipped = [], [], [], []
    seen = {}
    for src_id, src in sources.items():
        src_dir = ROOT / "metas" / src_id
        for p, status in find_metas(src_dir):
            name = p.stem
            rel = p.relative_to(src_dir).as_posix()
            if name.lower() in seen:
                errors.append(f"name clash: {rel} vs {seen[name.lower()]}")
                continue
            seen[name.lower()] = rel
            notes = []
            if p.suffix == ".met":
                af = BUILD / "tmp" / f"{name}.af"
                metaf(p, af)
                text = read_text(af)
                if not HAS_STATES.search(text):
                    skipped.append(f"{rel}: upstream .met is empty (no states)")
                    continue
                notes.append("no upstream .af; decompiled from upstream .met")
            else:
                text = read_text(p)
            info = analyse(text)
            applied = {}
            if not args.no_patch:
                for pid, fn in PATCHES:
                    text, n = fn(text)
                    if n:
                        applied[pid] = n
            out_af = BUILD / "af" / f"{name}.af"
            write_text(out_af, text)
            try:
                metaf(out_af, vt / f"{name}.met")
            except RuntimeError as e:
                (skipped if status == "draft" else errors).append(
                    f"{rel}: does not compile: " + " | ".join(l for l in str(e).splitlines() if "LINE" in l or "No " in l))
                continue

            folder = p.parent
            shipped_utl = []
            for utl in sorted(folder.glob("*.utl")):
                shutil.copy2(utl, vt / utl.name)
                shipped_utl.append(utl.name)
            missing_utl = [u for u in info["loot_profiles"]
                           if u.lower() not in {s.lower() for s in shipped_utl}]
            if missing_utl:
                notes.append("loads loot profile(s) you must supply: " + ", ".join(missing_utl))
            if info["aphus"]:
                notes.append("uses Aphus Lassel Recall")
            readme = folder / "README.md"
            entry = {
                "name": name,
                "title": humanize(name),
                "tab": pick_tab(rel, name, tabs_cfg),
                "status": status,
                "source": src_id,
                "author": info["credited"] or src["default_author"],
                "path": rel,
                "readme": f"metas/{src_id}/{readme.relative_to(src_dir).as_posix()}" if readme.exists() else None,
                "fellowship": info["fellowship"],
                "needs_tn_tie": info["tn_tie"],
                "chat_commands": info["chat_commands"],
                "loot_profiles": info["loot_profiles"],
                "returns_to_default_meta": info["returns_to_default_meta"],
                "patches": applied,
                "notes": notes,
            }
            catalog.append(entry)
            report.append(entry)

    # metas that chain-load a meta we don't ship
    names = {e["name"].lower() for e in catalog}
    for src_id in sources:
        for e in catalog:
            text = read_text(BUILD / "af" / f"{e['name']}.af")
            for m in META_LOAD.findall(text):
                if m.lower() not in names:
                    e["notes"].append(f"chain-loads '{m}', which is not in this bundle")

    catalog.sort(key=lambda e: (tabs_cfg["tabs"].index(e["tab"]), e["title"].lower()))
    (BUILD / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    write_catalog_tsv(plugin_dir / "catalog.tsv", tabs_cfg["tabs"], catalog)
    write_reg(plugin_dir / "MetaLauncher.reg")
    try:
        build_plugin(plugin_dir)
    except RuntimeError as e:
        errors.append(f"plugin build failed: {e}")
    shutil.rmtree(BUILD / "tmp")

    # report
    lines = ["# Build report", ""]
    by_tab = {}
    for e in catalog:
        by_tab.setdefault(e["tab"], []).append(e)
    lines.append("| Tab | Metas |")
    lines.append("|---|---|")
    for t in tabs_cfg["tabs"]:
        lines.append(f"| {t} | {len(by_tab.get(t, []))} |")
    lines += ["", f"Egg leader patched: {sum(1 for e in catalog if 'egg-leader' in e['patches'])} metas, "
              f"{sum(e['patches'].get('egg-leader', 0) for e in catalog)} conditions", ""]
    if skipped:
        lines += ["## Not built", ""] + [f"- {x}" for x in skipped] + [""]
    if errors:
        lines += ["## Errors", ""] + [f"- {x}" for x in errors] + [""]
    for t in tabs_cfg["tabs"]:
        lines += [f"## {t}", ""]
        for e in by_tab.get(t, []):
            flags = []
            if e["fellowship"]:
                flags.append("fellowship")
            if e["needs_tn_tie"]:
                flags.append("TN tie")
            if e["patches"]:
                flags.append("patched: " + ", ".join(f"{k} x{v}" for k, v in e["patches"].items()))
            if e["chat_commands"]:
                flags.append("commands: " + " ".join(c["send"] for c in e["chat_commands"]))
            if e["status"] == "draft":
                flags.insert(0, "DRAFT")
            lines.append(f"- **{e['title']}** (`{e['name']}`, {e['author']}) " + "; ".join(flags))
            for n in e["notes"]:
                lines.append(f"  - {n}")
        lines.append("")
    (BUILD / "report.md").write_text("\n".join(lines), encoding="utf-8")

    drafts = sum(1 for e in catalog if e["status"] == "draft")
    print(f"{len(catalog)} metas built ({drafts} drafts), {len(skipped)} not built, {len(errors)} errors -> {DIST}")
    for t in tabs_cfg["tabs"]:
        print(f"  {t:9} {len(by_tab.get(t, []))}")
    for x in errors:
        print("  ERROR", x)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
