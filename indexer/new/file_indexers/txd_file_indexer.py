import os
import sys
import config
from core_utils import get_relative_path
from db import operations as db_ops # For relationship creation
from file_indexers.generic_file_indexer import index_generic_file # TXD is a generic file type initially
from file_indexers.dds_file_indexer import index_dds_file         # For indexing DDS files found within TXD context
from relationship_builder import add_txd_dds_relationship

def process_txd_contained_dds_files(conn,
                                    txd_file_uuid: str,
                                    txd_file_full_path: str,
                                    # Base directory for calculating relative paths of the DDS files
                                    # This could be STR_INPUT_DIR or an extraction output directory.
                                    dds_files_rel_path_base_dir: str):
    """
    Processes DDS files found in the conventional folder (<txd_name>_txd)
    associated with a given TXD file.
    These DDS files are indexed, and their relationship with the TXD file is recorded.

    Args:
        conn: Active SQLite database connection.
        txd_file_uuid: The UUID of the parent TXD file.
        txd_file_full_path: Absolute path to the parent TXD file.
        dds_files_rel_path_base_dir: The directory against which the relative paths of
                                     the found DDS files should be calculated for DB storage.
                                     For root TXDs, this is STR_INPUT_DIR.
                                     For extracted TXDs, this is OUTPUT_BASE_DIR.
    """
    txd_filename_no_ext = os.path.splitext(os.path.basename(txd_file_full_path))[0]
    # The _txd folder is expected to be ADJACENT to the .txd file,
    # or within an extraction structure that mimics this.
    # If TXDs are extracted from STRs, their _txd folders will be relative to the STR's extraction path.
    
    # If the TXD is in STR_INPUT_DIR, its _txd is also expected there.
    # If the TXD is in OUTPUT_BASE_DIR/some_extraction_path, its _txd is there.
    parent_dir_of_txd = os.path.dirname(txd_file_full_path)
    dds_folder_name = txd_filename_no_ext + "_txd"
    dds_folder_full_path = os.path.join(parent_dir_of_txd, dds_folder_name)

    if not os.path.isdir(dds_folder_full_path):
        # print(f"        Info: DDS folder not found for {os.path.basename(txd_file_full_path)} at: {dds_folder_full_path}")
        return

    print(f"        Processing DDS files for {os.path.basename(txd_file_full_path)} in: {dds_folder_full_path}")
    for dds_root, _, dds_filenames in os.walk(dds_folder_full_path):
        for dds_filename in dds_filenames:
            if dds_filename.lower().endswith(".dds"):
                full_dds_file_path = os.path.join(dds_root, dds_filename)
                
                # Relative path for the DDS file for DB storage.
                # This should make the DDS path unique and identifiable.
                dds_rel_path_for_db = get_relative_path(full_dds_file_path, dds_files_rel_path_base_dir)

                dds_file_uuid = index_dds_file(conn, full_dds_file_path, dds_rel_path_for_db)
                if dds_file_uuid and txd_file_uuid:
                    add_txd_dds_relationship(conn, txd_file_uuid, dds_file_uuid)
                # else:
                    # print(f"            Skipping TXD-DDS relationship for {dds_filename} due to indexing failure or missing TXD UUID.")


def index_txd_file(conn,
                   full_file_path: str,
                   rel_path_for_db: str,
                   # Base dir for any DDS files that might be found alongside this TXD
                   # (e.g. STR_INPUT_DIR if this TXD is a root file, or
                   # OUTPUT_BASE_DIR if this TXD was extracted from an STR).
                   associated_dds_rel_path_base: str) -> str | None:
    """
    Indexes a TXD file and then processes any associated DDS files.

    Args:
        conn: Active SQLite database connection.
        full_file_path: Absolute path to the TXD file.
        rel_path_for_db: Relative path for storing the TXD file in the database.
        associated_dds_rel_path_base: The base directory for calculating relative paths
                                      of DDS files found in the <txd_name>_txd folder.

    Returns:
        The UUID of the indexed TXD file, or None if failed.
    """
    file_ext = ".txd"
    group_name = config.EXT_GROUPS.get(file_ext, "textures")

    # 1. Index the TXD file itself as a generic file
    print(f"    Indexing TXD: {rel_path_for_db}")
    txd_file_uuid = index_generic_file(conn,
                                       full_file_path,
                                       rel_path_for_db,
                                       file_ext,
                                       group_name)

    if not txd_file_uuid:
        print(f"    Failed to index TXD file: {full_file_path}. Skipping associated DDS processing.", file=sys.stderr)
        return None

    # 2. Process associated DDS files (if any)
    # The _txd folder is expected to be in the same directory as the .txd file itself.
    process_txd_contained_dds_files(conn, txd_file_uuid, full_file_path, associated_dds_rel_path_base)

    return txd_file_uuid