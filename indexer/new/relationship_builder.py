import os
import sys
from db import operations as db_ops
from db.schema import get_table_name_for_ext # To get table names for relationship logging or validation

# --- STR to Content Relationship --- (Existing)
def add_str_content_relationship(conn, str_archive_uuid: str, content_file_uuid: str, content_file_table_name: str):
    """Records a relationship between an STR archive and an extracted content file."""
    if not str_archive_uuid or not content_file_uuid or not content_file_table_name:
        return
    relationship_data = {
        "str_uuid": str_archive_uuid,
        "content_file_uuid": content_file_uuid,
        "content_file_table": content_file_table_name
    }
    if not db_ops.insert_relationship_entry(conn, "str_content_relationship", relationship_data):
        print(f"        Failed to add STR-Content relationship: STR {str_archive_uuid} -> {content_file_table_name}:{content_file_uuid}", file=sys.stderr)

# --- TXD to DDS Relationship --- (Existing)
def add_txd_dds_relationship(conn, txd_file_uuid: str, dds_file_uuid: str):
    """Records a relationship between a TXD file and an extracted DDS file."""
    if not txd_file_uuid or not dds_file_uuid:
        return
    relationship_data = {
        "txd_uuid": txd_file_uuid,
        "dds_uuid": dds_file_uuid
    }
    if not db_ops.insert_relationship_entry(conn, "txd_dds_relationship", relationship_data):
        print(f"        Failed to add TXD-DDS relationship: TXD {txd_file_uuid} -> DDS {dds_file_uuid}", file=sys.stderr)

# --- Blend to Preinstanced Relationship --- (Existing)
def add_blend_preinstanced_relationship(conn, blend_file_uuid: str, preinstanced_file_uuid: str):
    """Records a relationship between a .blend file and its source .preinstanced file."""
    if not blend_file_uuid or not preinstanced_file_uuid:
        return
    relationship_data = {
        "blend_uuid": blend_file_uuid,
        "preinstanced_uuid": preinstanced_file_uuid
    }
    if not db_ops.insert_relationship_entry(conn, "blend_preinstanced_relationship", relationship_data):
        print(f"        Failed to add Blend-Preinstanced relationship: Blend {blend_file_uuid} -> Preinstanced {preinstanced_file_uuid}", file=sys.stderr)

# --- GLB/FBX (Model Export) to Blend Relationship --- (Existing)
def add_model_export_blend_relationship(conn, exported_model_uuid: str, exported_model_table: str, blend_file_uuid: str):
    """Records a relationship between an exported model (.glb, .fbx) and its source .blend file."""
    if not exported_model_uuid or not blend_file_uuid or not exported_model_table:
        return
    relationship_data = {
        "exported_model_uuid": exported_model_uuid,
        "exported_model_table": exported_model_table,
        "blend_uuid": blend_file_uuid
    }
    if not db_ops.insert_relationship_entry(conn, "model_export_blend_relationship", relationship_data):
        print(f"        Failed to add ModelExport-Blend relationship: {exported_model_table}:{exported_model_uuid} -> Blend {blend_file_uuid}", file=sys.stderr)

# --- SNU to WAV Relationship --- (New Function)
def add_snu_wav_relationship(conn, snu_file_uuid: str, wav_file_uuid: str):
    """Records a relationship between an .snu file and its corresponding .wav file."""
    if not snu_file_uuid or not wav_file_uuid:
        print(f"        Skipping SNU-WAV relationship due to missing UUID(s). SNU: {snu_file_uuid}, WAV: {wav_file_uuid}", file=sys.stderr)
        return

    relationship_data = {
        "snu_uuid": snu_file_uuid,
        "wav_uuid": wav_file_uuid
    }
    snu_wav_table_name = "snu_wav_relationship" # As defined in db.schema.py
    if not db_ops.insert_relationship_entry(conn, snu_wav_table_name, relationship_data):
        print(f"        Failed to add SNU-WAV relationship: SNU {snu_file_uuid} -> WAV {wav_file_uuid}", file=sys.stderr)
    # else:
    #     print(f"        Added SNU-WAV relationship: SNU {snu_file_uuid} -> WAV {wav_file_uuid}")


