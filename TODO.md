

new static godot prebuild still uses hard coded paths for assets, migrate all to somehow use the normalised json map index to resolve the file paths, or since the paths Need to be in the scene files, it may need a refresh script that finds all asset paths and updates them according to the normalised map based on the files id in its old path

some scene files are still generated incorrectly by godot, for somereason parent tscn files have thousands of references to assets they done use or need, they need to be recreated to fix


evaluate the importance of the specific placeholder names in the current operations/config for the game files folder
items like audio_state may not be usefull anymore, others like type or region are still usefull


create a Cleanup operation, after all success operatoins, it should be similar to the reset operation but only deletes or moves to .backup the temporary files, artifactes etc

