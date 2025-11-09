# Simpsons Game File Indexer

## Overview

A comprehensive SQLite-based indexing system for The Simpsons Game assets that tracks file relationships across source, extracted, and converted formats.

## Features

- **Multi-Format Support**: Indexes 12+ file types including models, textures, audio, video
- **Relationship Tracking**: Maintains parent-child relationships between archives and contents
- **Three Index Modes**:
  - `SourceOnly`: Index only source files
  - `Full`: Index source + extracted files (hierarchical structure)
  - `FullFlattened`: Index source + flattened files (uses JSON mapping)
- **UUID-Based**: Content-addressable UUIDs combining file hash + path hash
- **Incremental Updates**: UPSERT logic prevents duplicate indexing

## Quick Start

### 1. Run with Config File (Recommended)
```bash
python test_fullflattened.py
```
Automatically reads settings from `config.toml`

### 2. Run Manually
```bash
python main.py \
  --region EU \
  --Type FullFlattened \
  --renamedBaseDirs isRenamed \
  --AudioReorg audio_reorg \
  --flatten-map-dir "A:\...\STROUT_Normalized"
```

## Index Types

### SourceOnly
- **Purpose**: Quick index of original game files only
- **Use Case**: Initial catalog, file discovery
- **Relationships**: None
- **Speed**: Fastest

### Full
- **Purpose**: Index source + extracted hierarchical files
- **Use Case**: Standard development workflow
- **Relationships**: All (STR→contents, TXD→DDS, format conversions, model pipeline)
- **Speed**: Moderate

### FullFlattened
- **Purpose**: Index source + flattened/reorganized files
- **Use Case**: Production builds, optimized asset layout
- **Relationships**: All (uses JSON mapping for path resolution)
- **Speed**: Moderate (includes JSON parsing overhead)
- **Requirements**: `flatten_map_*.json` files must exist

## Supported File Types

| Extension | Table | Purpose |
|-----------|-------|---------|
| `.str` | `str_index` | Archive files |
| `.txd` | `txd_index` | Texture dictionaries |
| `.dds` | `dds_index` | DirectDraw Surface textures |
| `.png` | `png_index` | Converted PNG images |
| `.preinstanced` | `preinstanced_index` | RenderWare model source |
| `.blend` | `blend_index` | Blender intermediate models |
| `.glb` | `glb_index` | glTF binary exported models |
| `.snu` | `snu_index` | Source audio files |
| `.wav` | `audio_wav_index` | Converted audio |
| `.mus` | `mus_index` | Music banks |
| `.vp6` | `video_index` | Source video files |
| `.ogv` | `video_ogv_index` | Converted video |
| Other | `other_files_index` | Misc files |

## Relationship Types

### Parent-Child Hierarchies
1. **STR → Content Files**: Archive extraction relationships
2. **TXD → DDS**: Texture dictionary contents

### Format Conversions (Extension Swap)
3. **SNU → WAV**: Audio conversion
4. **VP6 → OGV**: Video conversion
5. **DDS → PNG**: Texture conversion

### Model Pipeline (3-stage)
6. **Preinstanced → Blend → GLB**: Complete model conversion chain

## Database Schema

### File Index Tables
All file tables share this schema:
```sql
CREATE TABLE {table_name} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,           -- Content-addressable ID
    source_file_name TEXT,                -- Basename
    source_path TEXT UNIQUE NOT NULL,    -- Relative path
    file_hash TEXT,                       -- SHA256 of content
    path_hash TEXT,                       -- MD5 of path
    group_name TEXT,                      -- Categorization
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Relationship Tables
```sql
-- STR archives to contents
CREATE TABLE str_content_relationship (
    str_uuid TEXT NOT NULL,
    content_file_uuid TEXT NOT NULL,
    content_file_table TEXT NOT NULL
);

-- Texture dictionaries to textures
CREATE TABLE txd_dds_relationship (
    txd_uuid TEXT NOT NULL,
    dds_uuid TEXT NOT NULL
);

-- Format conversion relationships
CREATE TABLE snu_wav_relationship (...);
CREATE TABLE vp6_ogv_relationship (...);
CREATE TABLE dds_png_relationship (...);