# --- Function to Process Relationships WITHIN an Extracted STR Directory --- (Updated)
def process_relationships_in_extracted_dir(conn, extracted_content_map: dict):
    """
    Processes known file relationships (e.g., Blend <-> Preinstanced, GLB/FBX <-> Blend, SNU <-> WAV)
    based on the files found and indexed within a single STR extraction.

    Args:
        conn: Active SQLite database connection.
        extracted_content_map: A dictionary mapping file extensions to another dictionary,
                               which maps `rel_path_within_extraction` to `uuid`.
            Example: {
                '.blend': {'models/character.blend': 'uuid1', ...},
                '.preinstanced': {'models/character.preinstanced': 'uuid2', ...},
                '.glb': {'exports/character.glb': 'uuid3', ...},
                '.snu': {'audio/sound.snu': 'uuid_snu1', ...},
                '.wav': {'audio/sound.wav': 'uuid_wav1', ...}
            }
    """
    print("    Processing inter-file relationships for content within the current STR extraction...")

    # 1. Blend to Preinstanced Relationship
    if '.blend' in extracted_content_map and '.preinstanced' in extracted_content_map:
        blends = extracted_content_map['.blend']
        preinstanced_files = extracted_content_map['.preinstanced']
        matches = 0
        for blend_rel_path, blend_uuid in blends.items():
            expected_preinstanced_rel_path = os.path.splitext(blend_rel_path)[0] + ".preinstanced"
            if expected_preinstanced_rel_path in preinstanced_files:
                preinstanced_uuid = preinstanced_files[expected_preinstanced_rel_path]
                add_blend_preinstanced_relationship(conn, blend_uuid, preinstanced_uuid)
                matches +=1
        if matches > 0:
            print(f"        Found and processed {matches} Blend <-> Preinstanced relationships.")

    # 2. GLB/FBX to Blend Relationship
    model_export_exts = ['.glb', '.fbx']
    if '.blend' in extracted_content_map:
        blends = extracted_content_map['.blend']
        matches = 0
        for ext_type in model_export_exts:
            if ext_type in extracted_content_map:
                exported_models = extracted_content_map[ext_type]
                export_table_name = get_table_name_for_ext(ext_type)
                for model_rel_path, model_uuid in exported_models.items():
                    expected_blend_rel_path = os.path.splitext(model_rel_path)[0] + ".blend"
                    if expected_blend_rel_path in blends:
                        blend_uuid = blends[expected_blend_rel_path]
                        add_model_export_blend_relationship(conn, model_uuid, export_table_name, blend_uuid)
                        matches +=1
        if matches > 0:
            print(f"        Found and processed {matches} Model Export <-> Blend relationships.")

    # 3. SNU to WAV Relationship (New Section)
    #    Assumes .wav is named after .snu and in the same relative path within this extraction.
    if '.snu' in extracted_content_map and '.wav' in extracted_content_map:
        snu_files = extracted_content_map['.snu']
        wav_files = extracted_content_map['.wav']
        matches = 0
        for snu_rel_path, snu_uuid in snu_files.items():
            # Example: snu_rel_path could be "sounds/level1/music.snu"
            # We expect wav_rel_path to be "sounds/level1/music.wav"
            expected_wav_rel_path = os.path.splitext(snu_rel_path)[0] + ".wav"

            if expected_wav_rel_path in wav_files:
                wav_uuid = wav_files[expected_wav_rel_path]
                add_snu_wav_relationship(conn, snu_uuid, wav_uuid)
                matches += 1
        if matches > 0:
            print(f"        Found and processed {matches} SNU <-> WAV relationships.")

    # Add other relationship processing logic here for other types as needed.