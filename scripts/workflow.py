"""Build and exercise bleMD using the selected Blender executable."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "bleMD.zip"
DEFAULT_BLENDER = "/opt/blender-4.2.2-linux-x64/blender"


def build():
    # Recreate the archive so deleted files and Python caches cannot linger.
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "bleMD").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(ROOT))
    print(f"Built {ARCHIVE}", flush=True)


def background(blender, script, *, env=None, factory=False):
    command = [blender, "--background"]
    if factory:
        command.append("--factory-startup")
    command += ["--python-exit-code", "1", "--python", str(ROOT / "scripts" / script)]
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def test(blender):
    with tempfile.TemporaryDirectory(prefix="blemd-test-") as directory:
        env = os.environ.copy()
        env["BLENDER_USER_RESOURCES"] = directory
        env["BLENDER_USER_CONFIG"] = str(Path(directory) / "config")
        env["BLENDER_USER_SCRIPTS"] = str(Path(directory) / "scripts")
        env["BLENDER_USER_DATAFILES"] = str(Path(directory) / "datafiles")
        # Blender can fall back to the real profile if override directories do
        # not exist. Create every override before launching any Blender process.
        for name in ("BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS", "BLENDER_USER_DATAFILES"):
            Path(env[name]).mkdir(parents=True)
        background(blender, "install.py", env=env, factory=True)
        background(blender, "verify_install.py", env=env)
        # Reinstall with the previous version loaded, then validate the new
        # generation in a fresh process, exactly as the user workflow does.
        background(blender, "install.py", env=env)
        # A fresh process verifies that enablement was actually saved.
        background(blender, "smoke_test.py", env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default=os.environ.get("BLENDER", DEFAULT_BLENDER))
    parser.add_argument("command", choices=["build", "test", "install", "run", "dev", "uninstall"])
    parser.add_argument("--blend", type=Path, help="Scene to open in the Blender UI")
    args = parser.parse_args()
    if args.blend:
        args.blend = args.blend.resolve(strict=True)
    if args.command in {"build", "test", "install", "dev"}:
        build()
    if args.command in {"test", "dev"}:
        test(args.blender)
    if args.command in {"install", "dev"}:
        background(args.blender, "install.py")
        background(args.blender, "verify_install.py")
    if args.command == "uninstall":
        background(args.blender, "uninstall.py")
    if args.command in {"run", "dev"}:
        command = [args.blender]
        if args.blend:
            command.append(str(args.blend))
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
