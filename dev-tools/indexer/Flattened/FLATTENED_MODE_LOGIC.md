# FullFlattened Mode Relationship Logic

## Problem Statement

In `FullFlattened` mode, not all files are included in the flatten map JSON files:
- **In JSON**: Files that existed in STROUT before flattening (`.str`, `.txd`, `.preinstanced`, etc.)
- **NOT in JSON**: Files generated AFTER flattening (`.blend`, `.glb`, `.wav`, `.ogv`, `.png`)

This creates a challenge for determining relationships when target files aren't mapped.

## Solution Strategy

The script uses a **hybrid approach** that handles both mapped and unmapped files:

### 1. Files Generated Post-Flattening (blend, glb, wav, ogv, png)

These files are created in the **same directory structure** as their source files, which ARE in the JSON map.

#### Model Pipeline (preinstanced → blend → glb)
```
JSON contains:     frontend/models/homer.preinstanced
                   → Maps to → Assets_2_Frontend/models/character_models__Kabc123homer.preinstanced

Generated files:   Assets_2_Frontend/models/character_models__Kabc123homer.blend  (NOT in JSON)
                   Assets_2_Frontend/models/character_models__Kabc123homer.glb   (NOT in JSON)
```

**Logic**:
1. Get flattened `.preinstanced` path from state (already indexed from disk)
2. Calculate `.blend` and `.glb` paths by simple extension swap on the flattened path
3. Look up in state (they were indexed from disk walk)
4. **No JSON lookup needed for blend/glb!**

#### Audio/Video Conversion (snu → wav, vp6 → ogv)
```
Source files don't get reorganized, so:
   audiostreams/music/theme.snu → audiostreams/music/theme.wav
```

**Logic**:
1. Try to map source file through JSON (may or may not be mapped)
2. If target not in JSON map, fall back to simple extension swap
3. Audio/video stay in same relative locations, so this works

#### Texture Conversion (dds → png)
Similar to audio/video - generated alongside DDS files in the same structure.

### 2. Files in JSON (str, txd, preinstanced, etc.)

These use the JSON map for both source and target when both are mapped:

```
Original: frontend/frontend_str/textures/ui.txd
Mapped:   Assets_2_Frontend/ui/textures__K123ui.txd

Original: frontend/frontend_str/textures/ui_txd/background.dds  
Mapped:   Assets_2_Frontend/ui/textures__K123ui_txd/background.dds
```

## Code Implementation

### Extension Swap (relate_ext_swap)
```python
# 1. Simple extension swap on current (possibly flattened) path
rel_to = rel_from[:-len(from_ext)] + to_ext

# 2. If flatten map exists, try to use it
if flatten_map:
    original_from = flatten_map.get_original_path(rel_from)
    if original_from:
        original_to = original_from[:-len(from_ext)] + to_ext
        flattened_to = flatten_map.get_new_path(original_to)
        if flattened_to:
            rel_to = flattened_to
        # else: Not in map (generated file), use fallback from step 1

# 3. Look up target in state (indexed from disk)
uuid_to = dst_map.get(rel_to)
```

### Model Chain (relate_models_chain)
```python
# Preinstanced file path (from disk indexing - already flattened)
rel_pre = "Assets_2_Frontend/models/char__K123homer.preinstanced"

# Calculate related files in SAME directory
rel_blend = "Assets_2_Frontend/models/char__K123homer.blend"
rel_glb = "Assets_2_Frontend/models/char__K123homer.glb"

# Look up in state (both were indexed from disk)
uuid_blend = blend_map.get(rel_blend)  # Found!
uuid_glb = glb_map.get(rel_glb)        # Found!
```

## Why This Works

1. **All files are indexed from disk** via `walk_files()` regardless of JSON
2. **JSON is only used to map relationships**, not to discover files
3. **Generated files inherit their source's flattened location**, so simple extension swap works
4. **Fallback strategy**: If JSON doesn't have mapping, use simple path manipulation

## File Types Summary

| File Type | In JSON? | Relationship Strategy |
|-----------|----------|----------------------|
| `.str` | ✅ Yes | JSON map for extraction dir |
| `.txd` | ✅ Yes | JSON map for parent-child |
| `.dds` (from TXD) | ✅ Yes | JSON map for parent-child |
| `.preinstanced` | ✅ Yes | Indexed path (already flat) |
| `.blend` | ❌ No | Extension swap on preinstanced |
| `.glb` | ❌ No | Extension swap on preinstanced |
| `.snu` | Maybe | JSON map or fallback |
| `.wav` | ❌ No | Extension swap on snu |
| `.vp6` | Maybe | JSON map or fallback |
| `.ogv` | ❌ No | Extension swap on vp6 |
| `.dds` (standalone) | Maybe | Depends on source |
| `.png` | ❌ No | Extension swap on dds |

## Result

✅ **No need to include generated files in JSON maps!**
- Faster flattening (process fewer files)
- Simpler JSON (smaller files)
- Relationships still work correctly via hybrid lookup strategy
