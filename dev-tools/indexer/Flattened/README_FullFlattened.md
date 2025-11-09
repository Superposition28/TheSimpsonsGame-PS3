# FullFlattened Indexer Mode

## Overview

The `FullFlattened` mode enables the indexer to correctly determine file relationships even when files have been "flattened" into simplified directory structures. This is essential because flattening removes the hierarchical path information that the indexer normally uses to infer relationships.

## Problem Statement

When files are extracted and organized hierarchically (e.g., `Full` mode):
```
Assets_2_Frontend/
  frontend_global_str/
    build/PS3/pal_en/assets_rws/frontend/frontend/texture_dictionary/
      frontend_global.txd
```

The path structure provides hints about relationships (e.g., files in `frontend_global_str/` came from `frontend_global.str`).

When flattened:
```
Assets_2_Frontend/
  misc/misc/
    texture_dictionary_misc__K6qivwu6v3lfrontend_global.txd
```

The original path context is lost, making relationship determination impossible without additional metadata.

## Solution: Flatten Map JSON Files

The flattener produces JSON mapping files that preserve the original→flattened path relationships:

```json
{
  "key": "6qivwu6v3l",
  "original_path": "Assets_2_Frontend\\frontend_global_str\\build\\PS3\\pal_en\\assets_rws\\frontend\\frontend\\texture_dictionary\\frontend_global.txd",
  "new_path": "Assets_2_Frontend\\misc\\misc\\texture_dictionary_misc__K6qivwu6v3lfrontend_global.txd",
  "base": "Assets_2_Frontend",
  "zone": "",
  "category": "misc",
  "purpose": "misc",
  "owner": "texture_dictionary",
  "asset": "texture_dictionary",
  "index": "",
  "ext": "frontend_global.txd"
}
```

## Implementation

### FlattenMapLoader Class

Loads all `flatten_map_*.json` files from a directory and builds bidirectional mappings:
- `new_to_original`: Lookup original paths from flattened paths
- `original_to_new`: Lookup flattened paths from original paths

### Relationship Logic Updates

All relationship functions now accept an optional `flatten_map` parameter:

#### 1. **STR Content Relationships** (`relate_str_contents`)
- Uses original path to determine the extraction directory pattern
- Falls back to flattened path if original extraction dir not found
- Links STR archives to their extracted contents

#### 2. **Extension Swap Relationships** (`relate_ext_swap`)
For file format conversions (e.g., `.snu` → `.wav`, `.vp6` → `.ogv`):
- Converts flattened source path → original source path
- Calculates original target path (swap extension)
- Converts original target path → flattened target path
- Creates relationship using flattened paths

#### 3. **Model Chain Relationships** (`relate_models_chain`)
For model pipeline (`.preinstanced` → `.blend` → `.glb`):
- Uses original path logic to find related files
- Handles cases where different formats may be in different locations

#### 4. **TXD-DDS Relationships** (`relate_txd_dds`)
- Uses original paths to understand texture archive structure
- Links texture dictionaries to extracted DDS textures

## Usage

### Command Line

```bash
python main.py \
  --region US \
  --Type FullFlattened \
  --renamedBaseDirs isRenamed \
  --AudioReorg audio_og \
  --flatten-map-dir "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT_Normalized"
```

### Auto-Detection

If `--flatten-map-dir` is not specified, the indexer attempts auto-detection:
- If `output_dir` ends with `STROUT`, tries `STROUT_Normalized`
- Otherwise uses `output_dir` directly

### Test Script

```bash
python test_fullflattened.py
```

## Flatten Map File Requirements

The indexer expects:
1. JSON files matching pattern: `flatten_map_*.json` (per base directory)
2. Each entry must have:
   - `original_path`: The hierarchical path before flattening
   - `new_path`: The flattened path after reorganization
3. Excludes:
   - `flatten_map.json` (monolithic file - too large)
   - `flatten_map_summary.json` (summary only)

## Database Output

Creates SQLite database with naming pattern:
```
GameFilesIndex_{region}_{index_type}-{audio_reorg}-{renamed_base_dirs}.db
```

Example:
```
GameFilesIndex_US_FullFlattened-audio_og-isRenamed.db
```

## Key Benefits

1. **Preserves Relationships**: Maintains all file relationships despite flattened structure
2. **Performance**: Loads all mappings once at startup for fast lookups
3. **Fallback Logic**: Tries both original and flattened paths for robustness
4. **Bidirectional**: Supports both forward and reverse path lookups

## Relationship Types Supported

| Relationship | Parent | Child | Logic |
|-------------|---------|-------|-------|
| STR Content | `.str` | `*` | Directory pattern match |
| TXD Textures | `.txd` | `.dds` | Directory pattern match |
| Audio Conversion | `.snu` | `.wav` | Extension swap + path map |
| Video Conversion | `.vp6` | `.ogv` | Extension swap + path map |
| Texture Conversion | `.dds` | `.png` | Extension swap + path map |
| Model Pipeline | `.preinstanced` | `.blend`, `.glb` | Extension swap + path map |

## Troubleshooting

### Warning: "No flatten_map_*.json files found"
- Ensure flatten map directory exists
- Check that JSON files follow naming convention
- Verify JSON files are not empty

### Warning: "relation failed for..."
- File may not have been flattened (exists only in original location)
- Flatten map may be incomplete
- Check that both source and target files were indexed

### Database is empty
- Verify `input_dir` and `output_dir` paths are correct
- Check that base directories exist and match rename configuration
- Review terminal output for indexing errors

## Performance Considerations

- **Memory**: Loads all path mappings into memory (typically < 100MB)
- **Startup**: Initial load of JSON files takes 1-5 seconds
- **Indexing**: Negligible overhead vs non-flattened mode
- **Queries**: No impact - same database schema

## Future Enhancements

Potential improvements:
1. Lazy loading of flatten maps (load only needed base directories)
2. Database caching of mappings
3. Incremental updates when flatten maps change
4. Validation of flatten map completeness
