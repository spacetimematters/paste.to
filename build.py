"""Build paste.to into a standalone exe using PyInstaller."""
import subprocess
import sys

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "paste-to",
    "--collect-data", "customtkinter",
    "--noconfirm",
    "app_desktop.py",
]

print("Running:", " ".join(cmd))
subprocess.run(cmd, check=True)
print("\nDone! Executable is in dist/paste-to")
