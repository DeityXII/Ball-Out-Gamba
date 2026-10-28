"""Build a single-file executable for the current OS.

    python packaging/build.py          # command-line program: dist/ballout(.exe)
    python packaging/build.py --gui    # desktop app in its own window: dist/BallOutGamba(.exe)
                                       # (needs: pip install pywebview)

PyInstaller can't cross-compile, so build on Windows for a .exe, on macOS for a
Mac binary, and so on (the GitHub Actions workflow does this for you).
"""

import argparse
import platform
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def write_icon(path: Path) -> Path:
    """Windows .ico (PNG-compressed entries, Vista+) from the app's own icon."""
    from ballout.web import _png
    sizes = [256, 64, 48, 32, 16]
    images = [_png(s) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = len(header) + 16 * len(sizes)
    entries = b""
    for size, data in zip(sizes, images):
        dim = 0 if size == 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + b"".join(images))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gui", action="store_true", help="build the windowed desktop app")
    args = ap.parse_args()

    name = "BallOutGamba" if args.gui else "ballout"
    entry = "desktop_entry.py" if args.gui else "ballout_entry.py"
    icon = write_icon(ROOT / "build" / "ballout.ico")
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--windowed" if args.gui else "--console",
        "--name", name, "--icon", str(icon),
        "--collect-submodules", "ballout",
        "--hidden-import", "lxml.etree", "--hidden-import", "lxml._elementpath",
        "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "IPython",
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / name), "--specpath", str(ROOT / "build"),
    ]
    if args.gui:
        cmd += ["--collect-all", "webview"]
    cmd.append(str(ROOT / "packaging" / entry))
    subprocess.run(cmd, check=True, cwd=ROOT)
    suffix = ".exe" if platform.system() == "Windows" else (".app" if args.gui and platform.system() == "Darwin" else "")
    exe = ROOT / "dist" / (name + suffix)
    size = exe.stat().st_size if exe.is_file() else sum(f.stat().st_size for f in exe.rglob("*") if f.is_file())
    print(f"\nBuilt {exe} ({size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
