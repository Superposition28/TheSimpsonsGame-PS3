import os
import sys
import argparse
import sqlite3
import hashlib
import time
from typing import Dict, Tuple, Iterable


# --------------------
# CLI and Configuration
# --------------------

# Base folder rename mapping (original -> renamed)
RENAME_MAP = {
    "audiostreams": "Assets_1_Audio_Streams",
    "movies": "Assets_1_Video_Movies",
    "frontend": "Assets_2_Frontend",
    "simpsons_chars": "Assets_2_Characters_Simpsons",
    "spr_hub": "Map_3-00_SprHub",
    "loc": "Map_3-01_LandOfChocolate",
    "brt": "Map_3-02_BartmanBegins",
    "eighty_bites": "Map_3-03_HungryHungryHomer",
    "tree_hugger": "Map_3-04_TreeHugger",
    "mob_rules": "Map_3-05_MobRules",
    "cheater": "Map_3-06_EnterTheCheatrix",
    "dayofthedolphins": "Map_3-07_DayOfTheDolphin",
    "colossaldonut": "Map_3-08_TheColossalDonut",
    "dayspringfieldstoodstill": "Map_3-09_Invasion",
    "bargainbin": "Map_3-10_BargainBin",
    "gamehub": "Map_3-00_GameHub",
    "neverquest": "Map_3-11_NeverQuest",
    "grand_theft_scratchy": "Map_3-12_GrandTheftScratchy",
    "medal_of_homer": "Map_3-13_MedalOfHomer",
    "bigsuperhappy": "Map_3-14_BigSuperHappy",
    "rhymes": "Map_3-15_Rhymes",
    "meetthyplayer": "Map_3-16_MeetThyPlayer",
}

ORIGINAL_BASES = list(RENAME_MAP.keys())
RENAMED_BASES = list(RENAME_MAP.values())


def parse_args():
    parser = argparse.ArgumentParser(
        description="New Simpsons Game File Indexer (relationships + file catalogs)"
    )

    parser.add_argument(
        '--input-dir',
        default=r"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\Source\\USRDIR",
        help='Custom input directory for source files'
    )

    parser.add_argument(
        '--output-dir',
        default=r"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\GameFiles\\STROUT",
        help='Custom output directory for extracted files'
    )

    # Detailed selection flags
    parser.add_argument(
        '--region', choices=['EU', 'US'], required=True,
        help="Region selector ('EU' or 'US')"
    )

    parser.add_argument(
        '--Type', dest='index_type', choices=['Full', 'FullFlattened', 'SourceOnly'], required=True,
        help="Index Type: 'Full'|'FullFlattened'|'SourceOnly'"
    )

    parser.add_argument(
        '--renamedBaseDirs', dest='renamed_base_dirs', choices=['isRenamed', 'notRenamed'], required=True,
        help="Whether base dirs were renamed: 'isRenamed'|'notRenamed'"
    )

    parser.add_argument(
        '--AudioReorg', dest='audio_reorg', choices=['audio_reorg', 'audio_og'], required=True,
        help="Audio reorg status: 'audio_reorg'|'audio_og'"
    )

    parser.add_argument( ## changed logic of extraction tools, so the blend files are actually being placed in the STROUT folder instead of TEMP_BLEND for easier access
        '--blend-dir', dest='blend_dir', default=r"A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT",
        help='Optional TEMP_BLEND directory (mirror layout of STROUT for .blend)'
    )

    return parser.parse_args()


# --------------------
# Utility helpers
# --------------------

