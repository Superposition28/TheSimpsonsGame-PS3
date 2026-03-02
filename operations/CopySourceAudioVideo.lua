--- CopySourceAudioVideo.lua
--- Copies the 'movies' and 'audiostreams' folders from the game's source USRDIR 
--- into the processed assets target directory.
---
--- Arguments:
---   --source: The source USRDIR path containing movies and audiostreams.
---   --target: The target directory where the folders should be copied.

local Utils = import("SharedUtils")

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
    sdk.colour_print({ colour = "red", message = "Error: Missing required arguments --source and --target" })
    error("Missing required arguments")
end

sdk.colour_print({ colour = "cyan", message = "=== Copying Source Audio/Video Files ===" })
sdk.colour_print({ colour = "white", message = "  Source: " .. SourcePath })
sdk.colour_print({ colour = "white", message = "  Target: " .. TargetPath })

-- Initialize progress tracking
progress.start(3, "Copying Audio/Video")

-- Ensure the target base directory exists
sdk.ensure_dir(TargetPath)

-- Process Movies Folder
progress.step("Copying 'movies' folder...")
local MoviesSource = Utils.join(SourcePath, "movies")
local MoviesTarget = Utils.join(TargetPath, "movies")

if sdk.path_exists(MoviesSource) then
    sdk.colour_print({ colour = "white", message = "  Found 'movies', copying..." })
    sdk.copy_dir(MoviesSource, MoviesTarget, true)
else
    sdk.colour_print({ colour = "yellow", message = "  Warning: 'movies' folder not found at " .. MoviesSource })
end

-- Process Audiostreams Folder
progress.step("Copying 'audiostreams' folder...")
local AudioSource = Utils.join(SourcePath, "audiostreams")
local AudioTarget = Utils.join(TargetPath, "audiostreams")

if sdk.path_exists(AudioSource) then
    sdk.colour_print({ colour = "white", message = "  Found 'audiostreams', copying..." })
    sdk.copy_dir(AudioSource, AudioTarget, true)
else
    sdk.colour_print({ colour = "yellow", message = "  Warning: 'audiostreams' folder not found at " .. AudioSource })
end

-- Finish
progress.step("Finalizing")
sdk.colour_print({ colour = "green", message = "Successfully finished copying source files." })
