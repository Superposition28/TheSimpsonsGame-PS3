import os
import sys
import config
from core_utils import get_relative_path, ensure_dir_exists
from db import schema as db_schema, operations as db_ops
from file_indexers import (
    index_generic_file,
    index_dds_file,
    index_str_archive,
    index_txd_file
)
from extraction_manager import extract_str_file, get_extraction_output_dir
from relationship_builder import add_str_content_relationship, process_relationships_in_extracted_dir


def process_and_index_extracted_str_content(conn,
                                            parent_str_uuid: str,
                                            str_extraction_base_dir: str):
    """
    Scans an STR extraction directory, indexes its contents, and builds relationships.

    Args:
        conn: Active SQLite database connection.
        parent_str_uuid: UUID of the .str archive this content was extracted from.
        str_extraction_base_dir: The absolute path to the directory where the STR contents were extracted.
                                 (e.g., .../OUTPUT_BASE_DIR/path/to/original_str_file_str/)
    """
    if not parent_str_uuid:
        print(f"    ERROR: Cannot index extracted content from {str_extraction_base_dir} without parent STR UUID.", file=sys.stderr)
        return

    print(f"    Scanning and indexing content of STR extraction: {str_extraction_base_dir}")
    files_found_in_extraction = 0
    
    # For building relationships like .blend <-> .preinstanced within this extraction context
    # Key: file extension (e.g., '.blend'), Value: dict of {rel_path_in_extraction: uuid}
    indexed_content_details = {}

    for root, _, files in os.walk(str_extraction_base_dir):
        for file_name in files:
            files_found_in_extraction += 1
            full_file_path = os.path.join(root, file_name)
            file_ext = os.path.splitext(file_name)[1].lower()

            # Relative path for DB storage: relative to OUTPUT_BASE_DIR
            # This makes the path globally unique within the output structure.
            rel_path_for_db = get_relative_path(full_file_path, config.OUTPUT_BASE_DIR)

            # Relative path within this specific extraction, for finding related files
            # (e.g. a .blend and .preinstanced with the same relative path inside this _str folder)
            rel_path_within_extraction = get_relative_path(full_file_path, str_extraction_base_dir)

            group_name = config.EXT_GROUPS.get(file_ext, "unknown")
            content_file_uuid = None
            content_table_name = db_schema.get_table_name_for_ext(file_ext)

            if not file_ext: # Skip files with no extension, or handle as 'unknown'
                print(f"        Skipping file with no extension: {full_file_path}", file=sys.stderr)
                continue

            try:
                if file_ext == ".dds":
                    content_file_uuid = index_dds_file(conn, full_file_path, rel_path_for_db)
                elif file_ext == ".txd":
                    # For TXDs extracted from STRs, their _txd folders will be relative to OUTPUT_BASE_DIR
                    content_file_uuid = index_txd_file(conn, full_file_path, rel_path_for_db, config.OUTPUT_BASE_DIR)
                # Add elif for other specific indexers if they are not handled by generic_file_indexer logic
                # For example, if .blend files needed very special pre-processing before generic indexing.
                else: # Generic files including .blend, .preinstanced, .glb, .fbx, .lua, .bin, etc.
                      # STR and DDS are excluded by get_table_name_for_ext checks in generic_file_indexer
                    content_file_uuid = index_generic_file(conn, full_file_path, rel_path_for_db, file_ext, group_name)

                if content_file_uuid:
                    add_str_content_relationship(conn, parent_str_uuid, content_file_uuid, content_table_name)
                    
                    # Store details for intra-extraction relationship processing
                    if file_ext not in indexed_content_details:
                        indexed_content_details[file_ext] = {}
                    indexed_content_details[file_ext][rel_path_within_extraction] = content_file_uuid

            except Exception as e:
                print(f"    ERROR indexing extracted file {full_file_path}: {e}", file=sys.stderr)
                # Optionally, log to a file or raise if critical

    if files_found_in_extraction == 0:
        print(f"    Warning: No files found to index in extracted directory: {str_extraction_base_dir}", file=sys.stderr)
    else:
        # After all files in this extraction are indexed, process their internal relationships
        process_relationships_in_extracted_dir(conn, indexed_content_details)


