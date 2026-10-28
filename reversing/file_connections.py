"""Build and display the original/extracted game file connection graph (stdlib only).

python -B reversing/file_connections.py --build-only
python -B reversing/file_connections.py --open
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from connection_explorer.index import Builder, MODULE, Explorer
from connection_explorer.server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=MODULE / "Source/PS3/EU/1/PS3_GAME/USRDIR")
    parser.add_argument("--extracted", action="append", type=Path, help="Extracted dataset root; repeat for multiple output trees")
    parser.add_argument("--database", type=Path, default=MODULE / "GameFiles/file-connections/index.sqlite")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--open", action="store_true", help="Open the loopback UI in the default browser")
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--max-parse-mb", type=int, default=32, help="Per-payload structural parse limit; larger files remain raw-inspectable")
    args = parser.parse_args()
    source, database = args.source.resolve(), args.database.resolve()
    default_roots = [MODULE / "GameFiles/PS3-EU-Full-audio_reorg-isRenamed", MODULE / "GameFiles/PS3-EU-FullFlattened-audio_reorg-isRenamed"]
    extracted = [p.resolve() for p in (args.extracted if args.extracted is not None else default_roots) if p.is_dir()]
    if not source.is_dir():
        parser.error(f"original source root not found: {source}")
    if not database.is_relative_to((MODULE / "GameFiles").resolve()):
        parser.error("database and generated data must be beneath this module's GameFiles directory")
    if any(database.is_relative_to(p) for p in [source, *extracted]):
        parser.error("database must be outside input trees")
    if source in extracted or any(p.is_relative_to(source) or source.is_relative_to(p) for p in extracted):
        parser.error("source and extracted input trees must be separate")
    if not 1 <= args.max_parse_mb <= 256:
        parser.error("--max-parse-mb must be 1..256")
    if not 0 <= args.port <= 65535:
        parser.error("invalid loopback port")
    if args.rebuild or args.build_only or not database.exists():
        database.parent.mkdir(parents=True, exist_ok=True)
        temporary = database.with_name(database.name + f".building-{os.getpid()}")
        if temporary.exists():
            parser.error(f"unfinished build exists: {temporary}")
        builder = Builder(temporary, source, extracted, args.max_parse_mb * 1024 * 1024)
        try:
            summary = builder.build()
        except BaseException:
            builder.db.close()
            raise
        os.replace(temporary, database)
        (database.parent / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)
    if not args.build_only:
        serve(database, args.port, args.open)


if __name__ == "__main__":
    main()