-- Model pipeline relationships
CREATE TABLE preinstanced_blend_relationship (...);
CREATE TABLE glb_blend_relationship (...);
CREATE TABLE preinstanced_blend_glb_relationship (...);
```

## Configuration

### config.toml
```toml
[[placeholders]]
SourcePath = "A:\\...\\Source\\USRDIR"
Region = "EU"           # or "US"
isRenamed = "isRenamed" # or "notRenamed"
audio_state = "audio_reorg"  # or "audio_og"
Type = "normalized"     # maps to FullFlattened
STROUT = "STROUT_Normalized"
```

### Command Line Arguments
```
--region {EU,US}                    Region selector
--Type {Full,FullFlattened,SourceOnly}  Index type
--renamedBaseDirs {isRenamed,notRenamed}  Base dir naming
--AudioReorg {audio_reorg,audio_og}      Audio layout
--input-dir PATH                    Source directory
--output-dir PATH                   Extracted files directory
--blend-dir PATH                    Blend files directory
--flatten-map-dir PATH              Flatten map JSON directory (for FullFlattened)
```

## Database Output

Pattern: `GameFilesIndex_{region}_{type}-{audio}-{renamed}.db`

Examples:
- `GameFilesIndex_EU_FullFlattened-audio_reorg-isRenamed.db`
- `GameFilesIndex_US_Full-audio_og-notRenamed.db`
- `GameFilesIndex_US_SourceOnly-audio_og-isRenamed.db`

Location: `A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\config\`

## Querying the Database

### Find all files in an STR archive
```sql
SELECT cf.source_path, cf.source_file_name
FROM str_index si
JOIN str_content_relationship scr ON si.uuid = scr.str_uuid
JOIN {content_table} cf ON scr.content_file_uuid = cf.uuid
WHERE si.source_file_name = 'frontend.str';
```

### Find all textures from a TXD
```sql
SELECT d.source_path, d.file_hash
FROM txd_index t
JOIN txd_dds_relationship tdr ON t.uuid = tdr.txd_uuid
JOIN dds_index d ON tdr.dds_uuid = d.uuid
WHERE t.source_file_name = 'frontend_global.txd';
```

### Trace model conversion pipeline
```sql
SELECT 
    p.source_path as preinstanced,
    b.source_path as blend,
    g.source_path as glb
FROM preinstanced_blend_glb_relationship rel
JOIN preinstanced_index p ON rel.preinstanced_uuid = p.uuid
JOIN blend_index b ON rel.blend_uuid = b.uuid
JOIN glb_index g ON rel.glb_uuid = g.uuid;
```

## Documentation

- [`README_FullFlattened.md`](README_FullFlattened.md) - Detailed FullFlattened mode documentation
- [`README_TestScript.md`](README_TestScript.md) - Test script usage and integration

## Troubleshooting

### Missing base folders error
```
FATAL: Missing required base folders in Source (input-dir):
  A:\...\Assets_2_Frontend
```
**Solution**: Check `--renamedBaseDirs` parameter matches actual directory structure

### No flatten_map files found
```
FATAL: No flatten_map_*.json files found in A:\...\STROUT_Normalized
```
**Solution**: Run flattener first or specify correct `--flatten-map-dir`

### Relationship warnings
```
WARN: relation STR->content failed for frontend.str : ...
```
**Solution**: Extraction may be incomplete. Re-extract STR archives or ignore if expected.

## Performance

- **Indexing Speed**: ~1000-5000 files/second (depends on disk I/O)
- **Database Size**: ~100KB per 1000 files indexed
- **Memory Usage**: ~100-500MB peak (includes flatten map loading)
- **Query Performance**: Instant for most queries with proper indexes

## Requirements

- Python 3.8+
- No external dependencies (uses stdlib only)
- Optional: `tomli` for robust TOML parsing (Python <3.11)

## Future Enhancements

- [ ] Parallel indexing for faster processing
- [ ] Incremental updates (detect changed files only)
- [ ] Web UI for database browsing
- [ ] Export to other formats (CSV, JSON)
- [ ] Relationship validation and integrity checks
- [ ] Support for additional file types