def norm_rel(path: str) -> str:
    return path.replace('\\', '/').lstrip('/')


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def md5_string(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def make_uuid(file_hash: str, rel_path: str) -> str:
    ph = file_hash[:16]
    rh = md5_string(rel_path)[:16]
    return f"{ph}_{rh}"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def discover_blend_dir(output_dir: str, provided: str | None) -> str:
    if provided:
        return provided
    candidate = os.path.normpath(os.path.join(os.path.dirname(output_dir), 'TEMP_BLEND'))
    return candidate


def get_base_names(selected_renamed: str) -> Iterable[str]:
    return RENAMED_BASES if selected_renamed == 'isRenamed' else ORIGINAL_BASES


def validate_base_folders(root_dir: str, expected_bases: Iterable[str], label: str):
    missing = []
    for base in expected_bases:
        sub = os.path.join(root_dir, base)
        if not os.path.isdir(sub):
            missing.append(sub)
    if missing:
        lines = "\n  ".join(missing)
        raise RuntimeError(f"Missing required base folders in {label}:\n  {lines}")


# --------------------
# SQLite schema helpers
# --------------------

EXT_TO_TABLE = {
    '.str': 'str_index',
    '.preinstanced': 'preinstanced_index',
    '.blend': 'blend_index',
    '.glb': 'glb_index',
    '.txd': 'txd_index',
    '.vp6': 'video_index',
    '.ogv': 'video_ogv_index',
    '.snu': 'snu_index',
    '.wav': 'audio_wav_index',
    '.mus': 'mus_index',
    '.dds': 'dds_index',
    '.png': 'png_index',
}


GENERIC_TABLES = set(EXT_TO_TABLE.values()) | {"other_files_index"}


def init_schema(conn: sqlite3.Connection):
    cur = conn.cursor()

    # Generic file tables
    for table in GENERIC_TABLES:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                source_file_name TEXT,
                source_path TEXT UNIQUE NOT NULL,
                file_hash TEXT,
                path_hash TEXT,
                group_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute(f"""
            CREATE TRIGGER IF NOT EXISTS update_{table}_last_updated
            AFTER UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table} SET last_updated = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        """)

    # Relationships
    cur.execute("""
        CREATE TABLE IF NOT EXISTS str_content_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            str_uuid TEXT NOT NULL,
            content_file_uuid TEXT NOT NULL,
            content_file_table TEXT NOT NULL,
            UNIQUE (str_uuid, content_file_uuid, content_file_table)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS txd_dds_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txd_uuid TEXT NOT NULL,
            dds_uuid TEXT NOT NULL,
            UNIQUE (txd_uuid, dds_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dds_png_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dds_uuid TEXT NOT NULL,
            png_uuid TEXT NOT NULL,
            UNIQUE (dds_uuid, png_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS preinstanced_blend_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preinstanced_uuid TEXT NOT NULL,
            blend_uuid TEXT NOT NULL,
            UNIQUE (preinstanced_uuid, blend_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS glb_blend_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            glb_uuid TEXT NOT NULL,
            blend_uuid TEXT NOT NULL,
            UNIQUE (glb_uuid, blend_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS preinstanced_blend_glb_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preinstanced_uuid TEXT NOT NULL,
            blend_uuid TEXT NOT NULL,
            glb_uuid TEXT NOT NULL,
            UNIQUE (preinstanced_uuid, blend_uuid, glb_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS snu_wav_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snu_uuid TEXT NOT NULL,
            wav_uuid TEXT NOT NULL,
            UNIQUE (snu_uuid, wav_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vp6_ogv_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vp6_uuid TEXT NOT NULL,
            ogv_uuid TEXT NOT NULL,
            UNIQUE (vp6_uuid, ogv_uuid)
        )
    """)

    conn.commit()


def table_for_ext(ext: str) -> str:
    return EXT_TO_TABLE.get(ext.lower(), 'other_files_index')


def upsert_file(conn: sqlite3.Connection, table: str, full_path: str, rel_path: str, group_name: str) -> str:
    file_hash = sha256_file(full_path)
    path_hash = md5_string(rel_path)
    uuid = make_uuid(file_hash, rel_path)

    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT OR IGNORE INTO {table} (uuid, source_file_name, source_path, file_hash, path_hash, group_name)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (uuid, os.path.basename(full_path), rel_path, file_hash, path_hash, group_name)
    )
    if cur.rowcount == 0:
        # Ensure we can retrieve UUID of existing row (by source_path)
        cur.execute(f"SELECT uuid FROM {table} WHERE source_path = ?", (rel_path,))
        row = cur.fetchone()
        if row:
            uuid = row[0]
    conn.commit()
    return uuid


# --------------------
# Indexing passes
# --------------------

class IndexState:
    def __init__(self):
        # per-extension map: rel_path -> uuid
        self.by_ext: Dict[str, Dict[str, str]] = {}

    def add(self, ext: str, rel_path: str, uuid: str):
        ext = ext.lower()
        if ext not in self.by_ext:
            self.by_ext[ext] = {}
        self.by_ext[ext][rel_path] = uuid

    def get(self, ext: str, rel_path: str) -> str | None:
        ext = ext.lower()
        return self.by_ext.get(ext, {}).get(rel_path)


def walk_files(base_dir: str, allow_exts: set[str] | None = None) -> Iterable[Tuple[str, str, str]]:
    for root, _, files in os.walk(base_dir):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if allow_exts is not None and ext not in allow_exts:
                continue
            full = os.path.join(root, fn)
            rel = norm_rel(os.path.relpath(full, base_dir))
            yield full, rel, ext


