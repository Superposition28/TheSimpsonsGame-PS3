import os
import re
import json
import hashlib
import base64
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple, List, Dict

def sanitize_filename(name: str) -> str:
    """Make a safe filename segment from a folder name (Windows-friendly)."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name).strip()


def write_json(path: Path, rows) -> None:
    """Pretty-print JSON with UTF-8 and stable key order."""
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2, sort_keys=False)

"""
Why this script exists
----------------------
The original asset archive encodes *meaning* (character, zone, category, purpose, LOD index, etc.)
in deep, noisy directory paths and generic filenames. That makes the same logical asset appear at
many different physical paths. This script "flattens" each asset to a concise, deterministic path
and filename **without losing information**, while keeping assets in their original map/asset base
folders. It also keeps zone folders when applicable.

Key design goals (for the eventual C# rewrite as well):
- Preserve base folders (e.g., 'Map_3-02_BartmanBegins', 'Assets_2_Characters_Simpsons').
- Preserve zone folder if present (e.g., 'zone04_str').
- Extract stable tokens from the original path/filename:
  * category      (e.g., 'chars', 'weapons', 'props', ...)
  * purpose       (e.g., 'lod', 'geo', 'opt', 'bound', ...)
  * owner/variant (character/costume family or variant slug)
    * asset         (leaf asset identifier near 'assets/<category>/<asset>' or 'export')
    * index         (e.g., 'lod2' -> 2, 'opt_model7' -> 7) even when the folder purpose is something else
- Avoid redundant owner/asset tokens in filenames when they collapse to the same slug.
- Construct a new path like:
    <Base>[\\zoneNN_str][\\...normalized character folders...]\\<category>\\<purpose>\\<filename>
  and a readable filename:
    <owner_or_variant>_<asset>_<purpose>[_<index>]__K<key><ext>
  where <key> is a short Base32 of SHA1(original relative path) that guarantees uniqueness
  and allows exact reverse mapping.
- Emit a JSON map recording original->new paths and all extracted metadata for auditing and reversibility.
- Be conservative and Windows-friendly (Pathlib, no fancy dependencies), with a DRY_RUN preview.

What "flattening up a directory" means here
-------------------------------------------
Character trees can have many variant-named folders like 'marge_mm2_h2_str'. We normalize those so
each character has a single root folder 'marge_str', and variant parts (e.g., 'mm2_h2') become a
subfolder under that character:
    ...\\chars\\marge_mm2_h2_str\\...  ->  ...\\chars\\marge_str\\mm2_h2\\...
The filename owner token also drops the character name (uses just the variant slug).

Reversibility guarantee
-----------------------
Each new filename embeds a short "__K<key>" where 'key' = Base32(SHA1(original_rel_path))[:10].
Combined with the JSON map, we can uniquely map back to the original full path.

C# rewrite notes
----------------
- Use System.IO for traversal; Path.Combine for rebuilding paths.
- For hashing: System.Security.Cryptography.SHA1 (or SHA256) + Base32 (custom) or Base64 + trimming.
- Regex: System.Text.RegularExpressions with compiled Regex options (RegexOptions.IgnoreCase).
- JSON: System.Text.Json for the mapping file (records list).
- Ensure the same normalization steps and token priorities; unit test with fixtures to keep parity.

Caveats
-------
- The script intentionally ignores files that aren’t *.rws.*/*.dff.* with '.preinstanced' tail.
- If you later broaden the file types, update the filters accordingly.
- Collisions are extremely unlikely due to embedded key; still, rename with a suffix if the target exists.
"""

# === CONFIG ===
# Point this to the "ps3\\rws" or dff folder you showed (the parent of your base folders)
ROOT = r".\GameFiles\STROUT"

# Non-destructive output root (files are COPIED here with flattened names/paths)
# Defaults to a sibling of ROOT named "flattened_out".
OUTPUT_ROOT = str((Path(ROOT).parent / "STROUT-Flat").resolve())

DRY_RUN: bool = False  # set to False to actually copy files

# === NAME CONFIG ===
# Options:
#   "flattened" -> <owner>_<asset>_<purpose>[_<index>]__K<key><ext>
#   "key_only"  -> <key><ext>                 (dir path still encodes category/purpose/owner)
#   "template"  -> Use FILENAME_TEMPLATE below
FILENAME_MODE = "flattened"   # "flattened" | "key_only" | "template"

# Placeholders you can use in the template:
#   {owner} {asset} {purpose} {index} {key} {ext}
# Special helper:
#   {_index}  -> becomes "_<index>" if index exists, otherwise ""
# Example keeps your current style:
FILENAME_TEMPLATE = "{owner}_{asset}_{purpose}{_index}__K{key}{ext}"

# Strip trailing "_str" from ANY token used in output paths & filenames (zones, chars, owners, assets)
STRIP_STR_SUFFIX: bool = True

# Known base folders that must be preserved (add more if needed).
# Rationale: We never move files across these "root identities". That preserves high-level organization.
BASE_FOLDER_PREFIXES: List[str] = [
    "Assets_",
    "Map_",  # all map folders are Map_3-xx_*
]

# Known tokens
# CATEGORIES are high-level asset groups we want reflected in the flattened path.
CATEGORIES: List[str] = ["environs", "props", "chars", "weapons", "characters", "fx", "ui", "audio"]
# PURPOSE_TOKENS are pipeline/usage indicators and often appear as folders or in filenames.
PURPOSE_TOKENS: List[str] = ["geo", "opt", "lod", "bound", "rig", "tex", "mat", "proxy", "anim", "terrain"]

# Patterns for detecting purpose/index from filename stems.
# These are intentionally small and conservative; extend as new patterns are discovered.
FILENAME_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^lod[_\- ]?(\d+)", re.I), "lod"),
    (re.compile(r"^lod(\d+)[_\- ]?model$", re.I), "lod"),
    (re.compile(r"^opt[_\- ]?model(\d+)$", re.I), "opt"),
    (re.compile(r"^(.*)_geo$", re.I), "geo"),  # e.g., 'saxophone_GEO'
    (re.compile(r"^terrain", re.I), "terrain"),
]

# Character folder normalization:
#   'marge_mm2_h2_str' -> (char='marge', variant='mm2_h2') -> folders 'marge_str' / 'mm2_h2'
#   'marge_str' -> already canonical, variant=''
CHAR_FOLDER_RX = re.compile(r"^([a-z]+)_(.+)_str$", re.I)
CHAR_BASE_RX   = re.compile(r"^([a-z]+)_str$", re.I)

# Generic/noisy tokens that should not be used as asset identifiers.
GENERIC_TOKENS = set(["export", "assets", "build", "ntsc_en", "ps3", "rws"])


def find_chars_index(parts: List[str]) -> Optional[int]:
    """
    Return the index of 'chars' within a path parts list, or None.

    Why:
      Character folders have special normalization rules. This helps locate
      where in the path the character subtree begins.
    """
    for i, p in enumerate(parts):
        if p.lower() == "chars":
            return i
    return None


def char_root_and_variant(parts: List[str]) -> Tuple[Optional[str], str, Optional[int]]:
    """
    If the path looks like ...\\chars\\<char_or_variant>\\..., return:
        (main_char_folder, variant_slug, char_folder_index)

    Examples:
      'marge_mm2_h2_str' -> ('marge_str', 'mm2_h2', idx)
      'marge_str'        -> ('marge_str', '', idx)
      otherwise          -> (None, '', None)

    Why:
      We want *one* canonical folder per character ('<name>_str'), with any variant slug as a child.
      This collapses many near-duplicate char folders into a single root per character.
    """
    j = find_chars_index(parts)
    if j is None or j + 1 >= len(parts):
        return None, "", None

    folder = parts[j + 1]
    m_var = CHAR_FOLDER_RX.match(folder)
    if m_var:
        char_name, variant = m_var.group(1), m_var.group(2)
        return f"{char_name}_str", variant, j

    m_base = CHAR_BASE_RX.match(folder)
    if m_base:
        # already canonical
        return folder, "", j

    return None, "", None


def to_parts_lower(parts: List[str]) -> List[str]:
    """Lowercase helper used by token pickers (performance and clarity)."""
    return [p.lower() for p in parts]


def find_base_folder(rel_parts: List[str]) -> Tuple[Optional[int], Optional[str]]:
    """
    Return (index, name) of the first part that starts with allowed BASE_FOLDER_PREFIXES.

    Why:
      We must not move files outside their base folder ('Map_*' or 'Assets_*').
      This function anchors the transformation to that base.
    """
    for i, p in enumerate(rel_parts):
        for pref in BASE_FOLDER_PREFIXES:
            if p.startswith(pref):
                return i, p
    return None, None


def find_zone(parts: List[str]) -> Optional[str]:
    """
    Return the zone folder name if present (e.g., 'zone08_str'), else None.

    Why:
      Zones matter for organization and should be preserved when available.
    """
    for p in parts:
        if re.match(r"zone\d+(_[a-z0-9]+)?$", p, re.I):
            return p
    return None


def multi_ext(name: str) -> Tuple[str, str]:
    """
    Split a filename into (stem, multi-part extension).

    Why:
      Asset filenames often have compound extensions like '.dff.PS3.preinstanced'.
      We must preserve them verbatim.
    """
    parts = name.split(".")
    if len(parts) > 1:
        return parts[0], "." + ".".join(parts[1:])
    return name, ""


def short_key(s: str, length: int = 10) -> str:
    """
    Compute a short, filename-safe key = Base32(SHA1(s))[:length].

    Why:
      Embedding '__K<key>' into the flattened filename guarantees uniqueness and gives us a stable
      reverse-lookup hook even if different originals flatten to similar readable names.
      (In C#, use SHA1.Create(), compute hash bytes, then Base32-encode; trim padding.)
    """
    h = hashlib.sha1(s.encode("utf-8")).digest()
    b32 = base64.b32encode(h).decode("ascii").rstrip("=")
    return b32[:length].lower()


def strip_str_suffix(token: Optional[str]) -> Optional[str]:
    """Remove a trailing '_str' marker from a single path token."""
    if not token:
        return token
    return re.sub(r"(_str)$", "", token, flags=re.I)


def maybe_strip_str(token: Optional[str]) -> Optional[str]:
    return strip_str_suffix(token) if STRIP_STR_SUFFIX else token


def normalize_piece(s: Optional[str]) -> str:
    """
    Sanitize a path/filename token to [A-Za-z0-9_], collapsing others to underscores.

    Why:
      Ensures generated names are filesystem-friendly and consistent.
    """
    if not s:
        return "unk"
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_")


def render_filename(meta: dict, ext: str) -> str:
    """
    Build the output filename based on FILENAME_MODE / FILENAME_TEMPLATE.
    meta keys available: owner, asset, purpose, index, key
    ext includes the leading dot(s), e.g. '.dff.PS3.preinstanced'
    """
    mode = FILENAME_MODE.lower()
    owner = meta.get("owner", "")
    asset = meta.get("asset", "")
    purpose = meta.get("purpose", "")
    index = meta.get("index", "")
    key = meta.get("key", "")

    # De-duplicate owner/asset when they collapse to the same slug (common for chars).
    if owner and asset and owner.lower() == asset.lower():
        asset = ""

    if mode == "key_only":
        return f"{key}{ext}"

    if mode == "template":
        # Provide {_index} convenience
        variables = {
            "owner": owner,
            "asset": asset,
            "purpose": purpose,
            "index": index,
            "key": key,
            "ext": ext,
        }
        variables["_index"] = f"_{variables['index']}" if variables["index"] else ""
        # Basic placeholder formatting; safe for missing keys above
        return FILENAME_TEMPLATE.format(**variables)

    # default: "flattened"
    pieces = [p for p in (owner, asset, purpose) if p]
    if index:
        pieces.append(str(index))
    base = "_".join(pieces)
    return f"{base}__K{key}{ext}"


def find_category(parts: List[str]) -> str:
    """
    Determine the asset category ('chars', 'weapons', 'props', ...) from the path.

    Strategy:
      1) Prefer '...\\assets\\<category>\\...'
      2) Fallback to rightmost known category token anywhere in the path
      3) Else 'misc'

    Why:
      The category is a stable, high-signal folder we want to keep in the flattened path for grouping.
    """
    lower = [p.lower() for p in parts]
    for i, p in enumerate(lower):
        if p == "assets" and i + 1 < len(lower) and lower[i + 1] in CATEGORIES:
            cat = lower[i + 1]
            return "chars" if cat == "characters" else cat
    for p in reversed(lower):
        if p in CATEGORIES:
            return "chars" if p == "characters" else p
    return "misc"


def find_purpose(parts: List[str], stem: str) -> str:
    """
    Determine purpose ('lod', 'geo', 'opt', 'bound', ...) from path OR filename.

    Strategy:
      1) If any path token matches a known purpose, use it (normalize 'lod*' -> 'lod')
      2) Else inspect the filename stem for patterns like 'lod2_model' or '*_GEO'
      3) Else 'misc'

    Why:
      Purpose is key to organizing pipeline outputs and grouping under the final directory.
    """
    for p in parts:
        pl = p.lower()
        if pl in PURPOSE_TOKENS:
            return "lod" if pl.startswith("lod") else pl
    for rx, purpose in FILENAME_PATTERNS:
        if rx.match(stem):
            return purpose
    return "misc"


def extract_index(stem: str, purpose: str) -> Optional[str]:
    """
    Extract a numeric index from well-known stem patterns, e.g.:
      - 'lod2_model' -> '2'
      - 'opt_model7' -> '7'

    Why:
      Indexes disambiguate multiple LOD/OPT variants of the same asset.
    """
    m = re.search(r"\blod[_\- ]?(\d+)", stem, re.I)
    if not m:
        m = re.search(r"\blod(\d+)[_\- ]?model", stem, re.I)
    if not m and purpose == "opt":
        m = re.search(r"\bopt[_\- ]?model(\d+)", stem, re.I)
    return m.group(1) if m else None


def pick_owner(parts: List[str]) -> Optional[str]:
    """
    Choose a meaningful 'owner' token (character/costume/hub marker).

    Strategy:
      Prefer 'costume_*', then '*_str', then '*_hub', then any token that looks like
      '<letters>_<alnum_or_underscore>' and is not a generic token or a 'zone*'.

    Why:
      The owner gives human-readable context in the filename when we're NOT in a character-variant case.
      (Character-variant cases are handled separately to collapse multiple char folders into one.)
    """
    candidates: List[str] = []
    for p in parts:
        pl = p.lower()
        if pl.startswith("costume_"):
            candidates.append(p)
        elif pl.endswith("_str"):
            candidates.append(p)
        elif pl.endswith("_hub"):
            candidates.append(p)
        elif re.match(r"[a-z]+_[a-z0-9_]+", pl) and "zone" not in pl and pl not in GENERIC_TOKENS:
            candidates.append(p)
    return candidates[-1] if candidates else None


def pick_asset_leaf(parts: List[str]) -> Optional[str]:
    """
    Identify the leaf 'asset' token (e.g., 'slingshot', 'homer_gummi').

    Strategy:
      1) Prefer the token right after '...\\assets\\<category>\\'
      2) Else look near 'export' (just before/after)
      3) Else last non-generic, non-purpose token in the path

    Why:
      This leaf name is usually the most specific asset identifier, distinct from owner/character.
    """
    lower = [p.lower() for p in parts]
    purpose_set = set(PURPOSE_TOKENS)

    for i, p in enumerate(lower):
        if p == "assets" and i + 2 < len(lower) and lower[i + 1] in CATEGORIES:
            cand = parts[i + 2]
            pl = cand.lower()
            if pl not in GENERIC_TOKENS and pl not in purpose_set:
                return cand

    if "export" in lower:
        idx = len(parts) - 1 - lower[::-1].index("export")
        for k in (idx - 1, idx + 1):
            if 0 <= k < len(parts):
                cand = parts[k]
                pl = cand.lower()
                if pl not in GENERIC_TOKENS and pl not in purpose_set:
                    return cand

    for p in reversed(parts):
        pl = p.lower()
        if pl not in GENERIC_TOKENS and pl not in purpose_set:
            return p
    return None


def build_new_path(root: Path, rel: Path) -> Optional[Tuple[Path, Dict[str, str]]]:
    """
    Core transformation: given a file RELATIVE to ROOT, compute its new flattened path and metadata.

    Invariants:
      - The returned path never leaves its base folder (Assets_* or Map_*).
      - Zone folder is preserved when present.
      - Character folders are normalized to:  chars/<name>_str[/<variant_slug>]
      - Final layout ends with '<category>/<purpose>/<filename>' (unless adjusted by char normalization).

    Returns:
      (new_relative_path, metadata_dict)  OR  None if not under a recognized base folder.

    Why:
      This function isolates the "policy" for building the new path, so the traversal loop stays simple.
      Port this logic 1:1 in C#, including token extraction priorities.
    """
    rel_parts = list(rel.parts)
    base_idx, base_name = find_base_folder(rel_parts)
    if base_name is None:
        return None  # ignore files that aren't under a known base folder

    # Split the relative path: [ ... <base>, after... , <filename> ]
    after_base = rel_parts[base_idx + 1 : -1]  # exclude the filename
    filename = rel_parts[-1]
    stem, ext = multi_ext(filename)

    # Extract tokens from path/filename
    zone     = find_zone(after_base)
    category = find_category(after_base)
    purpose  = find_purpose(after_base, stem)
    index    = extract_index(stem, purpose)
    owner    = pick_owner(after_base)
    asset    = pick_asset_leaf(after_base)

    # Character normalization (single root per character; variant becomes its own subfolder)
    char_main, variant_slug, _ = char_root_and_variant(after_base)

    # strip _str for output everywhere
    zone_out = maybe_strip_str(zone)
    asset = maybe_strip_str(asset)

    # Choose what goes into the filename's "owner" slot:
    # - If character normalization applies, use the variant slug (if any) else the canonical char root.
    # - Otherwise, use the detected owner token.
    if char_main:
        owner_for_name = char_main
    else:
        owner_for_name = owner

    owner_for_name = maybe_strip_str(owner_for_name)

    owner_n = normalize_piece(owner_for_name)
    asset_n = normalize_piece(asset)

    # Reversible key based on the *full* original relative path
    key = short_key(str(rel))

    meta: Dict[str, str] = {
    "base": base_name,
    "zone": zone_out or "",
        "category": category,
        "purpose": purpose,
        "owner": owner_n,   # note: this is the post-normalization owner used in filename
        "asset": asset_n,
        "index": index or "",
        "key": key,
        "ext": ext
    }
    new_name = render_filename(meta, ext)

    # Build new directory (preserve base + zone; then normalized chars and/or category; end with purpose)
    new_dir_parts: List[str] = [base_name]
    if zone_out:
        new_dir_parts.append(zone_out)

    if char_main:
        # Force assets under chars/<char_str>[/<variant_slug>]
        char_root_folder = normalize_piece(maybe_strip_str(char_main))
        new_dir_parts.extend(["chars", char_root_folder])
        if variant_slug:
            new_dir_parts.append(variant_slug)
        # Optionally also retain category grouping if it's not 'chars' itself
        if category.lower() != "chars":
            new_dir_parts.append(category)
    else:
        new_dir_parts.append(category)

    new_dir_parts.append(purpose)
    new_rel = Path(*new_dir_parts) / new_name
    return new_rel, meta


def main() -> None:
    """
    Traverse ROOT, compute new paths for target assets, optionally move them, and write:
      - flatten_map.json      (all records)
      - flatten_map_<BASE>.json  (one file per base folder, e.g., Assets_2_Characters_Simpsons)
    """
    root = Path(ROOT)
    out_root = Path(OUTPUT_ROOT)

    # Ensure output directory exists for writing JSONs and copies
    out_root.mkdir(parents=True, exist_ok=True)

    mapping_rows: List[Dict[str, str]] = []
    per_base: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    total = 0

    for dp, _, files in os.walk(root):
        for fn in files:
            fl = fn.lower()
            #if ".glb" not in fl:
            #    continue


            full = Path(dp) / fn
            rel  = full.relative_to(root)

            result = build_new_path(root, rel)
            if not result:
                continue
            new_rel, meta = result
            total += 1

            row = {
                "key": meta["key"],
                "original_path": str(rel),
                "new_path": str(new_rel),
                "base": meta["base"],
                "zone": meta["zone"],
                "category": meta["category"],
                "purpose": meta["purpose"],
                "owner": meta["owner"],
                "asset": meta["asset"],
                "index": meta["index"],
                "ext": meta["ext"]
            }
            mapping_rows.append(row)
            per_base[meta["base"]].append(row)

            if DRY_RUN:
                print(f"[DRY COPY] {rel}  ->  {new_rel} (to {out_root.name})")
            else:
                dest = out_root / new_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                final_dest = dest
                if dest.exists():
                    base, e = os.path.splitext(dest.name)
                    final_dest = dest.with_name(base + "_dup" + e)
                shutil.copy2(full, final_dest)

    mapping_rows.sort(key=lambda r: (r["base"], r["original_path"]))
    for base, rows in per_base.items():
        rows.sort(key=lambda r: r["original_path"])

    map_json = out_root / "flatten_map.json"
    write_json(map_json, mapping_rows)

    created: List[str] = []
    for base, rows in per_base.items():
        safe = sanitize_filename(base)
        per_path = out_root / f"flatten_map_{safe}.json"
        write_json(per_path, rows)
        created.append(per_path.name)

    summary = {
        "total_assets": total,
        "bases": {b: len(rows) for b, rows in per_base.items()},
        "files_written": [map_json.name] + created,
    }
    summary_json = out_root / "flatten_map_summary.json"
    write_json(summary_json, summary)

    print(f"\nFound {total} assets.")
    print(f"JSON mapping written to: {map_json}")
    if created:
        print("Per-base maps:")
        for name in created:
            print(f"  - {name}")
        print(f"Summary: {summary_json}")


if __name__ == "__main__":
    main()
