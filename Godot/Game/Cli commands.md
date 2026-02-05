

```pwsh

dotnet run -c Debug --project EngineNet --framework net10.0 --
 --game_module "EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "lua"
 --script "{{Game_Root}}/Godot/Game/godot-init-V0.5.0.lua"
 --args '
    "--project-name", "SimpsonsGamePS3",
    "--repo-root", "{{Project_Root}}",
    "--sourcePath", "{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}",
    "--iconPath", "{{SourcePath}}/{{Region}}/{{PostSourcePath}}", "--no-exit"
'

```

