import os

# --- Core Paths ---
# IMPORTANT: Adjust these paths to your actual environment
BASE_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Source directory for game files
STR_INPUT_DIR = r"Source\USRDIR"
# Base output directory for extracted files
OUTPUT_BASE_DIR = r"GameFiles\STROUT"
# Path to the SQLite database file
DB_PATH = r"RemakeRegistry\Games\TheSimpsonsGame\GameFilesIndex_Modular3.db"

# Tools
QUICKBMS_EXE = r"Tools\QuickBMS\exe\quickbms.exe"
BMS_SCRIPT = r"RemakeRegistry\Games\TheSimpsonsGame\Scripts\simpsons_str.bms"

# --- File Extension Groupings & Table Mapping ---
# Defines how file extensions are grouped and which primary table they might map to.
# Specific table names are generated in db.schema
EXT_GROUPS = {
    ".str": "Archive_root",       # STR archives, containing all non root files
    ".preinstanced": "models_source",
    ".blend": "models_blend",   # Blender files
    ".glb": "models_glb",       # GLB files
    ".fbx": "models_fbx",       # FBX files
    ".txd": "texture_dictionary",         # Texture dictionary files
    ".vp6": "video_source",
    ".snu": "audio_source",
    ".mus": "audio_other",
    ".lua": "other",
    ".bin": "other",
    ".txt": "other",
    ".dds": "textures_dds",     # DDS textures (often extracted from TXD or STR)
    ".wav": "audio_wav",       # WAV files
	".ogv": "video_ogv",       # OGV files
}

# --- Hashing Parameters ---
PHASH_IMG_SIZE = 8
DHASH_IMG_SIZE = 8
AHASH_IMG_SIZE = 8

# --- Database Parameters ---
MAX_DB_RETRIES = 5
RETRY_DELAY_SEC = 1

# --- Path Normalization Helper (Optional but recommended) ---
def_abs_path = lambda p: os.path.join(BASE_PROJECT_DIR, p) if not os.path.isabs(p) else p

# Ensure paths are absolute or relative to a known base if needed
# Example: DB_PATH = def_abs_path(DB_PATH) if you want it relative to project root
# For this refactor, we'll assume the user sets them as absolute or correctly relative.

# --- Logging Configuration (Placeholder) ---
LOG_LEVEL = "INFO"
LOG_FILE = "file_processor.log"