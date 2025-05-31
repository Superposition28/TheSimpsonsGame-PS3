-- Main table for .str archive files
CREATE TABLE IF NOT EXISTS str_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,           -- Combined hash (file+path) acting as a unique ID
    source_file_name TEXT,             -- Original filename of the .str file
    source_path TEXT UNIQUE NOT NULL,  -- Relative path of the .str file within STR_INPUT_DIR
    file_hash TEXT,                  -- SHA256 hash of the .str file content
    path_hash TEXT                   -- MD5 hash of the source_path
);

-- Table for .preinstanced files (example of a dynamically named table)
CREATE TABLE IF NOT EXISTS preinstanced_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,           -- Combined hash (file+path)
    source_file_name TEXT,             -- Original filename
    source_path TEXT NOT NULL,         -- Relative path (either from STR_INPUT_DIR or OUTPUT_BASE_DIR)
    file_hash TEXT,                  -- SHA256 hash of the file content
    path_hash TEXT,                  -- MD5 hash of the source_path
    group_name TEXT                    -- From EXT_GROUPS (e.g., "models")
);

-- Table for .txd files
CREATE TABLE IF NOT EXISTS txd_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "textures"
);

-- Table for .vp6 files
CREATE TABLE IF NOT EXISTS vp6_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "videos"
);

-- Table for .snu files
CREATE TABLE IF NOT EXISTS snu_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "audio"
);

-- Table for .mus files
CREATE TABLE IF NOT EXISTS mus_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "audio" (Corrected based on script's EXT_GROUPS)
);

-- Table for .lua files
CREATE TABLE IF NOT EXISTS lua_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "other"
);

-- Table for .bin files
CREATE TABLE IF NOT EXISTS bin_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "other"
);

-- Table for .txt files
CREATE TABLE IF NOT EXISTS txt_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT                    -- "other"
);

-- Table for .dds files (referenced by txd_dds_relationship and str_content_relationship)
CREATE TABLE IF NOT EXISTS dds_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,           -- Relative path (within the <txd_name>_txd folder or extracted content)
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT DEFAULT 'textures_dds', -- "textures_dds"
    phash TEXT,                          -- Grayscale Perceptual Hash
    dhash TEXT,                          -- Grayscale Difference Hash
    ahash TEXT,                          -- Grayscale Average Hash
    color_phash TEXT,                    -- Color Perceptual Hash (concatenated channel hashes)
    color_dhash TEXT,                    -- Color Difference Hash (combined channel hashes)
    color_ahash TEXT                     -- Color Average Hash (combined channel hashes)
);

-- Table for files with unknown/unlisted extensions
CREATE TABLE IF NOT EXISTS unknown_index ( -- Name derived from get_table_name_for_ext("unknown")
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    source_file_name TEXT,
    source_path TEXT NOT NULL,
    file_hash TEXT,
    path_hash TEXT,
    group_name TEXT DEFAULT 'unknown'    -- Default value set
);

-- Relationship table linking .str archives to their extracted content files
CREATE TABLE IF NOT EXISTS str_content_relationship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    str_uuid TEXT NOT NULL,              -- UUID from str_index
    content_file_uuid TEXT NOT NULL,     -- UUID from one of the <ext>_index tables or unknown_index
    content_file_table TEXT NOT NULL,    -- Name of the table where content_file_uuid is stored (e.g., "txd_index", "dds_index")
    FOREIGN KEY (str_uuid) REFERENCES str_index(uuid) ON DELETE CASCADE,
    UNIQUE (str_uuid, content_file_uuid, content_file_table)
);

-- Relationship table linking .txd files to their constituent .dds files
CREATE TABLE IF NOT EXISTS txd_dds_relationship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txd_uuid TEXT NOT NULL,              -- UUID from txd_index
    dds_uuid TEXT NOT NULL,              -- UUID from dds_index
    FOREIGN KEY (txd_uuid) REFERENCES txd_index(uuid) ON DELETE CASCADE,
    FOREIGN KEY (dds_uuid) REFERENCES dds_index(uuid) ON DELETE CASCADE,
    UNIQUE (txd_uuid, dds_uuid)
);

-- Pragmas enabled by the script
-- PRAGMA foreign_keys = ON;