import os
import sys
import argparse
import sqlite3
import hashlib
import json
import glob
from typing import Dict, Iterable, Optional, List, Tuple
import re


# --------------------
# Index-Index: Cross-DB relationship generator
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="The Simpsons Game Index-Index: generate cross-DB relationship JSON files"
    )
    parser.add_argument(
        '--config-dir', dest='config_dir', default=r"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\config",
        help='Directory containing GameFilesIndex_*.db files'
    )
    parser.add_argument(
        '--output-json-dir', dest='output_json_dir', default="A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\config\\index-index",
        help='Directory for JSON files (default: <config-dir>/index-index)'
    )
    return parser.parse_args()


def norm_rel(path: str) -> str:
    return path.replace('\\', '/').lstrip('/')


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


# --------------------
# Relationship tables to export
# --------------------

REL_TABLES = [
    'audio_wav_index',
    'blend_index',
    'dds_index',
    'glb_index',
    'mus_index',
    'other_files_index',
    'png_index',
    'preinstanced_index',
    'snu_index',
    'str_index',
    'txd_index',
    'video_index',
    'video_ogv_index',
]


# --------------------
# Canonicalization + mapping
# --------------------

def canonicalize_base(path: str) -> str:
    """Canonicalize base folders so renamed/non-renamed roots match across DBs.

    - If first segment is a renamed base and second is the corresponding original base, drop the renamed.
    - Else if first segment is a renamed base but second isn't the original, replace first with original base.
    - Collapse duplicated leading base folder (e.g., 'loc/loc/...') to a single base segment.
    """
    p = norm_rel(path or '')
    if not p:
        return p
    parts = p.split('/')
    if not parts:
        return p

    ren_to_orig = {v: k for k, v in RENAME_MAP.items()}

    first = parts[0]
    if first in ren_to_orig:
        original = ren_to_orig[first]
        if len(parts) > 1 and parts[1] == original:
            parts = parts[1:]
        else:
            parts[0] = original
        p = '/'.join(parts)
        parts = p.split('/')

    # Collapse duplicated leading base folder
    if len(parts) > 1 and parts[0] == parts[1] and parts[0] in ORIGINAL_BASES:
        parts = parts[1:]

    return '/'.join(parts)


def _canonicalize_media_segments(parts: List[str], media_root: str, target_root: str) -> List[str]:
    """For media roots that include a language subfolder in reorg (e.g., Assets_1_Audio_Streams/EN/...),
    drop the language folder and map the root back to original (e.g., audiostreams).
    """
    if not parts:
        return parts
    if parts[0] != media_root:
        return parts
    # Replace root with original
    parts[0] = target_root
    # Drop language folder if present (2-5 letters/underscores)
    if len(parts) > 1 and re.fullmatch(r"[A-Za-z_]{2,5}", parts[1] or ""):
        parts = [parts[0]] + parts[2:]
    return parts


def canonicalize_path_for_table(table: str, path: str) -> str:
    # Base canonicalization (rename-map + duplicate base collapse)
    base = canonicalize_base(path)
    parts = base.split('/') if base else []

    # Media-specific normalization
    if table in {'audio_wav_index', 'mus_index'}:
        parts = _canonicalize_media_segments(parts, 'Assets_1_Audio_Streams', 'audiostreams')
    if table in {'video_index', 'video_ogv_index'}:
        parts = _canonicalize_media_segments(parts, 'Assets_1_Video_Movies', 'movies')

    return '/'.join([p for p in parts if p])


def choose_canonical_path(table: str, row: sqlite3.Row) -> Optional[str]:
    """Pick a canonical path from a DB row, preferring original_path when present."""
    try:
        has_original = 'original_path' in row.keys()
        has_source = 'source_path' in row.keys()
        has_sfn = 'source_file_name' in row.keys()
    except Exception:
        has_original = has_source = has_sfn = False

    chosen = None
    if has_original and row['original_path']:
        chosen = row['original_path']
    elif has_source and row['source_path']:
        chosen = row['source_path']
    elif has_sfn and row['source_file_name']:
        chosen = row['source_file_name']

    if not chosen:
        return None
    return canonicalize_path_for_table(table, chosen)


