--- CopySourceAudioVideo.lua
--- Copies the 'movies' and 'audiostreams' folders from the game's source USRDIR 
--- into the processed assets target directory.
---
--- Arguments:
---   --source: The source USRDIR path containing movies and audiostreams.
---   --target: The target directory where the folders should be copied.

local function ParseArgs(List)
    local Opts = {}
    local I = 1
    while I <= #List do
        local Key = List[I]
        if Key == "--source" and List[I + 1] then
            Opts.SourcePath = List[I + 1]
            I = I + 2
        elseif Key == "--target" and List[I + 1] then
            Opts.TargetPath = List[I + 1]
            I = I + 2
        else
            I = I + 1
        end
    end
    return Opts
end

-- Parse command line arguments
local Opts = ParseArgs(argv or {...})
local SourcePath = Opts.SourcePath
local TargetPath = Opts.TargetPath

if not SourcePath or not TargetPath then
    sdk.color_print("red", "Error: Missing required arguments --source and --target")
    error("Missing required arguments")
end

sdk.color_print("cyan", "=== Copying Source Audio/Video Files ===")
sdk.color_print("white", "  Source: " .. SourcePath)
sdk.color_print("white", "  Target: " .. TargetPath)

-- Initialize progress tracking
progress.start(3, "Copying Audio/Video")

-- Ensure the target base directory exists
sdk.ensure_dir(TargetPath)

-- Process Movies Folder
progress.step("Copying 'movies' folder...")
local MoviesSource = SourcePath .. "/movies"
local MoviesTarget = TargetPath .. "/movies"

if sdk.path_exists(MoviesSource) then
    sdk.color_print("white", "  Found 'movies', copying...")
    sdk.copy_dir(MoviesSource, MoviesTarget, true)
else
    sdk.color_print("yellow", "  Warning: 'movies' folder not found at " .. MoviesSource)
end

-- Process Audiostreams Folder
progress.step("Copying 'audiostreams' folder...")
local AudioSource = SourcePath .. "/audiostreams"
local AudioTarget = TargetPath .. "/audiostreams"

if sdk.path_exists(AudioSource) then
    sdk.color_print("white", "  Found 'audiostreams', copying...")
    sdk.copy_dir(AudioSource, AudioTarget, true)
else
    sdk.color_print("yellow", "  Warning: 'audiostreams' folder not found at " .. AudioSource)
end

-- Finish
progress.step("Finalizing")
sdk.color_print("green", "Successfully finished copying source files.")