def run_processing_passes(conn):
    """
    Runs the main processing passes:
    1. Scan STR_INPUT_DIR for root-level files (non-STR), index them.
       Handles TXD files and their associated _txd folders at this level.
    2. Scan STR_INPUT_DIR for .str archives, index them, extract if necessary,
       then index their contents and build relationships.
    """
    print(f"\n--- Pass 1: Indexing Root-Level Files (excluding .str) from: {config.STR_INPUT_DIR} ---")
    root_files_processed_count = 0
    for root_dir, _, dir_files in os.walk(config.STR_INPUT_DIR, topdown=True):
        # Skip the output directory itself to avoid processing already extracted files as root files
        abs_root_dir = os.path.abspath(root_dir)
        abs_output_base_dir = os.path.abspath(config.OUTPUT_BASE_DIR)
        if abs_root_dir.startswith(abs_output_base_dir):
            # print(f"    Skipping directory within OUTPUT_BASE_DIR: {root_dir}")
            continue
        
        print(f"Scanning root directory: {root_dir}")
        for file_item_name in dir_files:
            full_file_path = os.path.join(root_dir, file_item_name)
            file_ext = os.path.splitext(file_item_name)[1].lower()

            if not file_ext or file_ext == ".str": # Skip .str archives (Pass 2) and files without extensions
                continue

            root_files_processed_count +=1
            # Relative path for DB storage: relative to STR_INPUT_DIR for root files
            rel_path_for_db = get_relative_path(full_file_path, config.STR_INPUT_DIR)
            group_name = config.EXT_GROUPS.get(file_ext, "unknown")

            try:
                if file_ext == ".dds":
                    index_dds_file(conn, full_file_path, rel_path_for_db)
                elif file_ext == ".txd":
                    # For root TXDs, their _txd folders are relative to STR_INPUT_DIR
                    index_txd_file(conn, full_file_path, rel_path_for_db, config.STR_INPUT_DIR)
                else: # Other generic files
                    index_generic_file(conn, full_file_path, rel_path_for_db, file_ext, group_name)
            except Exception as e:
                print(f"    ERROR processing root file {full_file_path}: {e}", file=sys.stderr)
    print(f"--- Pass 1 Complete: Processed {root_files_processed_count} root files (excluding .str). ---\n")


    print(f"\n--- Pass 2: Processing .str Archives from: {config.STR_INPUT_DIR} ---")
    str_archives_processed_count = 0
    for root_dir, _, dir_files in os.walk(config.STR_INPUT_DIR, topdown=True):
        abs_root_dir = os.path.abspath(root_dir)
        abs_output_base_dir = os.path.abspath(config.OUTPUT_BASE_DIR)
        if abs_root_dir.startswith(abs_output_base_dir):
            continue

        for file_item_name in dir_files:
            if not file_item_name.lower().endswith(".str"):
                continue
            
            str_archives_processed_count += 1
            full_str_file_path = os.path.join(root_dir, file_item_name)
            
            # Relative path for DB storage (for the STR file itself): relative to STR_INPUT_DIR
            rel_str_path_for_db = get_relative_path(full_str_file_path, config.STR_INPUT_DIR)
            print(f"\nProcessing .str archive: {rel_str_path_for_db}")

            parent_str_uuid = index_str_archive(conn, full_str_file_path, rel_str_path_for_db)
            if not parent_str_uuid:
                print(f"    Failed to index or find .str archive: {rel_str_path_for_db}. Skipping content processing.", file=sys.stderr)
                continue
            
            # Determine expected extraction directory
            # str_extraction_output_dir is absolute path
            str_extraction_output_dir = get_extraction_output_dir(full_str_file_path, config.STR_INPUT_DIR, config.OUTPUT_BASE_DIR)

            if not str_extraction_output_dir:
                print(f"    Could not determine extraction output directory for {full_str_file_path}. Skipping extraction.", file=sys.stderr)
                continue

            extraction_needed = True
            if os.path.isdir(str_extraction_output_dir) and any(os.scandir(str_extraction_output_dir)):
                print(f"    Extraction directory already exists and is not empty: {str_extraction_output_dir}. Assuming already extracted.")
                extraction_needed = False # Skip extraction, proceed to indexing content
                extraction_successful = True
            
            if extraction_needed:
                print(f"    Attempting extraction for {rel_str_path_for_db}...")
                ensure_dir_exists(os.path.dirname(str_extraction_output_dir)) # Ensure parent of target extraction dir exists
                extraction_successful, actual_output_dir = extract_str_file(
                    str_file_path=full_str_file_path,
                    bms_script_path=config.BMS_SCRIPT,
                    quickbms_exe_path=config.QUICKBMS_EXE,
                    input_dir=config.STR_INPUT_DIR, # Base for calculating relative output structure
                    output_base_dir=config.OUTPUT_BASE_DIR
                )
                if actual_output_dir != str_extraction_output_dir: # Should ideally match
                    print(f"    WARNING: Mismatch in expected ({str_extraction_output_dir}) and actual ({actual_output_dir}) extraction dir.", file=sys.stderr)
                    # Decide how to handle: use actual_output_dir if extraction_successful
                    if extraction_successful: str_extraction_output_dir = actual_output_dir

            if extraction_successful:
                if os.path.isdir(str_extraction_output_dir): # Verify again after potential extraction
                    process_and_index_extracted_str_content(conn, parent_str_uuid, str_extraction_output_dir)
                else:
                    print(f"    WARNING: Extraction reported success for {rel_str_path_for_db}, but directory not found: {str_extraction_output_dir}", file=sys.stderr)
            else:
                print(f"    Skipping content indexing for {rel_str_path_for_db} due to extraction failure.", file=sys.stderr)

    print(f"--- Pass 2 Complete: Processed {str_archives_processed_count} .str archives. ---")