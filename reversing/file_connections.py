"""Compatibility entry point; the connections project now lives in fileviewer."""
from pathlib import Path
import runpy
import sys

VIEWER = Path(__file__).resolve().parent / "fileviewer"


def main() -> None:
    sys.path.insert(0, str(VIEWER))
    runpy.run_path(str(VIEWER / "file_connections.py"), run_name="__main__")


if __name__ == "__main__":
    main()
