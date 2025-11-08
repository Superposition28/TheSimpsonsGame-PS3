"""
validate that the hex headers found are correct and consistent accross all assets

"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from collections import Counter, defaultdict


TARGET_SUFFIXES = (
    ".rws.ps3.preinstanced",
    ".dff.ps3.preinstanced",
)

@dataclass
class PatternDef:
    """Human-friendly description of a binary pattern segment.

    Attributes:
        name: Display name used in reports.
        pattern: Single wildcard-capable hex string (e.g., "2D 00 ** 1C").
        patterns: Alternate patterns for the same logical segment; any may match.
        required: If True, missing this segment makes the file fail.
        note: Informational note shown in reports.
        max_allowed: Optional upper bound on occurrences per file (0 = no limit).
    follows: Priority-ordered list of predecessor constraints. For each tuple
                 (parent_id, relation), if that parent pattern exists in the file,
                 this pattern must satisfy the relation with respect to some
                 occurrence of the parent. If none of the listed parents exist,
                 the dependency is not enforced for this pattern.
                 relation: 'immediate' (start == parent_end) or 'after' (start >= parent_end).
    expected_offset: Optional absolute file offset where this segment is expected
             to start. If the segment is required and not found, the
             error message will include a 56-byte hex dump from this
             offset for debugging.
    """
    id: int
    name: str
    pattern: Optional[str] = None
    # Optional list of alternative patterns; if provided, any variant matching counts
    patterns: Optional[List[str]] = None
    required: bool = True
    note: str = ""
    max_allowed: int = 0  # 0 = no limit
    follows: Optional[List[Tuple[int, str]]] = None
    # Optional end-of-segment pattern: when provided, the true end of the
    # segment is determined by the first match of this pattern at/after the
    # segment start; dependency relations then use this end instead of the
    # start-pattern length.
    EOSPattern: Optional[str] = None
    # Optional absolute offset hint for diagnostics
    expected_offset: Optional[int] = None

PATTERN_DEFS: List[PatternDef] = [

    ## long headers are used in place of short ones to ensure correct detection avoiding any other instances of a similar hex string, Offsets cannot be used as there not consistant
    PatternDef(
        id=1,
        name="SOF Main header",
        patterns=[
            "10 00 00 00 0a 12 00 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C 01 00 00 00 00 00 00 00 00 00 00 00 0E 00 00 00 dc 00 00 00 2D 00 02 1C 01 00 00 00 74 00 00 00 ",
            "10 00 00 00 36 29 00 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C 02 00 00 00 00 00 00 00 00 00 00 00 0E 00 00 00 68 01 00 00 2D 00 02 1C 01 00 00 00 e4 00 00 00 ",
            # universal pattern for all SOF main headers
            "10 00 00 00 ?? ?? ?? 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C ?? ?? ?? ?? 00 00 00 00 00 00 00 00 0E 00 00 00 ?? ?? ?? ?? 2D 00 02 1C 01 00 00 00 ?? ?? ?? ?? ",
        ],
        required=True,
        note="",
        max_allowed=1,
        follows=None,
        expected_offset=0x00,
    ),
    PatternDef(
        id=2,
        name="SOF Second header",
        patterns=[
            ## four common patterns
            "2D 00 02 1C 03 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 ",
            "2D 00 02 1C 02 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 ",
            "2D 00 02 1C 04 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 ",
            "2D 00 02 1C 03 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 ",
            ## universal match for all second headers
            "2D 00 02 1C ** ** ** ** 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** ** ",
        ],
        required=True,
        note="",
        max_allowed=1,
        follows=[(1, "immediate")],
        expected_offset=0x38,
    ),
    PatternDef(
        id=3,
        name="SOF Third header",
        patterns=[
            ## every possible variation of the third header
            "FF FF FF FF 00 00 00 00 22 C4 7A 3D 00 00 00 00 43 D0 A0 BE 00 00 00 00 0A D7 A3 3E 00 00 00 00 43 D0 A0 3E 00 00 00 00 22 C4 7A 3D 04 29 29 42 4B CC 72 41 55 A4 32 C3",
            "FF FF FF FF 00 00 00 00 FF 32 00 BF 00 00 00 00 5E 96 5D 3F 00 00 00 00 00 00 80 3F 00 00 00 00 5E 96 5D BF 00 00 00 00 FF 32 00 BF 54 89 D3 42 7B C1 0C 41 15 5A 05 C3",
            "FF FF FF FF 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 BF 1A B4 92 C2 CF F7 E7 40 99 67 A3 42",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 F8 86 8F B1 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 1E 0B 8D C2 80 CC B2 3C BA CC 40 41",
            "FF FF FF FF 00 00 00 00 5E A8 51 BF 00 00 00 00 70 E6 12 BF 00 00 00 00 00 00 80 3F 00 00 00 00 70 E6 12 3F 00 00 00 00 5E A8 51 BF C8 01 85 C1 00 00 00 00 00 F1 95 BF",
            "FF FF FF FF 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 4B 16 B2 00 00 00 B2 00 00 80 BF 56 DF 97 B5 5C 58 81 B5 00 00 55 3B",
            "FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 2E 81 31 00 00 80 3F 00 28 27 31 00 00 80 BF 00 00 00 00 00 00 00 00 D6 B2 B2 C0 00 00 00 00 5C CB 30 41",
            "FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 5F 65 8A 41 36 53 AC C1 BF 5F 37 C1",
            "FF FF FF FF 00 00 00 00 B0 96 A6 B2 20 2C 27 B3 FF FF 7F 3F 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 00 00 45 F9 12 41 C2 BA 9F B5 E7 9B 26 41",
            "FF FF FF FF 00 00 00 00 32 61 0A C0 00 00 00 00 E7 DF 13 3F 00 00 00 00 94 3B 0F 40 00 00 00 00 E7 DF 13 BF 00 00 00 00 32 61 0A C0 17 64 84 C2 22 C8 17 42 87 15 3C C3",
            "FF FF FF FF 00 00 00 00 30 0D 00 3F 28 15 F9 BD 75 C8 4A 3F BB 14 0F BE BC FD 67 3F CC D4 68 3E 57 04 4A BF C2 40 73 BE 04 76 EC 3E C6 AD 96 C2 0B 51 25 41 2F 1B B0 C0",
            "FF FF FF FF 00 00 00 00 80 D6 82 3F 02 17 78 B1 ED F8 39 3E 00 00 00 00 13 E3 84 3F 00 00 00 00 EF F8 39 BE 31 FB 3D 32 80 D6 82 3F 6B AD F9 C0 77 59 4A 40 29 DF 72 41",
            "FF FF FF FF 00 00 00 00 32 EF AB 3E 04 66 30 B2 F9 0F 5C BF 00 00 00 00 09 42 6C 3F 00 00 00 00 F9 0F 5C 3F 54 B2 A8 B0 31 EF AB 3E 7D AF 72 C0 9D E4 8D 40 A2 97 30 C0",
            "FF FF FF FF 00 00 00 00 32 EF AB 3E 04 66 30 B2 F9 0F 5C BF 00 00 00 00 09 42 6C 3F 00 00 00 00 F9 0F 5C 3F 54 B2 A8 B0 31 EF AB 3E FE 18 6E C0 30 69 8B 40 4B AF 33 C0",
            "FF FF FF FF 00 00 00 00 32 EF AB 3E 04 66 30 B2 F9 0F 5C BF 00 00 00 00 09 42 6C 3F 00 00 00 00 F9 0F 5C 3F 54 B2 A8 B0 31 EF AB 3E 59 C5 71 C0 9D E4 8D 40 2A 3C 30 C0",
            "FF FF FF FF 00 00 00 00 80 D6 82 3F 02 17 78 B1 ED F8 39 3E 00 00 00 00 13 E3 84 3F 00 00 00 00 EF F8 39 BE 31 FB 3D 32 80 D6 82 3F A2 1E FB C0 61 7A 4C 40 55 2D 73 41",
            "FF FF FF FF 00 00 00 00 32 EF AB 3E 04 66 30 B2 F9 0F 5C BF 00 00 00 00 09 42 6C 3F 00 00 00 00 F9 0F 5C 3F 54 B2 A8 B0 31 EF AB 3E E5 D2 6B C0 40 D6 9A 40 9F 33 31 C0",
            "FF FF FF FF 00 00 00 00 54 24 C7 BE D4 1A 5A B2 15 CB 6C BF 00 00 00 00 2B 70 80 3F 00 00 00 00 17 CB 6C 3F 98 31 D2 B1 53 24 C7 BE B4 C3 B1 C0 D8 DC E9 40 D2 9A 06 C1",
            "FF FF FF FF 00 00 00 00 54 24 C7 BE D4 1A 5A B2 15 CB 6C BF 00 00 00 00 2B 70 80 3F 00 00 00 00 17 CB 6C 3F 98 31 D2 B1 53 24 C7 BE B4 C3 B1 C0 D8 DC E9 40 D2 9A 06 C1",
            "FF FF FF FF 00 00 00 00 54 24 C7 BE D4 1A 5A B2 15 CB 6C BF 00 00 00 00 2B 70 80 3F 00 00 00 00 17 CB 6C 3F 98 31 D2 B1 53 24 C7 BE 4F 4F B4 C0 16 2E EF 40 9B 03 06 C1",
            "FF FF FF FF 00 00 00 00 54 24 C7 BE D4 1A 5A B2 15 CB 6C BF 00 00 00 00 2B 70 80 3F 00 00 00 00 17 CB 6C 3F 98 31 D2 B1 53 24 C7 BE B4 C3 B1 C0 D8 DC E9 40 D2 9A 06 C1",
            "FF FF FF FF 00 00 00 00 B8 F3 F2 3E D2 54 31 B2 E0 57 61 3F 00 00 00 00 00 00 80 3F 00 00 00 00 E0 57 61 BF 38 30 BF B1 B8 F3 F2 3E 5C 7F A3 40 2F 50 6D 40 75 37 67 C2",
            "FF FF FF FF 00 00 00 00 41 F1 0C BF 03 F3 30 B2 96 DB 60 3F 00 00 00 00 74 B0 84 3F 00 00 00 00 96 DB 60 BF 77 D3 DD 31 41 F1 0C BF BF 7A AC C0 D6 4B F9 40 0D E7 64 C2",
            "FF FF FF FF 00 00 00 00 B8 F3 F2 3E D2 54 31 B2 E0 57 61 3F 00 00 00 00 00 00 80 3F 00 00 00 00 E0 57 61 BF 38 30 BF B1 B8 F3 F2 3E CF 57 A1 40 A1 AE 84 40 F0 D5 66 C2",
            "FF FF FF FF 00 00 00 00 41 F1 0C BF 03 F3 30 B2 96 DB 60 3F 00 00 00 00 74 B0 84 3F 00 00 00 00 96 DB 60 BF 77 D3 DD 31 41 F1 0C BF 6D 17 AA C0 95 15 FC 40 A9 17 65 C2",
            "FF FF FF FF 00 00 00 00 5F A6 A7 3F 8E 46 CE 31 53 17 F0 32 00 00 00 00 60 A6 A7 3F 00 00 00 00 00 00 00 00 00 00 00 00 60 A6 A7 3F FC AB 03 42 CA CC 51 41 58 29 5A BE",
            "FF FF FF FF 00 00 00 00 5F A6 A7 3F 8E 46 CE 31 53 17 F0 32 00 00 00 00 60 A6 A7 3F 00 00 00 00 00 00 00 00 00 00 00 00 60 A6 A7 3F 4D 13 04 42 E3 09 50 41 F1 AC 12 BE",
            "FF FF FF FF 00 00 00 00 5F A6 A7 3F 8E 46 CE 31 53 17 F0 32 00 00 00 00 60 A6 A7 3F 00 00 00 00 00 00 00 00 00 00 00 00 60 A6 A7 3F FC AB 03 42 CA CC 51 41 5E DD 43 BE",
            "FF FF FF FF 00 00 00 00 5F A6 A7 3F 8E 46 CE 31 53 17 F0 32 00 00 00 00 60 A6 A7 3F 00 00 00 00 00 00 00 00 00 00 00 00 60 A6 A7 3F 92 F1 03 42 2C FC 5A 41 BE 21 9C BD",
            "FF FF FF FF 00 00 00 00 D7 EC 6A 3F 39 38 7B 32 1F 86 1C 3F 00 00 00 00 8E 25 8D 3F 00 00 00 00 1E 86 1C BF 02 2B 88 30 D6 EC 6A 3F 6E 50 F3 C1 66 AF 27 40 93 0A 8A 41",
            "FF FF FF FF 00 00 00 00 03 0D 6E BE 4F 13 AA 3D 92 DB 82 3F 7C 46 33 3E 83 38 8B 3F 21 D3 46 BD B1 C6 4F BF BD C7 F9 3D 3A 22 47 BE 1C 23 B8 C1 87 A2 0A 3C D1 88 83 C1",
            "FF FF FF FF 00 00 00 00 D7 EC 6A 3F 39 38 7B 32 1F 86 1C 3F 00 00 00 00 8E 25 8D 3F 00 00 00 00 1E 86 1C BF 02 2B 88 30 D6 EC 6A 3F 10 E9 F2 C1 43 5F 33 40 73 62 89 41",
            "FF FF FF FF 00 00 00 00 D7 EC 6A 3F 39 38 7B 32 1F 86 1C 3F 00 00 00 00 8E 25 8D 3F 00 00 00 00 1E 86 1C BF 02 2B 88 30 D6 EC 6A 3F 6E 50 F3 C1 66 AF 27 40 93 0A 8A 41",
            "FF FF FF FF 00 00 00 00 03 0D 6E BE 4F 13 AA 3D 92 DB 82 3F 7C 46 33 3E 83 38 8B 3F 21 D3 46 BD B1 C6 4F BF BD C7 F9 3D 3A 22 47 BE 1C 23 B8 C1 87 A2 0A 3C D1 88 83 C1",
            "FF FF FF FF 00 00 00 00 D7 EC 6A 3F 39 38 7B 32 1F 86 1C 3F 00 00 00 00 8E 25 8D 3F 00 00 00 00 1E 86 1C BF 02 2B 88 30 D6 EC 6A 3F 6E 50 F3 C1 66 AF 27 40 93 0A 8A 41",
            "FF FF FF FF 00 00 00 00 F4 26 45 3F F2 D9 CF 2F 7E A1 60 32 00 00 00 00 DF 7F 2E 3F 00 00 00 00 00 00 00 00 00 00 00 00 F4 26 45 3F 85 A4 61 C1 CA EE 55 BD 8D 27 BE C1",
            "FF FF FF FF 00 00 00 00 1A 4E B2 3E 2E 08 36 31 61 B2 53 3F 00 00 00 00 1A B4 65 3F 00 00 00 00 61 B2 53 BF 22 1F D8 B1 19 4E B2 3E 15 2F 07 C2 DD AE FC 40 F5 8F 14 BF",
            "FF FF FF FF 00 00 00 00 EC A1 01 3F 90 57 84 31 E7 E0 29 3F 00 00 00 00 92 B0 55 3F 00 00 00 00 E7 E0 29 BF E5 6D AD B1 EC A1 01 3F CF 04 03 C2 49 8A 10 41 3F EC B6 40",
            "FF FF FF FF 00 00 00 00 EC A1 01 3F 90 57 84 31 E7 E0 29 3F 00 00 00 00 92 B0 55 3F 00 00 00 00 E7 E0 29 BF E5 6D AD B1 EC A1 01 3F D4 13 03 C2 A6 A9 11 41 5B B1 B4 40",
            "FF FF FF FF 00 00 00 00 BA F6 AB 40 00 00 00 00 FB 7C 47 C0 00 00 00 00 FD E6 8F 40 00 00 00 00 FE 66 10 40 00 00 00 00 ED F4 78 40 7D C0 82 C3 49 4F 20 41 45 64 12 C2",
            "FF FF FF FF 00 00 00 00 E5 88 B6 BF 00 00 00 00 00 00 00 00 00 00 00 00 F5 35 B3 3F 00 00 00 00 00 00 00 00 00 00 00 00 91 9E 88 BF FA FA E0 42 84 90 8C 3F 18 74 13 C2",
            "FF FF FF FF 00 00 00 00 A8 A6 7F 3F 00 00 00 00 28 CE 55 BD 00 00 00 00 00 00 80 3F 00 00 00 00 28 CE 55 3D 00 00 00 00 A8 A6 7F 3F 42 4A 14 42 EE E4 C9 40 AC CF 27 41",
            "FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 51 0E 0C 43 3E A5 78 3F BF FF 1E 43",
            "FF FF FF FF 00 00 00 00 C3 CC 07 3E 00 00 00 00 25 BD 7D 3F 00 00 00 00 00 00 80 3F 00 00 00 00 25 BD 7D BF 00 00 00 00 C3 CC 07 3E FA A8 13 43 00 00 00 00 F6 A1 B9 C1",
            "FF FF FF FF 00 00 00 00 E2 43 5F 3F 58 36 C8 BE 8D 90 96 3E F7 95 B7 3E FD 74 6B 3F 60 77 23 3E 7D 71 AA BE 30 5B 0A BD 60 3E 71 3F A6 4F DD BF 85 88 09 41 D3 B4 1B C2",
            "FF FF FF FF 00 00 00 00 FB 9B 40 3F B6 2B 25 3E 2C D8 FE BB 46 73 24 BE 47 54 3E 3F 46 EC EE BD F2 C4 8A BC 44 ED EC 3D 6F B5 42 3F 0E 22 15 3E 13 62 99 BD FC DE C9 40",
            "FF FF FF FF 00 00 00 00 95 9C 6D BF C1 DE A2 BE 18 CA 45 BE BC ED 32 BE 27 AC 54 3F 33 4C 07 BF 21 3C A8 3E D2 E0 E9 BE 38 A0 53 BF F3 D1 52 40 D5 9C A7 41 C1 47 71 42",
            "FF FF FF FF 00 00 00 00 65 67 A4 BF 00 00 00 00 22 35 B0 BE 00 00 00 00 15 34 AA 3F 00 00 00 00 22 35 B0 3E 00 00 00 00 65 67 A4 BF B3 3F C2 42 1C 4F 9D 3D 78 62 4E 42",
            "FF FF FF FF 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 BF FC 89 52 C2 DB F6 D3 41 43 CD 95 43",
            "FF FF FF FF 00 00 00 00 1E 99 83 B2 A7 9A B6 AD 1B 7D 9F 3F 00 00 00 00 D8 9C 38 3F 00 00 00 00 34 6C E0 BF 2E C0 19 21 AB 49 06 B3 C1 3E E8 41 90 35 89 3E AA D5 45 43",
            "FF FF FF FF 00 00 00 00 EB 5C 31 3F 3E 15 6A 2F 73 9A 38 BF 00 00 00 00 00 00 80 3F 00 00 00 00 72 9A 38 3F 03 63 F5 2F EB 5C 31 3F 82 CC CD 41 FF 30 86 3F 58 75 9F 40",
            "FF FF FF FF 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 BF 00 80 B3 43 2B 61 0C C2 2C B8 A6 C3",
            "FF FF FF FF 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 1A 00 00 00 10 00 00 00 2D 00 02 1C 01 00 00 00 04 00 00 00 2D 00 02 1C 00 00 00 00 03 00 00 00 11 00 00 00",
            "FF FF FF FF 00 00 00 00 F7 C7 A2 BF 00 00 00 00 F8 C7 A2 BF 00 00 00 00 11 35 E6 3F 00 00 00 00 F8 C7 A2 3F 00 00 00 00 F7 C7 A2 BF 11 02 3C 43 D0 FF 35 C0 7F A8 7F C3",
            "FF FF FF FF 00 00 00 00 E4 55 7A 3F 00 00 00 00 85 27 86 3E 00 00 00 00 4D 95 81 3F 00 00 00 00 18 B5 7B BE 00 00 00 00 A2 D8 6A 3F 59 F2 12 C3 B3 0D 37 C0 AC 19 48 C3",
            "FF FF FF FF 00 00 00 00 CB 60 66 BD A2 B9 E4 B0 6F CA 9D 3F 00 00 00 00 75 F4 9D 3F 00 00 00 00 6F CA 9D BF 3B 86 11 32 CB 60 66 BD 27 88 DE 41 4D 5D 84 C1 69 31 57 C3",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 14 92 86 AE 29 D7 7F 3F 91 94 10 3D BD 20 EE B0 91 94 10 BD 29 D7 7F 3F 9E 9D 9D BD 85 13 CD C1 B5 BE E9 42",
            "FF FF FF FF 00 00 00 00 D9 BD 60 BF 58 54 48 30 D0 2B F5 3E 00 00 00 00 00 00 80 3F 00 00 00 00 D0 2B F5 BE F0 A2 B7 B0 D9 BD 60 BF CE 75 E6 C1 10 FB 7B 40 08 07 06 C3",
            "FF FF FF FF 00 00 00 00 D9 BD 60 BF 58 54 48 30 D0 2B F5 3E 00 00 00 00 00 00 80 3F 00 00 00 00 D0 2B F5 BE F0 A2 B7 B0 D9 BD 60 BF E3 4F 10 C2 10 FB 7B 40 D0 0F 02 C3",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 88 DE 08 31 C0 5A 29 B0 00 00 80 3F A4 BC 40 41 E7 AF 33 3E 9B FD F9 C1",
            "FF FF FF FF 00 00 00 00 A6 1F 9E 3E 2A 4C 37 3C 00 78 73 BF 25 95 B5 BD 4D F4 7E 3F D6 E3 8B BC E1 6C 72 3F A8 7E B7 3D 53 FC 9D 3E 8A DD C7 C1 C7 DE A1 BF 6C D1 96 41",
            "FF FF FF FF 00 00 00 00 D1 AB 32 3E 4D AB 21 3E C7 CF 78 3F 88 0D 90 BC 82 C6 7C 3F 13 03 21 BE 64 08 7C BF 87 7C 29 3C 76 43 33 3E 41 69 80 C2 14 10 76 41 72 B6 71 42",
            "FF FF FF FF 00 00 00 00 05 BC 12 3F 00 00 00 00 12 C6 51 3F B8 02 26 B3 00 00 80 3F A0 4F 93 32 12 C6 51 BF 00 00 00 00 05 BC 12 3F A3 18 5B 41 58 21 C0 40 D0 21 32 C1",
            "FF FF FF FF 00 00 00 00 34 65 DF BD 36 33 A5 BE 97 B1 70 BF DF BC 28 3E 29 49 6D 3F 31 A6 AC BE 9C F3 7A 3F 61 50 44 BE 0C 5A 44 BD E9 6E 84 C2 04 A3 FB 40 C4 D6 92 41",
            "FF FF FF FF 00 00 00 00 B1 FC 51 BF 63 82 C8 30 87 CB F9 BE 00 00 00 00 CE 52 74 3F 00 00 00 00 88 CB F9 3E A6 E1 77 B0 B0 FC 51 BF 13 58 75 42 73 87 C7 BE BA B7 56 42",
            "FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 BF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 2B 9E 16 40 F4 92 11 C2 CD FF 43 C3",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 78 8B 5C C1 C7 4B 73 41 A6 84 7D 42",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 60 1E 07 43 9E AE 43 C2 F3 F3 6C C2",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 F6 42 55 C2 E0 C1 D6 47 CD C3",
            "FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 35 2D DE 42 51 FB 29 41 CB 41 57 43"
        ],
        required=True,
        note="",
        max_allowed=1,
        follows=[(2, "immediate")],
        expected_offset=0x70,
    ),

    ## this header indicates a following 12 byte sequence that is often followed by the same header then another 12 however many times until it reaches the 'Unknown DataBlock header'
    ## these two patterns are the same section hence having the same ID they are, when present, in the same order so the follows remain correct regardless of which version is present
    PatternDef(
        id=4,
        name="Binary Block Data",
        patterns=[
            ## the 00 is the first instance of this section the 01 is all other section headers
            "00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F",
            "01 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F",
        ],
        required=False,
        note="Possible Header, found after the unknown binary data just before texture data and mesh",
        max_allowed=1,
        # After 3, otherwise after 2, otherwise after 1
        follows=[(3, "after")],
    ),
    PatternDef(
        id=4,
        name="Binary Block Data v2",
        pattern=(
            # these two strings are one long pattern
            "00 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 ** 00 00 00 2D 00 02 1C 1E 01 00 00 ** 00 00 00 2D 00 02 1C 00 01 00 00 00 00 00 00 ** 00 00 00 "
            "02 80 03 00 00 00 00 00 ** ** ** ** 00 00 00 00 00 00 00 00 E9 1D BC 49 01 00 00 00 00 00 00 00 DC F6 DC 6E 02 00 00 00 00 00 00 00 ** ** ** ** 03 00 00 00 ** 00 00 00 ",
        ),
        EOSPattern=(
            "FF FF FF FF 07 00 00 00 E8 00 00 00 2D 00 02 1C 01 00 00 00 1C 00 00 00 2D 00 02 1C 00 00 00 00 FF FF FF FF 00 00 ** 18 01 00 00 00 00 00 80 3F 00 00 80 3F 00 00 80 3F 06 00 00 00 50 00 00 00 2D 00 02 1C 01 00 00 00 04 00 00 00 2D 00 02 1C ",
        ),
        required=False,
        note="alternative version of the SOF Binary Block Data",
        max_allowed=1,
        # After 3, otherwise after 2, otherwise after 1
        follows=[(3, "after")],
    ),

    ## these mark an unknown segment of data before the texturs after the SOF and after an unknown binary block often seen right after SOF
    ## these two patterns appear mostly in .rws files and in very few .dff
    PatternDef(
        id=5,
        name="Unknown DataBlock header",
        patterns=[
            ## two possible versions
            "01 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 18 00 00 00 2D 00 02 1C 1E 01 00 00 0C 00 00 00 2D 00 02 1C 00 01 00 00 00 00 00 00 00 00 00 00 03 00 00 00 18 00 00 00 2D 00 02 1C 1E 01 00 00 0C 00 00 00 2D 00 02 1C ",
            "00 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 00 00 00 00 2D 00 02 1C"
        ],
        required=False,
        note="found after the unknown binary data just before texture data and mesh",
        max_allowed=1,
        # Typically after #4 block data; fallback to after #1
        follows=[(4, "after"), (2, "after")],
    ),

    ## the textures are stored seperately in .txd dictionaryies that contain the files referenced as string file names here

    # === String/Name-related markers (from FIXED_SIGNATURES_TO_CHECK) ===
    # === Pre-Texture Names / Texture Data boundary ===
    PatternDef(
        id=6,
        name="Pre-texture names marker String Block Header (General, 8B) ",
        patterns=[
            "02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C",
            "02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C",
            "02 11 01 00 02 00 00 00 10 00 00 00 2D 00 02 1C",
        ],
        required=False,
        note="Observed before texture string names. // Fixed signature before embedded string(s); string usually starts +0x10.",
        max_allowed=0,  # max observed was 297
        # Usually appears after the unknown block (#5); fallback to after earlier anchors
        follows=[(5, "after"), (4, "after"), (2, "after")],
    ),
    # the purpose of this data is unknown but its likly texture mapping or other texture to mesh meta data
    PatternDef(
        id=7,
        name="TLFD (Texture Data start)",
        pattern="54 4C 46 44",
        required=False,
        note="Marks end of string names and start of Texture Data.",
        max_allowed=0,  # max observed was 138
        # Texture data starts after names (#6); allow fallback
        follows=[(6, "after"), (5, "after"), (4, "after"), (2, "after")],
    ),

    # === Mesh-chunk scanning (from mshBytes regex) ===
    PatternDef(
        id=8,
        name="Mesh chunk header",
        pattern="33 EA 00 00 ** ** ** ** 2D 00 02 1C",
        required=False,
        note="Header used to locate mesh chunks before reading counts/offsets.",
        max_allowed=0,
        # Mesh chunks appear after prior headers/blocks
        follows=[(7, "after"), (6, "after"), (2, "after")],
    ),

    # === Face/strip parsing delimiter ===
    #PatternDef(
    #    name="Triangle strip delimiter",
    #    pattern="FF FF",
    #    required=False,
    #    note="Index delimiter between strips (very common; non-unique).",
    #    max_allowed=0,
    #),

    # === EOF region ===
    PatternDef(
        id=9,
        name="EOF marker",
        pattern="16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00",
        required=True,
        note="Expected near EOF (search after SOF segment).",
        max_allowed=1,
        # EOF should be after everything else
        follows=[(8, "after"), (7, "after"), (6, "after"), (5, "after"), (4, "after"), (2, "after")],
    ),
]


# ===== Implementation =====

@dataclass
class CompiledVariant:
    patt: bytes
    mask: bytes
    # Optional label for analytics/debug; not used in output to keep format stable
    label: str = ""
    # Optional compiled EOS pattern and mask
    eos_patt: Optional[bytes] = None
    eos_mask: Optional[bytes] = None
    # Compiled regex equivalents for fast scanning
    rx: Optional[re.Pattern] = None
    eos_rx: Optional[re.Pattern] = None


@dataclass
class CompiledSegment:
    id: int
    name: str
    required: bool
    note: str
    variants: List[CompiledVariant]
    max_allowed: int
    follows: Optional[List[Tuple[int, str]]]
    expected_offset: Optional[int] = None


def iter_target_files(root: str) -> Iterable[str]:
    """Yield files under root whose suffix matches TARGET_SUFFIXES (case-insensitive)."""
    root = os.path.abspath(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(TARGET_SUFFIXES):
                yield os.path.join(dirpath, name)


def read_prefix(path: str, n: int) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def to_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def _parse_wildcard_pattern(pat: str) -> Tuple[bytes, bytes]:
    """Parse space-separated hex with **/?? wildcards into (pattern, mask)."""
    p: List[int] = []
    m: List[int] = []
    for raw_tok in pat.replace("\n", " ").split():
        tok = raw_tok.strip()
        if not tok:
            continue
        if tok in ("**", "??"):
            p.append(0)
            m.append(0)  # wildcard
            continue
        if len(tok) != 2:
            raise ValueError(f"invalid token length in pattern: {tok!r}")
        try:
            val = int(tok, 16)
        except ValueError:
            raise ValueError(f"invalid hex token in pattern: {tok!r}") from None
        p.append(val)
        m.append(0xFF)
    if not p:
        raise ValueError("pattern parsed to empty bytes")
    return bytes(p), bytes(m)


def _to_bytes_regex(patt: bytes, mask: bytes) -> re.Pattern:
    """Convert a masked pattern into a compiled bytes regex.

    Mask byte 0 means wildcard; non-zero means fixed and must match exactly.
    """
    parts: List[bytes] = []
    for pb, mb in zip(patt, mask):
        if mb == 0:
            parts.append(b".")  # wildcard any byte
        else:
            parts.append(re.escape(bytes([pb])))
    return re.compile(b"".join(parts), re.DOTALL)


def compile_pattern_defs(defs: List[PatternDef]) -> List[CompiledSegment]:
    """Compile pattern definitions into segments grouped by id.

    Multiple PatternDef entries with the same id are treated as alternative
    subformats of the same logical segment and merged as labeled variants under
    a single CompiledSegment. This preserves dependency semantics across
    subformats without changing output formatting.
    """
    grouped: Dict[int, List[PatternDef]] = {}
    order: List[int] = []
    for d in defs:
        if d.id not in grouped:
            grouped[d.id] = []
            order.append(d.id)
        grouped[d.id].append(d)

    out: List[CompiledSegment] = []
    for sid in order:
        defs_for_id = grouped[sid]
        base_name = defs_for_id[0].name
        base_note = defs_for_id[0].note
        required = any(d.required for d in defs_for_id)
        max_allowed = max((d.max_allowed for d in defs_for_id), default=0)
        exp_off: Optional[int] = None
        for d in defs_for_id:
            if d.expected_offset is not None and exp_off is None:
                exp_off = d.expected_offset
        # Merge follows in order, de-duplicated
        follows: Optional[List[Tuple[int, str]]] = None
        for d in defs_for_id:
            if d.follows:
                if follows is None:
                    follows = list(d.follows)
                else:
                    for item in d.follows:
                        if item not in follows:
                            follows.append(item)

        variants: List[CompiledVariant] = []
        for d in defs_for_id:
            patt_sources: List[Tuple[str, str]] = []  # (pattern, label)
            if d.patterns:
                for idx, s in enumerate(d.patterns):
                    patt_sources.append((s, f"{d.name} [alt {idx}]"))
            if d.pattern is not None:
                if isinstance(d.pattern, (list, tuple)):
                    patt_sources.append((" ".join(d.pattern), d.name))
                else:
                    patt_sources.append((d.pattern, d.name))
            if not patt_sources:
                raise ValueError(f"PatternDef {d.id} ({d.name}) has no pattern(s)")
            # Compile EOS once per definition, if present
            eos_patt: Optional[bytes] = None
            eos_mask: Optional[bytes] = None
            eos_rx: Optional[re.Pattern] = None
            if d.EOSPattern:
                eos_src: str
                if isinstance(d.EOSPattern, (list, tuple)):
                    eos_src = " ".join(d.EOSPattern)
                else:
                    eos_src = d.EOSPattern
                eos_patt, eos_mask = _parse_wildcard_pattern(eos_src)
                eos_rx = _to_bytes_regex(eos_patt, eos_mask)
            for s, label in patt_sources:
                patt, mask = _parse_wildcard_pattern(s)
                rx = _to_bytes_regex(patt, mask)
                variants.append(CompiledVariant(
                    patt=patt,
                    mask=mask,
                    label=label,
                    eos_patt=eos_patt,
                    eos_mask=eos_mask,
                    rx=rx,
                    eos_rx=eos_rx,
                ))

        out.append(
            CompiledSegment(
                id=sid,
                name=base_name,
                required=required,
                note=base_note,
                variants=variants,
                max_allowed=max_allowed,
                follows=follows,
                expected_offset=exp_off,
            )
        )

    out.sort(key=lambda s: s.id)
    return out


def _find_masked(data: bytes, patt: bytes, mask: bytes, start: int = 0) -> int:
    need = len(patt)
    if need == 0:
        return start
    limit = len(data) - need
    for i in range(start, max(-1, limit) + 1):
        seg = data[i:i + need]
        # quick-check first masked byte
        if (seg[0] & mask[0]) != (patt[0] & mask[0]):
            continue
        ok = True
        for db, pb, mb in zip(seg, patt, mask):
            if (db & mb) != (pb & mb):
                ok = False
                break
        if ok:
            return i
    return -1


def _find_all_masked(data: bytes, patt: bytes, mask: bytes) -> List[int]:
    pos = 0
    found: List[int] = []
    step = max(1, len(patt))
    while True:
        i = _find_masked(data, patt, mask, pos)
        if i < 0:
            break
        found.append(i)
        pos = i + step  # non-overlapping per-variant
    return found


def _filter_first_occurrence_after_follows(
    compiled: List[CompiledSegment],
    all_positions: Dict[int, List[Tuple[int, int]]],
) -> Dict[int, List[Tuple[int, int]]]:
    """For singleton segments (max_allowed==1), keep only the first relevant occurrence.

    - If the segment has 'follows', select the first occurrence satisfying the
      active parent relation. Active parent = first listed parent that exists
      (prefer already-selected occurrence; else earliest occurrence).
    - If no listed parents exist or no follows, pick the first occurrence.
    - Non-singleton segments remain unchanged.
    """
    selected: Dict[int, Optional[Tuple[int, int]]] = {}
    filtered: Dict[int, List[Tuple[int, int]]] = {}

    def _parent_first(pid: int) -> Optional[Tuple[int, int]]:
        pos = all_positions.get(pid) or []
        return pos[0] if pos else None

    for seg in compiled:
        pos_list = all_positions.get(seg.id, [])
        if not pos_list:
            selected[seg.id] = None
            filtered[seg.id] = []
            continue
        if seg.max_allowed != 1:
            filtered[seg.id] = pos_list
            selected[seg.id] = pos_list[0]
            continue

        chosen: Optional[Tuple[int, int]] = None
        if seg.follows:
            active_parent: Optional[Tuple[int, int]] = None
            active_rel: Optional[str] = None
            for pid, rel in seg.follows:
                psel = selected.get(pid)
                if psel is None:
                    psel = _parent_first(pid)
                if psel is not None:
                    active_parent = psel
                    active_rel = rel
                    break
            if active_parent is not None and active_rel is not None:
                p_start, p_len = active_parent
                p_end = p_start + p_len
                if active_rel == "immediate":
                    for c_start, c_len in pos_list:
                        if c_start == p_end:
                            chosen = (c_start, c_len)
                            break
                else:  # 'after'
                    for c_start, c_len in pos_list:
                        if c_start >= p_end:
                            chosen = (c_start, c_len)
                            break
        if chosen is None:
            chosen = pos_list[0]

        filtered[seg.id] = [chosen]
        selected[seg.id] = chosen

    return filtered


def collect_positions_per_segment(data: bytes, seg: CompiledSegment) -> Tuple[List[Tuple[int, int]], Dict[int, List[int]]]:
    """Return (positions, per_variant_positions) for a segment.

    positions: sorted list of (start, length) merged across variants.
    per_variant_positions: vidx -> list of start positions for that variant.
    """
    per_variant: Dict[int, List[int]] = {}
    merged: List[Tuple[int, int]] = []
    for vidx, v in enumerate(seg.variants):
        # Use compiled regex for fast scanning
        pos_list = [m.start() for m in v.rx.finditer(data)] if v.rx is not None else _find_all_masked(data, v.patt, v.mask)
        if pos_list:
            per_variant[vidx] = pos_list
            base_len = len(v.patt)
            # If EOS is available, use it to compute real segment length
            if v.eos_rx is not None or (v.eos_patt and v.eos_mask):
                eos_len = len(v.eos_patt) if v.eos_patt else 0
                for p in pos_list:
                    if v.eos_rx is not None:
                        m = v.eos_rx.search(data, p)
                        if m:
                            L = m.end() - p
                        else:
                            L = base_len
                    else:
                        eos_pos = _find_masked(data, v.eos_patt or b"", v.eos_mask or b"", start=p)
                        if eos_pos >= 0:
                            L = (eos_pos + eos_len) - p
                        else:
                            L = base_len
                    merged.append((p, L))
            else:
                merged.extend((p, base_len) for p in pos_list)
    merged.sort(key=lambda t: t[0])
    # Deduplicate identical start positions coming from different variants by keeping the max length
    dedup: List[Tuple[int, int]] = []
    last_start = None
    for s, L in merged:
        if last_start is None or s != last_start:
            dedup.append((s, L))
            last_start = s
        else:
            # same start from another variant: keep longer
            if L > dedup[-1][1]:
                dedup[-1] = (s, L)
    return dedup, per_variant


@dataclass
class FileMatchResult:
    path: str
    ok: bool
    reason: str
    per_segment_counts: Dict[str, int]
    dependency_errors: List[str]
    # Enhanced outputs for richer reporting (parity with check7)
    head_hex: str = ""
    matched_segments: Optional[List[str]] = None
    matched_segments_first_start: Optional[Dict[str, int]] = None
    classification: str = ""
    # variant_keys: segment_name -> variant_idx -> Counter(hexkey -> count)
    variant_keys: Optional[Dict[str, Dict[int, Counter]]] = None
    ordering_status: str = ""  # ORDER_OK | ORDER_MISMATCH | NO_TEXTURE | NO_MESH
    num_textures: int = 0
    num_meshes: int = 0
    textures_with_later_mesh: int = 0
    textures_after_last_mesh: int = 0
    earliest_texture_pos: Optional[int] = None
    earliest_mesh_pos: Optional[int] = None
    # New: raw start offsets per segment id (for cross-file offset stats)
    segment_offsets: Optional[Dict[int, List[int]]] = None


def _enforce_dependencies(
    compiled: List[CompiledSegment],
    all_positions: Dict[int, List[Tuple[int, int]]],
) -> Tuple[bool, List[str]]:
    """Check dependency constraints for all segments.

    Returns (ok, errors).
    Rules:
      - If a pattern has 'follows': choose the first parent in the list that exists in the file
        (has any occurrence). This becomes the active constraint.
      - If a parent exists, then the child must have at least one occurrence
        satisfying the relation to some occurrence of that parent:
           immediate: child_start == parent_start + parent_len
           after:     child_start >= parent_start + parent_len
      - If none of the listed parents exist, the dependency is not enforced for that child.
    """
    errors: List[str] = []
    # Build quick lookup of existence and end positions for parents
    exists: Dict[int, bool] = {seg.id: bool(all_positions.get(seg.id)) for seg in compiled}
    parent_end_positions: Dict[int, List[int]] = {
        seg.id: [(s + L) for (s, L) in all_positions.get(seg.id, [])] for seg in compiled
    }

    for seg in compiled:
        if not seg.follows:
            continue
        child_pos = all_positions.get(seg.id, [])
        # If the child doesn't exist at all, dependency will be handled by 'required' elsewhere.
        if not child_pos:
            # If the child isn't present, we can't check dependency; skip here.
            continue
        # pick the first parent rule whose parent exists
        active_rule: Optional[Tuple[int, str]] = None
        for pid, rel in seg.follows:
            if exists.get(pid, False):
                active_rule = (pid, rel)
                break
        if not active_rule:
            # no listed parents exist in the file; nothing to enforce
            continue
        pid, rel = active_rule
        ends = parent_end_positions.get(pid, [])
        if not ends:
            # Defensive: shouldn't happen if exists[pid] is True
            continue
        ok_for_this_child = False
        for c_start, c_len in child_pos:
            for pend in ends:
                if rel == "immediate":
                    if c_start == pend:
                        ok_for_this_child = True
                        break
                else:  # 'after'
                    if c_start >= pend:
                        ok_for_this_child = True
                        break
            if ok_for_this_child:
                break
        if not ok_for_this_child:
            parent_names = {s.id: s.name for s in compiled}
            errors.append(
                f"Dependency not satisfied: '{seg.name}' must follow {rel} '{parent_names.get(pid, str(pid))}'"
            )
    return (len(errors) == 0), errors


def check_file(path: str, compiled: List[CompiledSegment]) -> FileMatchResult:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return FileMatchResult(path, False, f"read error: {e}", {}, [f"read error: {e}"])

    # collect raw positions per segment
    all_positions_raw: Dict[int, List[Tuple[int, int]]] = {}
    per_segment_counts: Dict[str, int] = {}
    required_missing: List[str] = []
    for seg in compiled:
        pos, _per_variant = collect_positions_per_segment(data, seg)
        all_positions_raw[seg.id] = pos
        per_segment_counts[seg.name] = len(pos)
        if seg.required and len(pos) == 0:
            required_missing.append(seg.name)

    # Build offset list per segment id (list of start positions)
    segment_offsets: Dict[int, List[int]] = {}
    for seg in compiled:
        positions = all_positions_raw.get(seg.id, [])
        if positions:
            segment_offsets[seg.id] = [s for (s, _L) in positions]

    # Filter to first occurrence for singleton segments honoring 'follows'
    all_positions = _filter_first_occurrence_after_follows(compiled, all_positions_raw)

    dep_ok, dep_errors = _enforce_dependencies(compiled, all_positions)
    ok = (len(required_missing) == 0) and dep_ok
    reason_parts: List[str] = []
    if required_missing:
        # Build detailed missing message, including expected-offset hex previews
        miss_msgs: List[str] = []
        for name in required_missing:
            miss_msgs.append(name)
        reason_parts.append("missing required: " + ", ".join(miss_msgs))
        # For each missing compiled segment that has an expected_offset, include a 56-byte hex dump
        previews: List[str] = []
        for seg in compiled:
            if seg.name in required_missing and seg.expected_offset is not None:
                off = seg.expected_offset
                if 0 <= off < len(data):
                    snippet = data[off: off + 56]
                    previews.append(f"{seg.name} @0x{off:08X}: {to_hex(snippet)}")
                else:
                    previews.append(f"{seg.name} @0x{off:08X}: (offset out of range)")
        if previews:
            reason_parts.append("preview: " + " | ".join(previews))
    if not dep_ok and dep_errors:
        reason_parts.extend(dep_errors)
    reason = "; ".join(reason_parts)

    # === Enhanced analytics to match check7 outputs ===
    # Classification heuristics
    def _classify_file(payload: bytes, p: str) -> str:
        name = os.path.basename(p).lower()
        has_mesh_sig = (b"\x33\xEA\x00\x00" in payload) and (b"\x2D\x00\x02\x1C" in payload)
        has_tlfd = b"TLFD" in payload
        tok_renderless = any(t in name for t in ("bound","collision","col","icb","nopathseek","placeholder","fragment"))
        id1 = payload[:2048].count(b"\x00\x00\x80\x3F")
        looks_renderless = (not has_mesh_sig) and (not has_tlfd) and id1 >= 12
        if has_mesh_sig:
            return "RENDERABLE"
        if tok_renderless or looks_renderless:
            return "RENDERLESS"
        return "CONTAINER"

    classification = _classify_file(data, path)

    # head hex for quick debugging
    head_hex = to_hex(data[: min(256, len(data))])

    # Matched segment names and first start map
    matched_segments = [seg.name for seg in compiled if per_segment_counts.get(seg.name, 0) > 0]
    matched_segments_first_start: Dict[str, int] = {}
    for seg in compiled:
        positions = all_positions_raw.get(seg.id, [])
        if positions:
            matched_segments_first_start[seg.name] = positions[0][0]

    # Variant wildcard enumeration per segment/variant
    def _wildcard_indices(mask: bytes) -> List[int]:
        return [i for i, mb in enumerate(mask) if mb == 0]

    def _collect_variant_keys_for_variant(payload: bytes, patt: bytes, mask: bytes, rx: Optional[re.Pattern]) -> Counter:
        wc_idx = _wildcard_indices(mask)
        if rx is not None:
            positions = [m.start() for m in rx.finditer(payload)]
        else:
            positions = _find_all_masked(payload, patt, mask)
        c: Counter = Counter()
        if not wc_idx:
            if positions:
                c["(no-wildcards)"] = len(positions)
            return c
        for pos in positions:
            key_bytes = bytes(payload[pos + j] for j in wc_idx)
            c[key_bytes.hex()] += 1
        return c

    per_segment_variant_keys: Dict[str, Dict[int, Counter]] = {}
    for seg in compiled:
        alt: Dict[int, Counter] = {}
        for vidx, v in enumerate(seg.variants):
            c = _collect_variant_keys_for_variant(data, v.patt, v.mask, v.rx)
            if c:
                alt[vidx] = c
        if alt:
            per_segment_variant_keys[seg.name] = alt

    # Texture vs Mesh ordering analysis
    # Use segment ids from PATTERN_DEFS: 6 (names), 7 (TLFD), 8 (mesh)
    texture_positions: List[int] = []
    for sid in (6, 7):
        for s, _L in all_positions_raw.get(sid, []):
            texture_positions.append(s)
    texture_positions = sorted(set(texture_positions))
    mesh_positions = sorted([s for (s, _L) in all_positions_raw.get(8, [])])

    num_textures = len(texture_positions)
    num_meshes = len(mesh_positions)
    earliest_texture_pos = texture_positions[0] if texture_positions else None
    earliest_mesh_pos = mesh_positions[0] if mesh_positions else None
    textures_with_later_mesh = 0
    textures_after_last_mesh = 0
    if num_textures > 0 and num_meshes > 0:
        last_mesh = mesh_positions[-1]
        for tpos in texture_positions:
            if any(mpos > tpos for mpos in mesh_positions):
                textures_with_later_mesh += 1
        textures_after_last_mesh = sum(1 for tpos in texture_positions if tpos > last_mesh)
    elif num_textures > 0 and num_meshes == 0:
        textures_after_last_mesh = num_textures

    if num_textures == 0:
        ordering_status = "NO_TEXTURE"
    elif num_meshes == 0:
        ordering_status = "NO_MESH"
    elif textures_with_later_mesh == num_textures:
        ordering_status = "ORDER_OK"
    else:
        ordering_status = "ORDER_MISMATCH"

    # Relaxation heuristic for renderless containers: allow EOF-only successes
    if not ok:
        eof_cnt = per_segment_counts.get("EOF marker", 0)
        name_hint = os.path.basename(path).lower()
        name_screams_renderless = any(hint in name_hint for hint in (
            "bound", "collision", "col", "icb", "nopathseek", "placeholder", "fragment"
        ))
        id1 = data[:1024].count(b"\x00\x00\x80\x3F")
        has_mesh_sig = (b"\x33\xEA\x00\x00" in data) and (b"\x2D\x00\x02\x1C" in data)
        has_tlfd = (b"TLFD" in data)
        looks_renderless = (not has_mesh_sig) and (not has_tlfd) and (id1 >= 12)
        is_renderless = (classification == "RENDERLESS") or looks_renderless or name_screams_renderless
        if is_renderless and eof_cnt > 0:
            ok = True
            if reason:
                reason += "; "
            reason += "relaxed: renderless container with EOF present"

    return FileMatchResult(
        path=path,
        ok=ok,
        reason=reason,
        per_segment_counts=per_segment_counts,
        dependency_errors=dep_errors,
        head_hex=head_hex,
        matched_segments=matched_segments,
        matched_segments_first_start=matched_segments_first_start,
        classification=classification,
        variant_keys=per_segment_variant_keys,
        ordering_status=ordering_status,
        num_textures=num_textures,
        num_meshes=num_meshes,
        textures_with_later_mesh=textures_with_later_mesh,
        textures_after_last_mesh=textures_after_last_mesh,
        earliest_texture_pos=earliest_texture_pos,
        earliest_mesh_pos=earliest_mesh_pos,
        segment_offsets=segment_offsets,
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate preinstanced PS3 files with dependency-aware pattern matching")
    p.add_argument("path", nargs="?", default=".", help="Root folder to scan")
    p.add_argument("--workers", "-j", type=int, default=None, help="Number of worker processes to use (default: CPU count). Use 1 to disable multiprocessing.")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    root = args.path
    try:
        compiled = compile_pattern_defs(PATTERN_DEFS)
    except ValueError as e:
        print(f"Pattern parse error: {e}")
        return 3

    files = list(iter_target_files(root))
    total = len(files)
    failures = 0
    passes = 0

    # Aggregators similar to check7
    per_segment_found: Dict[str, int] = {}
    per_segment_max_in_file: Dict[str, int] = {}
    classification_counts: Dict[str, int] = {}
    # pattern -> variant_idx -> Counter
    global_variant_keys: Dict[str, Dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    total_occurrences_by_pattern: Dict[str, int] = defaultdict(int)
    ordering_counts: Dict[str, int] = defaultdict(int)
    files_with_textures = 0
    textures_total = 0
    textures_with_later_mesh_total = 0
    # Mesh aggregation
    meshes_total = 0
    max_meshes_in_file = 0
    min_meshes_in_file: Optional[int] = None
    # Aggregate start offsets across files for segments without expected offsets
    segment_offset_hist: Dict[int, Counter] = defaultdict(Counter)  # seg_id -> Counter(offset -> count)

    def _progress_write(msg: str, stream=None) -> None:
        if stream is None:
            stream = sys.stdout
        if stream.isatty():
            # Move to start of line and clear it
            stream.write('\r\x1b[K')
            # Optionally trim/pad to terminal width
            width = shutil.get_terminal_size((80, 20)).columns
            stream.write(msg[:width-1])
            stream.flush()
        else:
            # If output is piped, fall back to newline updates
            stream.write(msg + '\n')
            stream.flush()

    print(f"Scanning: {os.path.abspath(root)}")
    print(f"Target suffixes: {', '.join(TARGET_SUFFIXES)}")
    seg_info = ", ".join(f"#{s.id} {s.name}" for s in compiled)
    print(f"Segments: {seg_info}")
    print(f"Found {total} file(s)\n")

    # Initialize per-segment counters
    for seg in compiled:
        per_segment_found[seg.name] = 0
        per_segment_max_in_file[seg.name] = 0

    # Decide on multiprocessing
    workers = args.workers if args.workers and args.workers > 0 else (os.cpu_count() or 1)
    use_mp = workers > 1 and total > 1

    def handle_result(idx: int, path: str, res: FileMatchResult):
        nonlocal failures, passes, files_with_textures, textures_total, textures_with_later_mesh_total, meshes_total, max_meshes_in_file, min_meshes_in_file
        if res.ok:
            passes += 1
            #print(f"PASS [{idx}/{total}] {path}")
        else:
            failures += 1
            print(f"FAIL [{idx}/{total}] {path} :: {res.reason}")
            if res.head_hex:
                print("  head:", res.head_hex)

        _progress_write(f"{idx}/{total}")

        # Per-segment coverage and occurrences
        for seg in compiled:
            cnt = res.per_segment_counts.get(seg.name, 0)
            if cnt > 0:
                per_segment_found[seg.name] += 1
            if cnt > per_segment_max_in_file[seg.name]:
                per_segment_max_in_file[seg.name] = cnt
            total_occurrences_by_pattern[seg.name] += cnt

        # Classification
        cls = res.classification or "(unknown)"
        classification_counts[cls] = classification_counts.get(cls, 0) + 1

        # Variant keys merge
        if res.variant_keys:
            for pname, altmap in res.variant_keys.items():
                for vidx, counter in altmap.items():
                    global_variant_keys[pname][vidx].update(counter)

        # Offsets aggregation (only for segments without expected_offset)
        if res.segment_offsets:
            for seg in compiled:
                if seg.expected_offset is None:
                    offs = res.segment_offsets.get(seg.id, [])
                    if offs:
                        segment_offset_hist[seg.id].update(offs)

        # Ordering aggregation
        ord_status = res.ordering_status or "(unknown)"
        ordering_counts[ord_status] = ordering_counts.get(ord_status, 0) + 1
        if res.num_textures > 0:
            files_with_textures += 1
            textures_total += res.num_textures
            textures_with_later_mesh_total += res.textures_with_later_mesh
        # Mesh counts aggregation
        meshes_total += res.num_meshes
        if res.num_meshes > max_meshes_in_file:
            max_meshes_in_file = res.num_meshes
        if min_meshes_in_file is None or res.num_meshes < min_meshes_in_file:
            min_meshes_in_file = res.num_meshes

    if use_mp:
        _progress_write(f"Using {workers} workers...\n")
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(check_file, p, compiled) for p in files]
            for idx, fut in enumerate(as_completed(futures), 1):
                path = files[idx - 1] if idx - 1 < len(files) else "(unknown)"
                try:
                    res = fut.result()
                except Exception as e:
                    failures += 1
                    print(f"FAIL [{idx}/{total}] {path} :: worker error: {e}")
                    continue
                handle_result(idx, path, res)
    else:
        for idx, path in enumerate(files, 1):
            res = check_file(path, compiled)
            handle_result(idx, path, res)

    overall_status = "OK" if failures == 0 else "ERROR"

    print()
    print("Summary:")
    print("  Pattern coverage:")
    for seg in compiled:
        found = per_segment_found.get(seg.name, 0)
        missing = total - found
        max_in_file = per_segment_max_in_file.get(seg.name, 0)
        req_flag = "required" if seg.required else "optional"
        print(f"    - {seg.name}: files with ≥1 = {found}, missing = {missing}, max occurrences in a file = {max_in_file} ({req_flag})")
    print(f"  All required patterns OK: {passes}/{total}")
    print(f"  Long SOF pattern: {overall_status} - {passes} pass, {failures} fail, {total} total")

    # Variant enumeration summary
    print()
    print("Variant enumeration (wildcard instantiations):")
    for seg in compiled:
        pname = seg.name
        altmap = global_variant_keys.get(pname, {})
        total_occ = total_occurrences_by_pattern.get(pname, 0)
        unique_keys_total = sum(len(c) for c in altmap.values())
        print(f"  - {pname}: total occurrences={total_occ}, unique instantiated keys across variants={unique_keys_total}")
        for vidx, counter in altmap.items():
            top_items = counter.most_common(3)
            tops = ", ".join(f"{k}:{v}" for k, v in top_items) if top_items else "(none)"
            variant_label = seg.variants[vidx].label if vidx < len(seg.variants) else f"variant[{vidx}]"
            last_four = seg.variants[vidx].patt[-4:].hex().upper() if vidx < len(seg.variants) and len(seg.variants[vidx].patt) >= 4 else "N/A"
            first_four = seg.variants[vidx].patt[:4].hex().upper() if vidx < len(seg.variants) and len(seg.variants[vidx].patt) >= 4 else "N/A"
            print(f"      {variant_label}: unique={len(counter)}; first4bytes={first_four}; last4bytes={last_four}; top3: {tops}")

    # Classification summary
    if total > 0:
        print()
        print("Classification summary:")
        for k in sorted(classification_counts.keys()):
            print(f"  {k}: {classification_counts[k]}")

    # Ordering summary
    if total > 0:
        print()
        print("Texture/Mesh ordering summary:")
        for k in ("ORDER_OK", "NO_TEXTURE", "NO_MESH", "ORDER_MISMATCH", "(unknown)"):
            if k in ordering_counts:
                print(f"  {k}: {ordering_counts[k]}")
        if files_with_textures > 0:
            pct = (textures_with_later_mesh_total / textures_total * 100.0) if textures_total else 0.0
            print(f"  Files with textures: {files_with_textures}  (textures total: {textures_total}; textures with later mesh: {textures_with_later_mesh_total} = {pct:.1f}% )")

    # Mesh counts summary
    if total > 0:
        print()
        print("Mesh counts:")
        print(f"  Total meshes across all files: {meshes_total}")
        print(f"  Max meshes in a single file: {max_meshes_in_file}")
        min_meshes_display = min_meshes_in_file if min_meshes_in_file is not None else 0
        print(f"  Min meshes in a single file: {min_meshes_display}")

    # Offsets summary for segments without expected offsets
    if total > 0:
        print()
        print("Offsets summary (segments without expected_offset):")
        for seg in compiled:
            if seg.expected_offset is not None:
                continue
            hist = segment_offset_hist.get(seg.id)
            if not hist:
                continue
            uniq = len(hist)
            top5 = hist.most_common(5)
            tops = ", ".join(f"0x{off:X}:{cnt}" for off, cnt in top5) if top5 else "(none)"
            print(f"  - {seg.name}: unique offsets={uniq}; top5: {tops}")

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))



