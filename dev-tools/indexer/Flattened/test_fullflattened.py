"""
Test script for FullFlattened indexer mode
Reads configuration from config.toml to determine indexing parameters
"""
import subprocess
import sys
import os
from pathlib import Path

# Try to import tomli/tomllib for robust TOML parsing (fallback to simple parser)
try:
    # Python 3.11+ has tomllib built-in
    import tomllib
    HAS_TOML = True
except ImportError:
    try:
        # For older Python, try tomli package
        import tomli as tomllib
        HAS_TOML = True
    except ImportError:
        HAS_TOML = False
        tomllib = None

def find_config_file():
    """Find the config.toml file in the project structure."""
    # Start from the current directory and search up the tree
    current = Path(__file__).resolve().parent
    
    # Common locations to check
    search_paths = [
        current.parent.parent.parent / 'config.toml',  # Go up to game module root
        current.parent.parent.parent.parent / 'config.toml',
        Path('a:/RemakeEngine/EngineApps/Games/TheSimpsonsGame-PS3/config.toml'),
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None

def parse_config_toml(config_path):
    """Parse config.toml file to extract indexing parameters.
    
    Returns dict with keys: region, type, renamed, audio, source_path, strout_dir
    """
    config = {
        'region': 'US',
        'type': 'FullFlattened',
        'renamed': 'isRenamed',
        'audio': 'audio_og',
        'source_path': None,
        'strout_dir': None,
        'flatten_map_dir': None
    }
    
    if not config_path or not config_path.exists():
        print(f"Warning: Config file not found at {config_path}, using defaults")
        return config
    
    print(f"Reading config from: {config_path}")
    
    try:
        # Try robust TOML parser first
        if HAS_TOML:
            with open(config_path, 'rb') as f:
                toml_data = tomllib.load(f)
                
            # Extract from [[placeholders]] array
            if 'placeholders' in toml_data and len(toml_data['placeholders']) > 0:
                placeholder = toml_data['placeholders'][0]
                
                if 'Region' in placeholder:
                    config['region'] = placeholder['Region']
                if 'isRenamed' in placeholder:
                    config['renamed'] = placeholder['isRenamed']
                if 'audio_state' in placeholder:
                    config['audio'] = placeholder['audio_state']
                if 'Type' in placeholder:
                    # Map config type to indexer type
                    value = placeholder['Type']
                    if value == 'normalized':
                        config['type'] = 'FullFlattened'
                    elif value == 'full':
                        config['type'] = 'Full'
                    elif value == 'source':
                        config['type'] = 'SourceOnly'
                    else:
                        config['type'] = value
                if 'SourcePath' in placeholder:
                    config['source_path'] = placeholder['SourcePath']
                if 'STROUT' in placeholder and config['source_path']:
                    base = Path(config['source_path']).parent.parent
                    config['strout_dir'] = str(base / 'GameFiles' / placeholder['STROUT'])
                    config['flatten_map_dir'] = config['strout_dir']
        else:
            # Fallback to simple line-by-line parser
            with open(config_path, 'r', encoding='utf-8') as f:
                in_placeholders = False
                for line in f:
                    line = line.strip()
                    
                    if line == '[[placeholders]]':
                        in_placeholders = True
                        continue
                    
                    if in_placeholders and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"')
                        
                        if key == 'Region':
                            config['region'] = value
                        elif key == 'isRenamed':
                            config['renamed'] = value
                        elif key == 'audio_state':
                            config['audio'] = value
                        elif key == 'Type':
                            # Map config type to indexer type
                            if value == 'normalized':
                                config['type'] = 'FullFlattened'
                            elif value == 'full':
                                config['type'] = 'Full'
                            elif value == 'source':
                                config['type'] = 'SourceOnly'
                            else:
                                config['type'] = value
                        elif key == 'SourcePath':
                            config['source_path'] = value
                        elif key == 'STROUT':
                            # Construct full path from STROUT directory name
                            if config['source_path']:
                                base = Path(config['source_path']).parent.parent
                                config['strout_dir'] = str(base / 'GameFiles' / value)
                                config['flatten_map_dir'] = config['strout_dir']
    
    except Exception as e:
        print(f"Warning: Error parsing config file: {e}, using defaults")
    
    return config

def run_indexer(region='US', index_type='FullFlattened', renamed='isRenamed', audio='audio_og', 
                source_path=None, strout_dir=None, flatten_map_dir=None):
    """Run the indexer with specified parameters."""
    
    cmd = [
        sys.executable,
        'main.py',
        '--region', region,
        '--Type', index_type,
        '--renamedBaseDirs', renamed,
        '--AudioReorg', audio,
    ]
    
    # Add optional paths if provided
    if source_path:
        cmd.extend(['--input-dir', source_path])
    if strout_dir:
        cmd.extend(['--output-dir', strout_dir])
    if flatten_map_dir:
        cmd.extend(['--flatten-map-dir', flatten_map_dir])
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    print(f"\nReturn code: {result.returncode}")
    return result.returncode == 0

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Find and parse config file
    config_path = find_config_file()
    config = parse_config_toml(config_path)
    
    print("\nConfiguration loaded:")
    print(f"  Region: {config['region']}")
    print(f"  Type: {config['type']}")
    print(f"  Renamed: {config['renamed']}")
    print(f"  Audio: {config['audio']}")
    if config['source_path']:
        print(f"  Source Path: {config['source_path']}")
    if config['strout_dir']:
        print(f"  STROUT Dir: {config['strout_dir']}")
    if config['flatten_map_dir']:
        print(f"  Flatten Map Dir: {config['flatten_map_dir']}")
    print()
    
    # Run indexer with config values
    success = run_indexer(
        region=config['region'],
        index_type=config['type'],
        renamed=config['renamed'],
        audio=config['audio'],
        source_path=config['source_path'],
        strout_dir=config['strout_dir'],
        flatten_map_dir=config['flatten_map_dir']
    )
    
    sys.exit(0 if success else 1)