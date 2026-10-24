"""Zip dist/ into a player-ready release: release/MetaLauncher-<version>.zip

    python tools/package.py 0.1.0

Layout inside the zip: VirindiTank/ (metas + loot profiles), MetaLauncher/ (Decal plugin,
catalog, .reg), INSTALL.txt, licenses and credits. Run tools/build.py first.
"""
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "0.1.0"
    name = f"MetaLauncher-{version}"
    files = {}
    for p in sorted((ROOT / "dist" / "VirindiTank").iterdir()):
        files[f"{name}/VirindiTank/{p.name}"] = p
    for p in sorted((ROOT / "dist" / "Decal Plugins" / "MetaLauncher").iterdir()):
        files[f"{name}/MetaLauncher/{p.name}"] = p
    files[f"{name}/INSTALL.txt"] = ROOT / "packaging" / "INSTALL.txt"
    files[f"{name}/LICENSE.txt"] = ROOT / "LICENSE"
    files[f"{name}/LICENSE-metas.txt"] = ROOT / "metas" / "ragnar" / "LICENSE"
    files[f"{name}/CREDITS.md"] = ROOT / "CREDITS.md"

    out = ROOT / "release" / f"{name}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in files.items():
            z.write(src, arc)  # forward-slash paths, readable by every unzip tool
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
    if bad:
        sys.exit(f"corrupt entry: {bad}")
    print(f"{out} ({out.stat().st_size:,} bytes, {len(files)} files)")


if __name__ == "__main__":
    main()
