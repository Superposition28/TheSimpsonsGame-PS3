"""Compare TXD texture counts and validate exported PNGs in two asset trees.

Run from the repository root with:
    python EngineApps/Games/TheSimpsonsGame-PS3/reversing/validate_txd_exports.py \
        EngineApps/Games/TheSimpsonsGame-PS3/GameFiles/EU-FullFlattened-audio_og-isRenamed \
        EngineApps/Games/TheSimpsonsGame-PS3/GameFiles/EU-TEST-audio_og-isRenamed
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    from PIL import Image
except ImportError as error:
    raise SystemExit("Pillow is required. Install it with: python -m pip install Pillow") from error


TEXTURE_NAME_SIGNATURE = bytes.fromhex("2D00021C0000000A")


def find_files(root: Path, extension: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == extension
    )


def count_txd_textures(txd_files: list[Path]) -> tuple[int, list[str]]:
    texture_count = 0
    errors: list[str] = []

    for txd_file in txd_files:
        try:
            texture_count += txd_file.read_bytes().count(TEXTURE_NAME_SIGNATURE)
        except OSError as error:
            errors.append(f"Could not read TXD {txd_file}: {error}")

    return texture_count, errors


def validate_png(png_file: Path) -> str | None:
    try:
        with Image.open(png_file) as image:
            if image.format != "PNG":
                return f"Unexpected image format {image.format!r}"
            image.verify()

        with Image.open(png_file) as image:
            image.load()
            if image.width <= 0 or image.height <= 0:
                return f"Invalid dimensions {image.width}x{image.height}"
    except Exception as error:
        return str(error)

    return None


def validate_tree(label: str, root: Path) -> tuple[int, int, int, list[str]]:
    if not root.is_dir():
        return 0, 0, 0, [f"{label}: directory does not exist: {root}"]

    txd_files = find_files(root=root, extension=".txd")
    png_files = find_files(root=root, extension=".png")
    texture_count, errors = count_txd_textures(txd_files=txd_files)
    invalid_pngs: list[str] = []

    for png_file in png_files:
        validation_error = validate_png(png_file=png_file)
        if validation_error is not None:
            invalid_pngs.append(f"Invalid PNG {png_file}: {validation_error}")

    if not txd_files:
        errors.append(f"{label}: no TXD files found under {root}")
    if texture_count != len(png_files):
        errors.append(
            f"{label}: TXDs contain {texture_count} texture signatures, "
            f"but the tree contains {len(png_files)} PNG files"
        )

    print(
        f"{label}: TXDs={len(txd_files)}, texture records={texture_count}, "
        f"PNGs={len(png_files)}, invalid PNGs={len(invalid_pngs)}"
    )
    return texture_count, len(png_files), len(invalid_pngs), errors + invalid_pngs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare TXD texture-record and PNG counts, then decode every PNG."
    )
    parser.add_argument("reference_root", type=Path, help="Reference asset tree to validate")
    parser.add_argument("test_root", type=Path, help="New test asset tree to validate")
    arguments = parser.parse_args()

    reference = validate_tree(label="Reference", root=arguments.reference_root)
    test = validate_tree(label="Test", root=arguments.test_root)
    errors = reference[3] + test[3]

    if reference[0] != test[0]:
        errors.append(
            f"Reference and test TXDs contain different texture-record totals "
            f"({reference[0]} vs {test[0]})"
        )
    if reference[1] != test[1]:
        errors.append(
            f"Reference and test trees contain different PNG totals "
            f"({reference[1]} vs {test[1]})"
        )

    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print(f"Validation failed with {len(errors)} issue(s).")
        return 1

    print("Validation passed: TXD record counts match PNG totals and all PNGs decode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())