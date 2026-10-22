"""Run Godot with sandbox-local caches/logs. Pass any Godot CLI arguments after --.

Example: python -B tools/run_godot.py -- --headless --editor --import
No system settings or installed Godot files are changed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', type=Path)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    candidates = [args.godot] if args.godot else [
        Path('b:/Installed_Apps/Program_Files_x86/Steam/steamapps/common/Godot Engine/godot.windows.opt.tools.64.exe'),
        Path('A:/RemakeEngine/Main/EngineApps/Tools/Godot-4.6-stable-win-x64/Godot_v4.6-stable_win64_console.exe'),
    ]
    executable = next((path for path in candidates if path is not None and path.is_file()), None)
    if executable is None:
        raise SystemExit('Godot executable not found. Supply --godot <path>.')
    output = project / 'test-output'
    output.mkdir(exist_ok=True)
    environment = os.environ.copy()
    for variable, directory in [('APPDATA', 'roaming'), ('LOCALAPPDATA', 'local')]:
        path = output / 'profile' / directory
        path.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(path)
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    command = [str(executable), '--path', str(project), '--log-file', str(output / 'godot.log'), *arguments]
    raise SystemExit(subprocess.run(command, env=environment).returncode)


if __name__ == '__main__':
    main()
