

new static godot prebuild still uses hard coded paths for assets, migrate all to somehow use the normalised json map index to resolve the file paths, or since the paths Need to be in the scene files, it may need a refresh script that finds all asset paths and updates them according to the normalised map based on the files id in its old path


godot all the scene files named for a glb file will now have the wrong uid in the name, update them to the new uids


evaluate the importance of the specific placeholder names in the current operations/config for the game files folder
items like audio_state may not be usefull anymore, others like type or region are still usefull


create a Cleanup operation, after all success operatoins, it should be similar to the reset operation but only deletes or moves to .backup the temporary files, artifactes etc

example folders to cleanup
TMP_TSG_LNKS-PS3-EU-FullFlattened-audio_reorg-isRenamed
operations\Blender\blend.log
GameFiles or only the GameFiles\PS3-EU-Full-audio_reorg-isRenamed not the GameFiles\PS3-EU-FullFlattened-audio_reorg-isRenamed
but it depends on what stage this is run at
after the godot game process? or before it..
maybe the operations should simply avoid leaving behind these things and should cleanthemselves up immediately after execution
