# Test Script for FullFlattened Indexer

## Overview

The `test_fullflattened.py` script automates testing of the indexer by reading configuration from `config.toml` and running the indexer with the appropriate parameters.

## Features

### Automatic Config Detection
- Searches for `config.toml` in common locations:
  - Game module root directory
  - Project root directory
  - Hardcoded fallback path

### Config File Parsing
- **Robust TOML Parsing**: Uses `tomllib` (Python 3.11+) or `tomli` package if available
- **Fallback Parser**: Simple line-based parser if TOML libraries unavailable
- **Safe Defaults**: Falls back to sensible defaults if config not found

### Configuration Mapping

The script reads from `[[placeholders]]` section in `config.toml`:

| Config.toml Key | Indexer Parameter | Description |
|----------------|-------------------|-------------|
| `Region` | `--region` | Region code (EU/US) |
| `Type` | `--Type` | Index type (normalized→FullFlattened, full→Full, source→SourceOnly) |
| `isRenamed` | `--renamedBaseDirs` | Whether base dirs are renamed |
| `audio_state` | `--AudioReorg` | Audio reorganization state |
| `SourcePath` | `--input-dir` | Source files directory |
| `STROUT` | `--output-dir` | Extracted files directory |
| (derived) | `--flatten-map-dir` | Directory containing flatten map JSON files |

## Usage

### Basic Run
```bash
python test_fullflattened.py
```

This will:
1. Find and parse `config.toml`
2. Display the loaded configuration
3. Run the indexer with those parameters
4. Show the indexer output
5. Exit with appropriate return code

### Test Config Parsing Only
```bash
python test_config_parse.py
```

Quickly verifies that config parsing works without running the full indexer.

## Example Output

```
Reading config from: A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\config.toml

Configuration loaded:
  Region: EU
  Type: FullFlattened
  Renamed: isRenamed
  Audio: audio_reorg
  Source Path: A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\Source\USRDIR
  STROUT Dir: A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT_Normalized
  Flatten Map Dir: A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT_Normalized

Running command: python main.py --region EU --Type FullFlattened --renamedBaseDirs isRenamed --AudioReorg audio_reorg --input-dir A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\Source\USRDIR --output-dir A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT_Normalized --flatten-map-dir A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT_Normalized
--------------------------------------------------------------------------------
...
```

## Integration with CI/CD

The script's return code reflects success/failure:
- `0`: Indexing succeeded
- `1`: Indexing failed
- `2`: Validation error (missing directories)
- `3`: Config loading error

This makes it suitable for automated testing:

```bash
python test_fullflattened.py || exit 1
```

## Configuration File Structure

Expected `config.toml` format:

```toml
[[placeholders]]
SourcePath = "A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\Source\\USRDIR"
Region = "EU"
isRenamed = "isRenamed"
audio_state = "audio_reorg"
Type = "normalized"
STROUT = "STROUT_Normalized"
```

## Dependencies

### Required
- Python 3.8+
- Standard library modules: `subprocess`, `sys`, `os`, `pathlib`

### Optional (for robust TOML parsing)
- Python 3.11+ (includes `tomllib`)
- OR `tomli` package: `pip install tomli`

If neither available, falls back to simple parser that works for the expected format.

## Troubleshooting

### "Config file not found"
- Check that `config.toml` exists in the game module root
- Script searches up to 3 directory levels
- Falls back to hardcoded defaults if not found

### "Failed to load flatten maps"
- Ensure `STROUT_Normalized` (or configured STROUT dir) exists
- Check that `flatten_map_*.json` files are present
- Only relevant for `FullFlattened` type

### Indexer fails with missing directories
- Verify paths in `config.toml` are correct
- Check that base directories exist (Assets_*, Map_*)
- Ensure renamed directory structure matches `isRenamed` setting

## Files

- `test_fullflattened.py`: Main test script with config parsing
- `test_config_parse.py`: Simple config parser tester
- `main.py`: The actual indexer script
- `README_FullFlattened.md`: Documentation for FullFlattened mode
