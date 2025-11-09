# Original Path Tracking in FullFlattened Mode

## Overview

In `FullFlattened` mode, the indexer now tracks **both** the flattened path and the inferred original hierarchical path for each file. This enables cross-referencing between different index types (Full, FullFlattened, SourceOnly).

## Database Schema Addition

```sql
CREATE TABLE {table_name} (
    ...
    source_path TEXT UNIQUE NOT NULL,      -- Flattened path (actual location on disk)
    original_path TEXT,                     -- Inferred original hierarchical path
    ...
);
```

## Path Tracking Strategy

### 1. Files in Flatten Map JSON
For files that existed before flattening (`.str`, `.txd`, `.preinstanced`, etc.):
- **source_path**: The flattened path where the file actually exists
- **original_path**: Directly from the flatten map JSON

Example:
```
source_path:   Assets_2_Frontend/misc/misc/texture_dictionary_misc__K6qivwu6v3lfrontend_global.txd
original_path: Assets_2_Frontend/frontend_global_str/build/PS3/pal_en/assets_rws/frontend/frontend/texture_dictionary/frontend_global.txd
```

### 2. Generated Files (Not in JSON)
For files generated after flattening (`.blend`, `.glb`, `.wav`, `.ogv`, `.png`):
- **source_path**: Current flattened location
- **original_path**: Inferred based on source file's original path

#### Model Pipeline Example
```
Preinstanced (in JSON):
  source_path:   Map_3-01/models/char__K123homer.preinstanced
  original_path: Map_3-01/levels/loc_str/models/homer.preinstanced

Blend (generated, inferred):
  source_path:   Map_3-01/models/char__K123homer.blend
  original_path: Map_3-01/levels/loc_str/models/homer.blend  ← Inferred!

GLB (generated, inferred):
  source_path:   Map_3-01/models/char__K123homer.glb
  original_path: Map_3-01/levels/loc_str/models/homer.glb    ← Inferred!
```

#### Audio Conversion Example
```
SNU (may be in JSON):
  source_path:   Assets_1_Audio_Streams/music/theme.snu
  original_path: Assets_1_Audio_Streams/audiostreams_str/music/sfx/theme.snu

WAV (generated, inferred):
  source_path:   Assets_1_Audio_Streams/music/theme.wav
  original_path: Assets_1_Audio_Streams/audiostreams_str/music/sfx/theme.wav  ← Inferred!
```

## Inference Algorithm

The `infer_original_path()` function uses these strategies:

### Extension Swap Inference
```python
ext_swap_map = {
    '.blend': '.preinstanced',
    '.glb': '.preinstanced',
    '.wav': '.snu',
    '.ogv': '.vp6',
    '.png': '.dds',
}
```

**Logic**:
1. Find the source file path (change extension)
2. Look up source file in flatten map
3. If found, swap extension on the original source path

### Archive Content Inference
For files in `_str/` or `_txd/` directories:

**Logic**:
1. Extract archive path (e.g., `frontend.str`)
2. Look up archive in flatten map
3. If found, reconstruct: `{original_archive_base}_str/{content_relative_path}`

## Use Cases

### Cross-Index Queries
Query files that exist in both Full and FullFlattened indexes:

```sql
-- Find matching files between indexes
SELECT 
    ff.source_path as flattened_path,
    ff.original_path as original_path,
    f.source_path as full_index_path,
    ff.file_hash,
    f.file_hash
FROM FullFlattened_db.preinstanced_index ff
JOIN Full_db.preinstanced_index f ON ff.original_path = f.source_path
WHERE ff.file_hash = f.file_hash;
```

### Path Comparison
Verify flattening consistency:

```sql
-- Files where original path differs from source path
SELECT 
    source_file_name,
    source_path,
    original_path
FROM preinstanced_index
WHERE source_path != original_path
ORDER BY original_path;
```

### Relationship Validation
Check that related files maintain their hierarchical relationships:

```sql
-- Verify blend files are in same directory as preinstanced in original structure
SELECT 
    p.original_path as pre_original,
    b.original_path as blend_original,
    p.source_path as pre_flattened,
    b.source_path as blend_flattened
FROM preinstanced_blend_relationship pbr
JOIN preinstanced_index p ON pbr.preinstanced_uuid = p.uuid
JOIN blend_index b ON pbr.blend_uuid = b.uuid
WHERE SUBSTR(p.original_path, 1, LENGTH(p.original_path) - 13) != 
      SUBSTR(b.original_path, 1, LENGTH(b.original_path) - 6);
```

## Benefits

1. **Index Compatibility**: Can cross-reference between Full and FullFlattened indexes
2. **Migration Support**: Helps migrate from hierarchical to flattened structure
3. **Debugging**: Easier to track file provenance and transformations
4. **Validation**: Verify that flattening preserved relationships correctly
5. **Tooling**: External tools can use original paths to understand file relationships

## Implementation Details

### Indexing Phase
```python
# During file indexing
original_path = None
if flatten_map:
    # Try direct lookup
    original_path = flatten_map.get_original_path(rel)
    # If not found, try inference
    if not original_path:
        original_path = infer_original_path(rel, ext, flatten_map)

# Store both paths
upsert_file(conn, table, full_path, rel_path, group, original_path)
```

### Relationship Phase
Original paths are automatically populated during relationship building when on-the-fly indexing occurs.

## Limitations

1. **Inference Accuracy**: Inferred paths assume standard naming conventions
2. **Source Files**: Files in input_dir have no original_path (they ARE the source)
3. **Manual Edits**: Manually moved/renamed files won't have accurate original paths
4. **Edge Cases**: Complex transformations may not infer correctly

## Future Enhancements

- Store transformation history (chain of paths)
- Track confidence level of inference
- Support custom inference rules per project
- Bidirectional path resolution (original → flattened lookup)
