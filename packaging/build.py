"""Build a single-file executable for the current OS: `python packaging/build.py`.

PyInstaller can't cross-compile, so build on Windows for a .exe, on macOS for a
Mac binary, and so on (the GitHub Actions workflow does all three).
"""

import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    name = "ballout"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
        "--name", name,
        "--collect-submodules", "ballout",
        "--hidden-import", "lxml.etree", "--hidden-import", "lxml._elementpath",
        "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "IPython",
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
        str(ROOT / "packaging" / "ballout_entry.py"),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = ROOT / "dist" / (name + (".exe" if platform.system() == "Windows" else ""))
    print(f"\nBuilt {exe} ({exe.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
