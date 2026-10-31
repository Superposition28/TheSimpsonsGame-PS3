import csv
import hashlib
import os
from pathlib import Path
import re
import sys
from collections import defaultdict

# ----------------------------------------------------------------------
# Configuration & Knowledge Base
# ----------------------------------------------------------------------
RUN_CONFIGS = {
    "source": {
        "report_prefix": "report_source",
        "folders": {
            "PS3_EU": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\Source\PS3\EU\1\PS3_GAME\USRDIR",
            "PS3_US": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\Source\PS3\US\1\PS3_GAME\USRDIR",
            "XBOX_EU": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\Source\XBOX360\EU\1\TSG",
            "XBOX_US": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\Source\XBOX360\US\1\extractedFiles",
        },
    },
    "normalised": {
        "report_prefix": "report_normalised",
        "folders": {
            "PS3_EU": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\PS3-EU-FullFlattened-audio_reorg-isRenamed",
            "PS3_US": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\PS3-US-FullFlattened-audio_reorg-isRenamed",
            "XBOX_EU": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\XBOX360-EU-FullFlattened-audio_reorg-isRenamed",
            "XBOX_US": r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\XBOX360-US-FullFlattened-audio_reorg-isRenamed",
        },
    },
}

HASH_CHUNK_SIZE = 1024 * 1024

PLATFORM_PATTERN = r"(?:ps3|xen|xnx|xbox360|x360)"
LANGUAGE_FOLDERS = {"/es/", "/fr/", "/it/", "/de/", "/sf/", "/uk/", "/us/", "/en/", "/da/", "/fi/", "/no/"}

RE_RAW_BUILD_PATH = re.compile(rf"(^|/)build/{PLATFORM_PATTERN}/(?:ntsc|pal)_[a-z]{{2}}(?=/|$)", re.IGNORECASE)
RE_NORM_BUILD_PATH = re.compile(rf"(^|/)build{PLATFORM_PATTERN}(?:(?:ntsc|pal)[a-z]{{2}})?(?=/|$)", re.IGNORECASE)
RE_PLATFORM_PATH = re.compile(rf"(^|/){PLATFORM_PATTERN}(?=/|$)", re.IGNORECASE)
RE_PLATFORM_EXT_SEGMENT = re.compile(rf"\.{PLATFORM_PATTERN}(?=\.|$)", re.IGNORECASE)
RE_UID_SUFFIX = re.compile(r"_[0-9a-f]{6}(?=\.[^./]+(?:\.[^./]+)*$)", re.IGNORECASE)
RE_TEXTURE_EXT = re.compile(r"\.i?txd$", re.IGNORECASE)

