"""Quick test to verify config parsing"""
from test_fullflattened import find_config_file, parse_config_toml

config_path = find_config_file()
print(f"Config path: {config_path}")
print()

config = parse_config_toml(config_path)
print("Parsed configuration:")
for key, value in config.items():
    print(f"  {key}: {value}")