def index_root_dir(conn: sqlite3.Connection, base_dir: str, ext_filter: set[str] | None, state: IndexState):
    for full, rel, ext in walk_files(base_dir, ext_filter):
        tbl = table_for_ext(ext)
        grp = ext  # simple grouping by extension string
        try:
            uuid = upsert_file(conn, tbl, full, rel, grp)
            state.add(ext, rel, uuid)
        except Exception as e:
            print(f"ERROR indexing {full}: {e}", file=sys.stderr)


def relate_str_contents(conn: sqlite3.Connection, input_dir: str, output_dir: str, state: IndexState):
    cur = conn.cursor()
    str_map = state.by_ext.get('.str', {})
    for rel_str_path, str_uuid in str_map.items():
        rel_no_ext = rel_str_path[:-4] if rel_str_path.lower().endswith('.str') else rel_str_path
        extraction_rel_dir = f"{rel_no_ext}_str"
        extraction_abs_dir = os.path.join(output_dir, extraction_rel_dir)
        if not os.path.isdir(extraction_abs_dir):
            # It's valid for some STRs not to be extracted yet
            continue
        for root, _, files in os.walk(extraction_abs_dir):
            for fn in files:
                fext = os.path.splitext(fn)[1].lower()
                full = os.path.join(root, fn)
                rel = norm_rel(os.path.relpath(full, output_dir))
                content_tbl = table_for_ext(fext)
                content_uuid = state.get(fext, rel)
                if content_uuid is None:
                    # If not indexed yet (e.g., filtered), index on-the-fly
                    try:
                        content_uuid = upsert_file(conn, content_tbl, full, rel, fext)
                        state.add(fext, rel, content_uuid)
                    except Exception as e:
                        print(f"WARN: could not index STR content {full}: {e}", file=sys.stderr)
                        continue
                try:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO str_content_relationship (str_uuid, content_file_uuid, content_file_table)
                        VALUES (?, ?, ?)
                        """,
                        (str_uuid, content_uuid, content_tbl)
                    )
                except Exception as e:
                    print(f"WARN: relation STR->content failed for {rel} : {e}", file=sys.stderr)
    conn.commit()


def relate_txd_dds(conn: sqlite3.Connection, roots: Iterable[str], state: IndexState):
    cur = conn.cursor()
    # Build a quick lookup of dds rel paths
    for base in roots:
        for full, rel, ext in walk_files(base, {'.txd'}):
            parent_dir = os.path.dirname(full)
            base_no_ext = os.path.splitext(os.path.basename(full))[0]
            dds_dir = os.path.join(parent_dir, base_no_ext + "_txd")
            txd_uuid = state.get('.txd', rel)
            if txd_uuid is None:
                try:
                    txd_uuid = upsert_file(conn, table_for_ext('.txd'), full, rel, '.txd')
                    state.add('.txd', rel, txd_uuid)
                except Exception as e:
                    print(f"WARN: could not index TXD {full} for relationships: {e}", file=sys.stderr)
                    continue
            if not os.path.isdir(dds_dir):
                continue
            for droot, _, files in os.walk(dds_dir):
                for fn in files:
                    if not fn.lower().endswith('.dds'):
                        continue
                    dfull = os.path.join(droot, fn)
                    drel = norm_rel(os.path.relpath(dfull, base))
                    d_uuid = state.get('.dds', drel)
                    if d_uuid is None:
                        try:
                            d_uuid = upsert_file(conn, table_for_ext('.dds'), dfull, drel, '.dds')
                            state.add('.dds', drel, d_uuid)
                        except Exception as e:
                            print(f"WARN: could not index DDS {dfull}: {e}", file=sys.stderr)
                            continue
                    try:
                        cur.execute(
                            "INSERT OR IGNORE INTO txd_dds_relationship (txd_uuid, dds_uuid) VALUES (?, ?)",
                            (txd_uuid, d_uuid)
                        )
                    except Exception as e:
                        print(f"WARN: TXD-DDS relation failed for {rel} -> {drel}: {e}", file=sys.stderr)
    conn.commit()


def relate_ext_swap(conn: sqlite3.Connection, state: IndexState, from_ext: str, to_ext: str,
                    table_rel: str, from_col: str, to_col: str):
    cur = conn.cursor()
    src_map = dict(state.by_ext.get(from_ext, {}))
    dst_map = dict(state.by_ext.get(to_ext, {}))
    for rel_from, uuid_from in src_map.items():
        if not rel_from.lower().endswith(from_ext):
            continue
        rel_to = rel_from[:-len(from_ext)] + to_ext
        uuid_to = dst_map.get(rel_to)
        if not uuid_to:
            continue
        try:
            cur.execute(
                f"INSERT OR IGNORE INTO {table_rel} ({from_col}, {to_col}) VALUES (?, ?)",
                (uuid_from, uuid_to)
            )
        except Exception as e:
            print(f"WARN: relation {from_ext}->{to_ext} failed for {rel_from}: {e}", file=sys.stderr)
    conn.commit()


def relate_models_chain(conn: sqlite3.Connection, state: IndexState):
    cur = conn.cursor()
    pre_map = dict(state.by_ext.get('.preinstanced', {}))
    blend_map = dict(state.by_ext.get('.blend', {}))
    glb_map = dict(state.by_ext.get('.glb', {}))

    for rel_pre, uuid_pre in pre_map.items():
        if not rel_pre.lower().endswith('.preinstanced'):
            continue
        rel_common = rel_pre[:-len('.preinstanced')]
        rel_blend = rel_common + '.blend'
        rel_glb = rel_common + '.glb'
        uuid_blend = blend_map.get(rel_blend)
        uuid_glb = glb_map.get(rel_glb)
        if uuid_blend:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO preinstanced_blend_relationship (preinstanced_uuid, blend_uuid) VALUES (?, ?)",
                    (uuid_pre, uuid_blend)
                )
            except Exception as e:
                print(f"WARN: preinstanced->blend relation failed for {rel_pre}: {e}", file=sys.stderr)
        if uuid_glb and uuid_blend:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO glb_blend_relationship (glb_uuid, blend_uuid) VALUES (?, ?)",
                    (uuid_glb, uuid_blend)
                )
                cur.execute(
                    "INSERT OR IGNORE INTO preinstanced_blend_glb_relationship (preinstanced_uuid, blend_uuid, glb_uuid) VALUES (?, ?, ?)",
                    (uuid_pre, uuid_blend, uuid_glb)
                )
            except Exception as e:
                print(f"WARN: model chain relation failed for {rel_pre}: {e}", file=sys.stderr)
    conn.commit()


# --------------------
# Main
# --------------------

def main():
    args = parse_args()

    selected_region = args.region
    selected_type = args.index_type
    selected_renamed = args.renamed_base_dirs
    selected_audio = args.audio_reorg

    input_dir = args.input_dir
    output_dir = args.output_dir
    blend_dir = discover_blend_dir(output_dir, args.blend_dir)

    # Validate base folder names exist in Source, STROUT, TEMP_BLEND
    expected_bases = list(get_base_names(selected_renamed))
    try:
        validate_base_folders(input_dir, expected_bases, 'Source (input-dir)')
        validate_base_folders(output_dir, expected_bases, 'STROUT (output-dir)')
        validate_base_folders(blend_dir, expected_bases, 'TEMP_BLEND (blend-dir)')
    except RuntimeError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)

    # Compute DB path by pattern
    dbpath = rf"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\config\\GameFilesIndex_{selected_region}_{selected_type}-{selected_audio}-{selected_renamed}.db"

    # Ensure DB directory exists
    ensure_dir(os.path.dirname(dbpath))

    # Open DB and create schema
    conn = sqlite3.connect(dbpath)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    init_schema(conn)

    state = IndexState()

    # Select scanning strategy by Type
    # - SourceOnly: only index input_dir
    # - Full/FullFlattened: index input_dir, output_dir, and blend_dir
    try:
        if selected_type == 'SourceOnly':
            index_root_dir(conn, input_dir, None, state)
        else:
            index_root_dir(conn, input_dir, None, state)
            index_root_dir(conn, output_dir, None, state)
            # Blend dir may not exist for all projects; skip if missing
            if os.path.isdir(blend_dir):
                index_root_dir(conn, blend_dir, {'.blend'}, state)

        # Relationships
        if selected_type != 'SourceOnly':
            relate_str_contents(conn, input_dir, output_dir, state)

            # TXD -> DDS from both roots
            relate_txd_dds(conn, [input_dir, output_dir], state)

            # SNU -> WAV (by same rel path and extension swap) across input->output
            relate_ext_swap(conn, state, '.snu', '.wav', 'snu_wav_relationship', 'snu_uuid', 'wav_uuid')

            # VP6 -> OGV across input->output
            relate_ext_swap(conn, state, '.vp6', '.ogv', 'vp6_ogv_relationship', 'vp6_uuid', 'ogv_uuid')

            # DDS -> PNG within output
            relate_ext_swap(conn, state, '.dds', '.png', 'dds_png_relationship', 'dds_uuid', 'png_uuid')

            # Model relationships using STROUT (.preinstanced, .glb) and TEMP_BLEND (.blend)
            relate_models_chain(conn, state)

        print(f"Index complete. SQLite written to: {dbpath}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