# Define expected behavior mappings for known extensions
EXPECTED_BEHAVIORS = {
    ".vp6": ["IDENTICAL_ALL_4", "EXPECTED_LOCALIZATION", "ALL_4_DIFFERENT"], # ALL_4_DIFF covers the EA logo
    ".bnk": ["IDENTICAL_ALL_4"],
    ".rcb": ["IDENTICAL_ALL_4"],
    ".vfb": ["IDENTICAL_ALL_4"],
    ".acs": ["IDENTICAL_ALL_4"],
    ".graph": ["IDENTICAL_ALL_4"],
    ".bbn": ["IDENTICAL_ALL_4"],
    ".str.occ.toc": ["IDENTICAL_ALL_4"],
    ".mus": ["IDENTICAL_REGIONS_DIFFER_BY_PLATFORM"],
    ".sbk": ["IDENTICAL_REGIONS_DIFFER_BY_PLATFORM", "XBOX_MATCHES_PS3_DIFFERS", "PS3_MATCHES_XBOX_DIFFERS", "EXPECTED_LOCALIZATION"],
    ".canonical_txd": ["IDENTICAL_REGIONS_DIFFER_BY_PLATFORM", "XBOX_MATCHES_PS3_DIFFERS", "PS3_MATCHES_XBOX_DIFFERS"],
    ".dff.preinstanced": ["ALL_4_DIFFERENT", "IDENTICAL_REGIONS_DIFFER_BY_PLATFORM"],
    ".lh2": ["EXPECTED_LOCALIZATION", "UNEXPECTED_MISSING"], # lh2 text files have weird regional splits
    ".rcm_b": ["XBOX_MATCHES_PS3_DIFFERS", "IDENTICAL_REGIONS_DIFFER_BY_PLATFORM", "PS3_MATCHES_XBOX_DIFFERS"],
    ".dat": ["IDENTICAL_ALL_4"], # Exclusives here are usually unexpected +1 naming shifts
    "[NO_EXTENSION]": ["IDENTICAL_ALL_4"],
    ".rws.preinstanced": ["ALL_4_DIFFERENT", "IDENTICAL_REGIONS_DIFFER_BY_PLATFORM", "XBOX_MATCHES_PS3_DIFFERS", "PS3_MATCHES_XBOX_DIFFERS"],
    ".hkt": ["IDENTICAL_REGIONS_DIFFER_BY_PLATFORM", "ALL_4_DIFFERENT", "XBOX_MATCHES_PS3_DIFFERS", "PS3_MATCHES_XBOX_DIFFERS"],
    ".hko": ["ALL_4_DIFFERENT", "PS3_MATCHES_XBOX_DIFFERS", "XBOX_MATCHES_PS3_DIFFERS", "IDENTICAL_REGIONS_DIFFER_BY_PLATFORM"],
    ".meta.xml": ["IDENTICAL_ALL_4", "ALL_4_DIFFERENT"],
    ".xml": ["IDENTICAL_ALL_4", "ALL_4_DIFFERENT"],
    ".bsp": ["ALL_4_DIFFERENT", "COMPLEX_MATCH", "IDENTICAL_ALL_4"],
    ".smb": ["IDENTICAL_ALL_4"],
    ".tox": ["IDENTICAL_ALL_4"],
    ".uix": ["IDENTICAL_ALL_4"],
    ".imb": ["IDENTICAL_ALL_4"],
    ".alb": ["IDENTICAL_ALL_4"],
    ".mib": ["IDENTICAL_ALL_4"],
}

# ----------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------
def get_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(HASH_CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except OSError as err:
        return f"ERR_{err}"

def is_localization_file(norm_path: str) -> bool:
    return any(lang in norm_path for lang in LANGUAGE_FOLDERS)

def get_full_extension(filepath: str) -> str:
    filename = filepath.split("/")[-1]
    if "." in filename:
        return filename[filename.index("."):]
    return "[NO_EXTENSION]"

def normalize_dir_path(rel_str: str) -> str:
    norm = rel_str.replace("\\", "/").lower()
    norm = RE_RAW_BUILD_PATH.sub("", norm)
    norm = RE_NORM_BUILD_PATH.sub("", norm)
    norm = RE_PLATFORM_PATH.sub(r"\1", norm)
    norm = re.sub(r"/+", "/", norm).strip("/")
    return norm

def normalize_file_path(rel_str: str, is_normalised_run: bool = False) -> str:
    norm = rel_str.replace("\\", "/").lower()
    norm = RE_RAW_BUILD_PATH.sub("", norm)
    norm = RE_NORM_BUILD_PATH.sub("", norm)
    norm = RE_PLATFORM_PATH.sub(r"\1", norm)
    norm = RE_PLATFORM_EXT_SEGMENT.sub("", norm)
    norm = RE_TEXTURE_EXT.sub(".canonical_txd", norm)
    norm = re.sub(r"/+", "/", norm).strip("/")
    if is_normalised_run:
        norm = RE_UID_SUFFIX.sub("", norm)
    return norm

# ----------------------------------------------------------------------
# 1. Directory Tree Comparison
# ----------------------------------------------------------------------
def analyze_directory_trees(folders: dict):
    print("\n--- [1] DIRECTORY TREE ANALYSIS (FOLDERS ONLY) ---")
    normalized_dirs = defaultdict(lambda: defaultdict(list))
    for label, root_str in folders.items():
        root = Path(root_str)
        if not root.exists(): continue
        raw_dirs = set()
        for dirpath, dirnames, _ in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() != "audio"]
            for d in dirnames:
                rel_d = str((Path(dirpath) / d).relative_to(root)).replace("\\", "/")
                raw_dirs.add(rel_d)
                norm_d = normalize_dir_path(rel_d)
                if norm_d: normalized_dirs[norm_d][label].append(rel_d)
        print(f"  {label:<8}: {len(raw_dirs):>5} raw subdirectories")

    dir_presence = defaultdict(int)
    for build_map in normalized_dirs.values():
        present = set(build_map.keys())
        tag = "ALL_4_MATCH" if len(present) == 4 else f"PARTIAL ({'+'.join(sorted(present))})"
        dir_presence[tag] += 1
    
    print("\n  Canonical Directory Breakdown:")
    for tag, count in sorted(dir_presence.items(), key=lambda x: -x[1]):
        print(f"    {tag:<35}: {count:>5}")