def compute_global_uuid(table: str, canonical_path: str) -> str:
    """Stable, content-agnostic UUID per table based on path."""
    payload = f"{table}::{canonical_path}"
    return hashlib.md5(payload.encode('utf-8')).hexdigest()


def list_sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in cur.fetchall()}


def read_table_rows(db_path: str, table: str) -> Iterable[sqlite3.Row]:
    # Open in read-only mode (avoid WAL/SHM writes)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        available = list_sqlite_tables(conn)
        if table not in available:
            return []
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        for row in cur.fetchall():
            yield row
    finally:
        conn.close()


def build_index_index(config_dir: str, output_dir: str, collapsed: bool = False):
    """Build per-table JSON mapping global_uuid -> ids-by-db.

    Output schema per table (e.g., glb_index.json):
    {
      "<global_uuid>": {
        "canonical_path": "loc/.../file.glb",
        "ids_by_db": {
          "GameFilesIndex_EU_Full-audio_og-isRenamed.db": 1629,
          "GameFilesIndex_EU_Full-audio_og-notRenamed.db": 2270
        }
      }
    }
    """
    ensure_dir(output_dir)

    # Discover DB files
    pattern = os.path.join(config_dir, 'GameFilesIndex_*.db')
    db_files = sorted(glob.glob(pattern))
    if not db_files:
        raise RuntimeError(f"No DB files found in {config_dir} with pattern GameFilesIndex_*.db")

    print(f"Discovered {len(db_files)} DBs for index-index:")
    for dbf in db_files:
        print(f" - {os.path.basename(dbf)}")

    # Per-table JSON mapping
    per_table: Dict[str, Dict[str, Dict[str, object]]] = {}

    # Iterate per table: load all rows across DBs, then cluster with multi-signal matching
    for table in REL_TABLES:
        # Collect entries across DBs
        entries: List[Dict[str, object]] = []
        for db_path in db_files:
            db_name = os.path.basename(db_path)
            for row in read_table_rows(db_path, table):
                # Row basics
                try:
                    row_id = int(row['id']) if 'id' in row.keys() else None
                except Exception:
                    row_id = None
                if row_id is None:
                    continue
                try:
                    row_uuid = row['uuid'] if 'uuid' in row.keys() else None
                except Exception:
                    row_uuid = None
                try:
                    fh = row['file_hash'] if 'file_hash' in row.keys() else None
                except Exception:
                    fh = None
                try:
                    sfn = row['source_file_name'] if 'source_file_name' in row.keys() else None
                except Exception:
                    sfn = None
                cp = choose_canonical_path(table, row)
                entries.append({
                    'db': db_name,
                    'id': row_id,
                    'uuid': row_uuid,
                    'file_hash': fh,
                    'name': sfn,
                    'cp': cp,
                })

        # Build indices for matching
        idx_by_fh: Dict[str, List[int]] = {}
        idx_by_cp: Dict[str, List[int]] = {}
        idx_by_uuid: Dict[str, List[int]] = {}
        idx_by_fh_name: Dict[Tuple[str, str], List[int]] = {}

        for i, e in enumerate(entries):
            fh = e.get('file_hash') or ''
            cp = e.get('cp') or ''
            uu = e.get('uuid') or ''
            nm = e.get('name') or ''
            if fh:
                idx_by_fh.setdefault(fh, []).append(i)
                if nm:
                    idx_by_fh_name.setdefault((fh, nm), []).append(i)
            if cp:
                idx_by_cp.setdefault(cp, []).append(i)
            if uu:
                idx_by_uuid.setdefault(uu, []).append(i)

        # Union-Find helpers
        parent = list(range(len(entries)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int):
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            parent[rb] = ra

        # Helper to union across DBs only
        def cross_db_union(indices: List[int]):
            by_db: Dict[str, int] = {}
            for i in indices:
                db = entries[i]['db']
                if db in by_db:
                    continue
                by_db[db] = i
            # Union first with all others (one per DB)
            pivots = list(by_db.values())
            for i in range(1, len(pivots)):
                union(pivots[0], pivots[i])

        # 1) Strong match for audio/video by file hash (expected unique per DB)
        if table in {'audio_wav_index', 'mus_index', 'video_index', 'video_ogv_index'}:
            for fh, lst in idx_by_fh.items():
                if len(lst) < 2:
                    continue
                cross_db_union(lst)

        # 2) Path equality across DBs (after canonicalization)
        for cp, lst in idx_by_cp.items():
            if len(lst) < 2:
                continue
            cross_db_union(lst)

        # 3) UUID equality (rare across DBs, but safe if present)
        for uu, lst in idx_by_uuid.items():
            if len(lst) < 2:
                continue
            cross_db_union(lst)

        # 4) For non-audio/video where duplicates share file hashes, add guard: file_hash + name
        if table not in {'audio_wav_index', 'mus_index', 'video_index', 'video_ogv_index'}:
            for key, lst in idx_by_fh_name.items():
                if len(lst) < 2:
                    continue
                cross_db_union(lst)

        # Build clusters
        clusters: Dict[int, List[int]] = {}
        for i in range(len(entries)):
            r = find(i)
            clusters.setdefault(r, []).append(i)

        # Emit mapping with one row per DB per cluster
        out_map: Dict[str, Dict[str, object]] = {}
        for indices in clusters.values():
            # Build ids_by_db (prefer exactly one per DB)
            ids_by_db: Dict[str, int] = {}
            candidate_cps: List[str] = []
            for i in indices:
                e = entries[i]
                db = e['db']
                # Keep first occurrence per DB
                if db not in ids_by_db:
                    ids_by_db[db] = int(e['id'])
                if e.get('cp'):
                    candidate_cps.append(str(e['cp']))
            # Representative canonical path
            canonical_path = min(candidate_cps) if candidate_cps else ''
            # Stable global uuid key
            key_basis = canonical_path if canonical_path else (entries[indices[0]].get('file_hash') or entries[indices[0]].get('uuid') or entries[indices[0]].get('name') or str(indices[0]))
            global_uuid = compute_global_uuid(table, str(key_basis))
            out_map[global_uuid] = {
                'canonical_path': canonical_path,
                'ids_by_db': ids_by_db,
            }

        per_table[table] = out_map

    # Write JSON files per table with inline ids_by_db
    for table, mapping in per_table.items():
        out_path = os.path.join(output_dir, f"{table}.json")
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                if collapsed:
                    # Compact output on a single line
                    json.dump(mapping, f, ensure_ascii=False, separators=(',', ':'))
                else:
                    # Expanded object with collapsed entries (one entry per line)
                    f.write('{\n')
                    items = list(mapping.items())
                    for idx, (gkey, data) in enumerate(sorted(items, key=lambda kv: kv[0])):
                        cp = data.get('canonical_path', '') if isinstance(data, dict) else ''
                        ids = data.get('ids_by_db', {}) if isinstance(data, dict) else {}
                        # Entire entry on one line
                        entry = {
                            'canonical_path': cp,
                            'ids_by_db': dict(sorted(ids.items()))
                        }
                        entry_json = json.dumps(entry, ensure_ascii=False, separators=(',', ': '))
                        comma = ',' if idx < len(items) - 1 else ''
                        f.write(f'  {json.dumps(gkey, ensure_ascii=False)}: {entry_json}{comma}\n')
                    f.write('}\n')
            print(f"Wrote {out_path} ({len(mapping)} entries)")
        except Exception as e:
            print(f"ERROR writing {out_path}: {e}", file=sys.stderr)


def main():
    args = parse_args()
    config_dir = args.config_dir
    output_json_dir = args.output_json_dir or os.path.join(config_dir, 'index-index')

    try:
        build_index_index(config_dir, output_json_dir, collapsed=False)
    except Exception as e:
        print(f"FATAL (index-index): {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == '__main__':
    main()
