import os
import sys
from PIL import Image, UnidentifiedImageError
import imagehash

import config
from core_utils import sha256_file, md5_string, generate_uuid
from db import operations as db_ops
from db.schema import get_table_name_for_ext

def calculate_image_hashes(img_path: str) -> dict:
    """Calculates various image hashes for a given image file."""
    hashes = {
        "phash": None, "dhash": None, "ahash": None,
        "color_phash": None, "color_dhash": None, "color_ahash": None
    }
    try:
        img = Image.open(img_path)

        # Grayscale Hashes
        img_gray = None
        if img.mode != 'L':
            try:
                img_gray = img.convert('L')
            except ValueError as e:
                print(f"        WARNING: Could not convert image {img_path} to grayscale: {e}", file=sys.stderr)
        else:
            img_gray = img
        
        if img_gray:
            hashes["phash"] = str(imagehash.phash(img_gray, hash_size=config.PHASH_IMG_SIZE))
            hashes["dhash"] = str(imagehash.dhash(img_gray, hash_size=config.DHASH_IMG_SIZE))
            hashes["ahash"] = str(imagehash.average_hash(img_gray, hash_size=config.AHASH_IMG_SIZE))

        # Color Hashes
        img_rgb = None
        if img.mode not in ('RGB', 'RGBA'):
            try:
                img_rgb = img.convert('RGB')
            except ValueError as e:
                print(f"        WARNING: Could not convert image {img_path} to RGB for color hashing: {e}", file=sys.stderr)
        else:
            img_rgb = img.convert('RGB') # Ensure RGBA is converted to RGB

        if img_rgb:
            try:
                hashes["color_ahash"] = str(imagehash.average_hash(img_rgb, hash_size=config.AHASH_IMG_SIZE))
                hashes["color_dhash"] = str(imagehash.dhash(img_rgb, hash_size=config.DHASH_IMG_SIZE))
                
                # Color pHash (concatenating R, G, B channel phashes)
                phash_r = imagehash.phash(img_rgb.getchannel('R'), hash_size=config.PHASH_IMG_SIZE)
                phash_g = imagehash.phash(img_rgb.getchannel('G'), hash_size=config.PHASH_IMG_SIZE)
                phash_b = imagehash.phash(img_rgb.getchannel('B'), hash_size=config.PHASH_IMG_SIZE)
                hashes["color_phash"] = str(phash_r) + str(phash_g) + str(phash_b)
            except Exception as e:
                print(f"        WARNING: Failed to calculate some color hashes for {img_path}: {e}", file=sys.stderr)
        
        img.close()
    except FileNotFoundError:
        print(f"        ERROR: Image file not found for hashing: {img_path}", file=sys.stderr)
    except UnidentifiedImageError:
        print(f"        WARNING: Could not identify/load image {img_path} for hashing (corrupted/unsupported).", file=sys.stderr)
    except Exception as e:
        print(f"        ERROR: Processing image {img_path} for hashing: {e}", file=sys.stderr)
    return hashes

def index_dds_file(conn,
                   full_file_path: str,
                   rel_path_for_db: str) -> str | None:
    """
    Indexes a DDS file, including calculating and storing various image hashes.

    Args:
        conn: Active SQLite database connection.
        full_file_path: The absolute path to the DDS file on disk.
        rel_path_for_db: The relative path string to be stored in the database.

    Returns:
        The UUID of the indexed DDS file, or None if indexing failed.
    """
    table_name = get_table_name_for_ext(".dds")
    group_name = config.EXT_GROUPS.get(".dds", "textures_dds")

    file_hash = sha256_file(full_file_path)
    if file_hash is None:
        print(f"    Failed to get SHA256 hash for DDS: {full_file_path}", file=sys.stderr)
        return None

    path_hash_content = rel_path_for_db
    path_hash = md5_string(path_hash_content)
    file_uuid = generate_uuid(file_hash, path_hash)

    image_hashes = calculate_image_hashes(full_file_path)

    data_to_insert = {
        "uuid": file_uuid,
        "source_file_name": os.path.basename(full_file_path),
        "source_path": rel_path_for_db,
        "file_hash": file_hash,
        "path_hash": path_hash,
        "group_name": group_name,
        **image_hashes # Spread the image hash dictionary
    }

    inserted_uuid = db_ops.insert_file_entry(conn, table_name, data_to_insert)

    if inserted_uuid == file_uuid:
        print(f"    Indexed DDS: {rel_path_for_db} (UUID: {file_uuid})")
    elif inserted_uuid:
        print(f"    Found existing DDS: {rel_path_for_db} (UUID: {inserted_uuid})")
    else:
        print(f"    Failed to index/find DDS: {rel_path_for_db}", file=sys.stderr)
        return None

    return inserted_uuid