# ----------------------------------------------------------------------
# 2. File Analysis & Extension Breakdown
# ----------------------------------------------------------------------
def analyze_files(folders: dict, is_normalised_run: bool, prefix: str):
    labels = list(folders.keys())
    file_index = defaultdict(dict)

    print("\nScanning files and mapping extensions...")
    for label, root_str in folders.items():
        root = Path(root_str)
        if not root.exists(): continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() != "audio"]
            for fname in filenames:
                full_path = Path(dirpath) / fname
                rel_path = full_path.relative_to(root)
                if rel_path.suffix.lower() == ".snu" or (len(rel_path.parts) == 1 and rel_path.suffix.lower() in {".json", ".lua"}):
                    continue
                rel_str = str(rel_path).replace("\\", "/")
                canonical_key = normalize_file_path(rel_str, is_normalised_run)
                file_index[canonical_key][label] = {"full_path": full_path, "rel_path": rel_str, "size": full_path.stat().st_size}

    print("Hashing candidates...")
    for builds in file_index.values():
        size_groups = defaultdict(list)
        for label, meta in builds.items():
            size_groups[meta["size"]].append(label)
        for size, matching_labels in size_groups.items():
            if len(matching_labels) > 1 and size > 0:
                for label in matching_labels:
                    builds[label]["hash"] = get_sha256(builds[label]["full_path"])
            else:
                for label in matching_labels:
                    builds[label]["hash"] = "EMPTY_0B" if size == 0 else f"UNIQUE_SIZE_{size}_{label}"

    all_labels_set = set(labels)
    ext_breakdown = {
        "KNOWN_EXPECTED": defaultdict(int),
        "KNOWN_UNEXPECTED": defaultdict(int),
        "UNKNOWN": defaultdict(int)
    }
    rows = []

    for canonical_key, builds in sorted(file_index.items()):
        present_labels = set(builds.keys())
        is_in_all = present_labels == all_labels_set
        is_localization = is_localization_file(f"/{canonical_key}")
        ext = get_full_extension(canonical_key)

        # 1. Determine Content Status (if present in all)
        content_tag = "INCOMPLETE_PRESENCE"
        if is_in_all:
            hashes = {builds[l]["hash"] for l in labels}
            if len(hashes) == 1:
                content_tag = "IDENTICAL_ALL_4"
            elif builds["PS3_EU"]["hash"] == builds["PS3_US"]["hash"] and builds["XBOX_EU"]["hash"] == builds["XBOX_US"]["hash"]:
                content_tag = "IDENTICAL_REGIONS_DIFFER_BY_PLATFORM" 
            elif builds["PS3_EU"]["hash"] == builds["XBOX_EU"]["hash"] and builds["PS3_US"]["hash"] == builds["XBOX_US"]["hash"]:
                content_tag = "IDENTICAL_PLATFORMS_DIFFER_BY_REGION"
            elif builds["PS3_EU"]["hash"] == builds["PS3_US"]["hash"]:
                content_tag = "PS3_MATCHES_XBOX_DIFFERS"
            elif builds["XBOX_EU"]["hash"] == builds["XBOX_US"]["hash"]:
                content_tag = "XBOX_MATCHES_PS3_DIFFERS"
            elif len(hashes) == 4:
                content_tag = "ALL_4_DIFFERENT"
            else:
                content_tag = "COMPLEX_MATCH"

        # 2. Assign Unified Behavior Tag
        if is_in_all:
            behavior_tag = content_tag
        elif is_localization:
            behavior_tag = "EXPECTED_LOCALIZATION"
        else:
            behavior_tag = "UNEXPECTED_MISSING"

        # 3. Classify the Extension
        if ext in EXPECTED_BEHAVIORS:
            if behavior_tag in EXPECTED_BEHAVIORS[ext]:
                ext_class = "KNOWN_EXPECTED"
            else:
                ext_class = "KNOWN_UNEXPECTED"
        else:
            ext_class = "UNKNOWN"

        ext_breakdown[ext_class][(ext, behavior_tag)] += 1

        # Record CSV Data
        raw_filenames = {Path(b["rel_path"]).name for b in builds.values()}
        naming_variant = "PLATFORM_EXT_DIFF" if len(raw_filenames) > 1 else "IDENTICAL_FILENAME"
        sample_rel = next(iter(builds.values()))["rel_path"]
        
        row = {
            "Canonical_Key": canonical_key,
            "Sample_Path": sample_rel,
            "Extension": ext,
            "Behavior_Tag": behavior_tag,
            "Naming_Variant": naming_variant,
        }
        for l in labels:
            row[f"{l}_Size"] = builds[l]["size"] if l in builds else "-"
            row[f"{l}_Hash"] = builds[l]["hash"][:12] if l in builds else "-"
        rows.append(row)

    # Write CSVs split by Behavior_Tag
    fields = ["Canonical_Key", "Sample_Path", "Extension", "Behavior_Tag", "Naming_Variant"]
    for l in labels: fields.extend([f"{l}_Size", f"{l}_Hash"])

    # Group rows by behavior
    rows_by_behavior = defaultdict(list)
    for row in rows:
        rows_by_behavior[row["Behavior_Tag"]].append(row)

    for behavior_tag, behavior_rows in rows_by_behavior.items():
        # Clean tag to ensure safe filenames
        safe_tag = "".join(c for c in behavior_tag if c.isalnum() or c in ("_", "-"))
        csv_file = f"{prefix}_{safe_tag}.csv"

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(behavior_rows)

    # Print Breakdown
    print("\n--- [2] EXTENSION BEHAVIOR ANALYSIS ---")
    
    print("\n🟢 KNOWN EXTENSIONS (Acting Exactly as Expected)")
    for (ext, beh), count in sorted(ext_breakdown["KNOWN_EXPECTED"].items(), key=lambda x: (-x[1], x[0][0])):
        print(f"  {ext:<20} | {beh:<40} : {count:>5}")

    print("\n🔴 KNOWN EXTENSIONS (Acting UNEXPECTEDLY)")
    if not ext_breakdown["KNOWN_UNEXPECTED"]:
        print("  None! All known extensions behaved correctly.")
    else:
        for (ext, beh), count in sorted(ext_breakdown["KNOWN_UNEXPECTED"].items(), key=lambda x: (-x[1], x[0][0])):
            print(f"  {ext:<20} | {beh:<40} : {count:>5}")

    print("\n🟡 UNKNOWN EXTENSIONS (Discovered during scan)")
    for (ext, beh), count in sorted(ext_breakdown["UNKNOWN"].items(), key=lambda x: (-x[1], x[0][0])):
        print(f"  {ext:<20} | {beh:<40} : {count:>5}")

    print(f"\nDetailed file reports written to the current directory with prefix: {prefix}_<Behavior_Tag>.csv")

def main():
    for run_name, config in RUN_CONFIGS.items():
        print("\n" + "=" * 80)
        print(f"RUNNING ANALYSIS FOR: {run_name.upper()}")
        print("=" * 80)
        analyze_directory_trees(config["folders"])
        is_normalised = run_name == "normalised"
        analyze_files(config["folders"], is_normalised, config["report_prefix"])

if __name__ == "__main__":
    main()