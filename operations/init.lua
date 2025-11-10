-- RemakeEngine Module Init (The Simpsons Game - PS3)
-- Initializes source files by optionally copying/moving them to a local workspace
-- to avoid modifying originals (unless the user chooses to use-in-place).
-- Uses a module-local config.toml ([[placeholders]]) with only SourcePath persisted.
--
-- Runtime guarantees: lfs, sdk, prompt() global are provided by engine

local lfs = require("lfs")
local path_sep = package.config:sub(1,1)

local Colours = {
    DEFAULT = "default",
    WHITE = "white",
    RED = "red",
    GREEN = "green",
    YELLOW = "yellow",
    BLUE = "blue",
    MAGENTA = "magenta",
    CYAN = "cyan",
    GRAY = "gray",
    GREY = "gray",
    DARK_GREEN = "darkgreen",
    DARKGRAY = "darkgray",
    DARKGREY = "darkgray",
    DARKCYAN = "darkcyan",
    DARKYELLOW = "darkyellow",
    DARKRED = "darkred"
}

--- Print a coloured message via SDK (guaranteed by engine runtime)
-- @param opts table { colour: string, message: string }
-- @usage colour_print{ colour = Colours.GREEN, message = "Done" }
local function colour_print(opts)
    opts = opts or {}
    local colour = opts.colour or Colours.DEFAULT
    local message = opts.message or ""
    sdk.colour_print({ colour = colour, message = message, newline = true })
end

local function join(a, b)
    local sep = path_sep or "/"
    if a:sub(-1) == sep then return a .. b end
    return a .. sep .. b
end

local function basename(path)
    return (path and path:match("([^/\\]+)$")) or path
end

local function ends_with_usrdir(p)
    if not p then return false end
    local name = basename(p)
    return name and name:lower() == "usrdir"
end

local function normalize(p)
    if not p then return p end
    local sep = path_sep or "/"
    if sep == "\\" then p = p:gsub("/", "\\") else p = p:gsub("\\", "/") end
    p = p:gsub("[/\\]+", sep)
    return p
end

local function trim(s)
    if not s then return s end
    return s:match("^%s*(.-)%s*$")
end

local function normalize_region(value)
    if type(value) ~= "string" then return nil end
    local region = trim(value)
    if not region or region == "" then return nil end
    region = region:upper()
    if region == "US" or region == "EU" then
        return region
    end
    return nil
end

local function dirname(p)
    if not p or p == "" then return "." end
    local d = p:match("(.+)[/\\][^/\\]+$") or p:match("(.+)[/\\]$") or ""
    if d == "" then return "." end
    return d
end

local function is_absolute(p)
    if not p then return false end
    if p:match("^%a:[/\\]") then return true end -- Windows drive
    if p:sub(1,2) == "\\\\" then return true end -- UNC
    if p:sub(1,1) == "/" then return true end -- Unix root
    return false
end

local function is_dir(path)
    return sdk.is_dir(path)
end

local function file_exists(path)
    return sdk.path_exists(path)
end

local function list_subdirs(path)
    local dirs = {}
    if not is_dir(path) then return dirs end
    for f in lfs.dir(path) do
        if f ~= "." and f ~= ".." then
            local full = join(path, f)
            local attr = lfs.attributes(full)
            if attr and attr.mode == "directory" then
                table.insert(dirs, f)
            end
        end
    end
    return dirs
end

-- Input helper using engine's guaranteed prompt() global
local function get_input(msg, id)
    return prompt(msg, id or "tsg_init", false)
end

-- TODO: change to get dir names from config/RenameMap.db

-- Required directory sets (either original or USRDIR layout is accepted)
local USRDIR_DIRS = {
    "Assets_1_Audio_Streams", "Assets_1_Video_Movies", "Assets_2_Characters_Simpsons",
    "Assets_2_Frontend", "Map_3-00_GameHub", "Map_3-00_SprHub", "Map_3-01_LandOfChocolate",
    "Map_3-02_BartmanBegins", "Map_3-03_HungryHungryHomer", "Map_3-04_TreeHugger",
    "Map_3-05_MobRules", "Map_3-06_EnterTheCheatrix", "Map_3-07_DayOfTheDolphin",
    "Map_3-08_TheColossalDonut", "Map_3-09_Invasion", "Map_3-10_BargainBin",
    "Map_3-11_NeverQuest", "Map_3-12_GrandTheftScratchy", "Map_3-13_MedalOfHomer",
    "Map_3-14_BigSuperHappy", "Map_3-15_Rhymes", "Map_3-16_MeetThyPlayer",
}

local USRDIR_DIRS_ORIGINAL = {
    "audiostreams", "bargainbin", "bigsuperhappy", "brt", "cheater", "colossaldonut",
    "dayofthedolphins", "dayspringfieldstoodstill", "eighty_bites", "frontend", "gamehub",
    "grand_theft_scratchy", "loc", "medal_of_homer", "meetthyplayer", "mob_rules",
    "movies", "neverquest", "rhymes", "simpsons_chars", "spr_hub", "text", "tree_hugger",
}

local function check_dirs_exist(base_path, required_dirs)
    if not is_dir(base_path) then return false end
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not is_dir(full_path) then return false end
    end
    return true
end

-- Verbose variant for logging which list is being checked
local function check_dirs_exist_verbose(base_path, required_dirs, list_name)
    if not is_dir(base_path) then return false end
    local missing = {}
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not is_dir(full_path) then table.insert(missing, dir_name) end
    end
    if #missing == 0 then
        colour_print{colour=Colours.GREEN, message=(list_name and ("All %d required '%s' subdirectories found in '"..base_path.."'."):format(#required_dirs, list_name) or ("All %d required subdirectories found in '"..base_path.."'."):format(#required_dirs))}
        return true
    end
    return false
end

-- TOML helpers via engine SDK (guaranteed by runtime)
local function read_placeholders(cfg_path)
    if not sdk.toml_read_file then
        error("SDK toml_read_file not available - engine integrity issue")
    end
    local doc = sdk.toml_read_file(cfg_path)
    if not doc then return {} end
    -- Accept either tables or arrays-of-tables for 'placeholders'
    local ph = doc["placeholders"]
    if type(ph) == "table" then
        if ph[1] and type(ph[1]) == "table" then
            return ph[1]
        end
        return ph
    end
    return {}
end

local function write_placeholders(cfg_path, new_placeholders)
    if not sdk.toml_write_file then
        error("SDK toml_write_file not available - engine integrity issue")
    end
    local doc = {}
    -- Write as array-of-tables to mirror previous structure [[placeholders]]
    doc["placeholders"] = { new_placeholders }
    sdk.toml_write_file(cfg_path, doc)
end

-- Count files recursively (files only)
local function count_files(path)
    local count = 0
    for file in lfs.dir(path) do
        if file ~= "." and file ~= ".." then
            local full = join(path, file)
            local attr = lfs.attributes(full)
            if attr and attr.mode == "file" then
                count = count + 1
            elseif attr and attr.mode == "directory" then
                count = count + count_files(full)
            end
        end
    end
    return count
end

-- ensure_dir: create directory using SDK (guaranteed by engine runtime)
local function ensure_dir(path)
    return sdk.ensure_dir(normalize(path))
end

-- copy a file using SDK (guaranteed by engine runtime)
local function copy_file(src, dst)
    ensure_dir(dirname(dst))
    return sdk.copy_file(src, dst, true)
end

-- copy a directory tree using SDK with progress tracking
local function copy_tree(src, dst, total, state)
    for file in lfs.dir(src) do
        if file ~= "." and file ~= ".." then
            local src_path = join(src, file)
            local dst_path = join(dst, file)
            local attr = lfs.attributes(src_path)
            if attr and attr.mode == "directory" then
                ensure_dir(dst_path)
                copy_tree(src_path, dst_path, total, state)
            elseif attr and attr.mode == "file" then
                copy_file(src_path, dst_path)
                state.count = state.count + 1
                local progress = (total > 0) and ((state.count / total) * 100) or 100
                sdk.color_print({ color = 'yellow', message = string.format("Copying... %d/%d files (%.1f%%) ", state.count, total, progress), newline = false })
            end
        end
    end
end

-- move a directory using SDK (guaranteed by engine runtime)
local function move_tree(src, dst)
    return sdk.move_dir(src, dst, false)
end

-- Check if a folder contains USRDIR, PARAM.SFO, and at least one PNG (PS3_GAME folder structure)
local function is_ps3_game_folder(path)
    if not is_dir(path) then return false end
    local has_usrdir = is_dir(join(path, "USRDIR"))
    local has_sfo = file_exists(join(path, "PARAM.SFO"))
    local has_png = false
    -- Check for any PNG file
    if lfs then
        for file in lfs.dir(path) do
            if file:match("%.png$") or file:match("%.PNG$") then
                has_png = true
                break
            end
        end
    end
    return has_usrdir and has_sfo and has_png
end

-- Validate and resolve the source path, checking multiple possible locations for USRDIR
-- Returns: ok (bool), usrdir_path (for validation), folder_to_copy (the PS3_GAME parent folder)
-- Handles paths that point to:
--   - Direct USRDIR folder (D:\PS3_GAME\USRDIR) -> copy parent PS3_GAME
--   - PS3_GAME folder containing USRDIR (D:\PS3_GAME) -> copy this folder
--   - Root disc folder containing PS3_GAME (D:\) -> find and copy PS3_GAME subfolder
local function validate_source_path(path)
    if not path or path == "" or not is_dir(path) then return false, path, path end
    
    -- Check if path itself is USRDIR (has game directories)
    local ok = check_dirs_exist(path, USRDIR_DIRS_ORIGINAL) or check_dirs_exist(path, USRDIR_DIRS)
    if ok then
        -- This is the USRDIR folder, so copy its parent (PS3_GAME)
        local parent = dirname(path)
        if is_ps3_game_folder(parent) then
            return true, path, parent
        end
        -- Fallback if parent doesn't have PS3_GAME structure
        return true, path, path
    end
    
    -- Check if path contains USRDIR subfolder (this is PS3_GAME folder)
    local usrdir = join(path, "USRDIR")
    if is_dir(usrdir) then
        ok = check_dirs_exist(usrdir, USRDIR_DIRS_ORIGINAL) or check_dirs_exist(usrdir, USRDIR_DIRS)
        if ok and is_ps3_game_folder(path) then
            -- This is the PS3_GAME folder itself, copy this folder
            return true, usrdir, path
        end
    end
    
    -- Check path/PS3_GAME/USRDIR (for disc root like D:\)
    local ps3_game = join(path, "PS3_GAME")
    if is_dir(ps3_game) then
        local ps3_usrdir = join(ps3_game, "USRDIR")
        if is_dir(ps3_usrdir) then
            ok = check_dirs_exist(ps3_usrdir, USRDIR_DIRS_ORIGINAL) or check_dirs_exist(ps3_usrdir, USRDIR_DIRS)
            if ok and is_ps3_game_folder(ps3_game) then
                -- Found PS3_GAME subfolder, copy that folder
                return true, ps3_usrdir, ps3_game
            end
        end
    end
    
    return false, path, path
end

local function main()
    -- Determine module directory (two levels up from this script: operations/init.lua -> module root)
    local this_file_path = debug.getinfo(1, 'S').source:sub(2)
    local module_dir = (this_file_path:match("(.+)[/\\][^/\\]+[/\\][^/\\]+$") or ".")
    local cfg_path = join(module_dir, "config.toml")
    local local_data_path = normalize(join(module_dir, "Source"))

    -- Ensure config.toml exists with a placeholders block
    if not file_exists(cfg_path) then
        colour_print{colour=Colours.YELLOW, message="Config not found. Creating: " .. cfg_path}
        -- Include isRenamed = "notRenamed" by default
        write_placeholders(cfg_path, { SourcePath = "", Region = "", isRenamed = "notRenamed" })
        colour_print{colour=Colours.GREEN, message="Created config.toml with default placeholders."}
    end

    colour_print{colour=Colours.BLUE, message="Reading module config: " .. cfg_path}
    local placeholders = read_placeholders(cfg_path)
    -- Auto-add isRenamed = "notRenamed" if missing; do not overwrite if it already exists
    if placeholders["isRenamed"] == nil then
        placeholders["isRenamed"] = "notRenamed"
        write_placeholders(cfg_path, placeholders)
        colour_print{colour=Colours.GREEN, message="Initialized placeholders.isRenamed = \"notRenamed\""}
    end

    -- ensure audio_state placeholder exists if not set to audio_og
    if placeholders["audio_state"] == nil then
        placeholders["audio_state"] = "audio_og"
        write_placeholders(cfg_path, placeholders)
        colour_print{colour=Colours.GREEN, message="Initialized placeholders.audio_state = \"audio_og\""}
    end

    -- ensure type placeholder exists if not set
    if placeholders["Type"] == nil then
        placeholders["Type"] = "Full"
        write_placeholders(cfg_path,placeholders)
        colour_print{colour=Colours.GREEN, message="Initialized placeholders.Type = \"Full\""}
    end

    -- ensure out placeholder exists if not set
    if placeholders["STROUT"] == nil then
        placeholders["STROUT"] = "STROUT"
        write_placeholders(cfg_path,placeholders)
        colour_print{colour=Colours.GREEN, message="Initialized placeholders.STROUT = \"STROUT\""}
    end

    local region = normalize_region(placeholders["Region"])
    if region then
        placeholders["Region"] = region
    else
        colour_print{colour=Colours.YELLOW, message="No valid Region set in config.toml. You'll be prompted to set one (US or EU)."}
                while true do
            local input = get_input("Enter the game region (US or EU) and press Enter (leave blank to cancel):", "tsg_region")
            if not input or input == "" then
                colour_print{colour=Colours.RED, message="Initialization aborted: no valid Region provided."}
                colour_print{colour=Colours.YELLOW, message="Please update '" .. cfg_path .. "' with Region = \"US\" or \"EU\" and re-run this initializer."}
                return false
            end
            local normalized = normalize_region(input)
            if normalized then
                region = normalized
                placeholders["Region"] = region
                write_placeholders(cfg_path, placeholders)
                colour_print{colour=Colours.GREEN, message="Set Region to '" .. region .. "'."}
                break
            else
                colour_print{colour=Colours.RED, message="Invalid region. Please enter 'US' or 'EU'."}
            end
        end
    end

    colour_print(placeholders)
    local existing = placeholders["SourcePath"]
    local copy_source_root = nil -- exact folder provided by user (or existing), used for copy/move semantics

    -- Phase A: If existing SourcePath is invalid/missing, prompt user to provide a valid path
    local path_from_config = nil
    if existing and existing ~= "" then
        existing = normalize(existing)
        copy_source_root = existing
        local ok, resolved, folder_to_copy = validate_source_path(existing)
        if ok then
            path_from_config = normalize(resolved)
            copy_source_root = folder_to_copy -- Update to use the folder that should be copied
            if path_from_config ~= existing then
                colour_print{colour=Colours.YELLOW, message="Detected USRDIR under provided path; using '" .. path_from_config .. "' as source root."}
                colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. basename(copy_source_root) .. "'"}
            end
        else
            colour_print{colour=Colours.YELLOW, message="Existing SourcePath is not valid. You'll be prompted to set a valid one."}
        end
    else
        colour_print{colour=Colours.YELLOW, message="No SourcePath set in config.toml. You'll be prompted to set one."}
    end

    while not path_from_config do
        local input = prompt("Enter the path to your game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
        if not input or input == "" then
            colour_print{colour=Colours.RED, message="Initialization aborted: no valid SourcePath is configured and no input was provided."}
            colour_print{colour=Colours.YELLOW, message="Please update '" .. cfg_path .. "' with a valid SourcePath and re-run this initializer."}
            return false
        end
        input = normalize(is_absolute(input) and input or join(lfs.currentdir(), input))
        if is_dir(input) then
            local ok, resolved, folder_to_copy = validate_source_path(input)
            if ok then
                path_from_config = normalize(resolved)
                copy_source_root = folder_to_copy -- Use the folder that should be copied
                if path_from_config ~= input then
                    colour_print{colour=Colours.YELLOW, message="Detected USRDIR under provided path; using '" .. path_from_config .. "' as source root."}
                    colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. basename(copy_source_root) .. "'"}
                end
            else
                colour_print{colour=Colours.RED, message="The provided path does not look like a valid game root/USRDIR. Please try again."}
            end
        else
            colour_print{colour=Colours.RED, message="The provided path is not a directory. Please try again."}
        end
    end

    -- Phase B: Offer to Copy/Move/Use-in-place into local workspace under the module
    colour_print{colour=Colours.MAGENTA, message="\n--- Source Path Handling ---"}
    colour_print{colour=Colours.CYAN, message="Validated source path: '" .. path_from_config .. "'"}
    colour_print{colour=Colours.CYAN, message="Local project data path: '" .. local_data_path .. "'"}

    local effective_source_path = path_from_config

    -- If SourcePath is already inside local_data_path, assume it was set to local previously
    local function starts_with(a, b)
        return a:sub(1, #b):lower() == b:lower()
    end

    if not starts_with(path_from_config, local_data_path) then
        if not file_exists(local_data_path) then
            colour_print{colour=Colours.YELLOW, message="\nChoose how to use the source files:"}
            local display_name = basename(copy_source_root or path_from_config)
            
            -- Check if source path is writable (not read-only like an ISO)
            local source_is_writable = sdk and sdk.is_writable and sdk.is_writable(copy_source_root or path_from_config) or false
            
            -- Build options based on writability
            local options = {}
            table.insert(options, {id = "1", label = "Copy folder '" .. display_name .. "' into local '" .. basename(local_data_path) .. "' (Recommended, Safe)"})
            
            if source_is_writable then
                table.insert(options, {id = "2", label = "Move folder '" .. display_name .. "' into local '" .. basename(local_data_path) .. "' (Warning: Deletes originals)"})
                table.insert(options, {id = "3", label = "Use original path '" .. display_name .. "' directly (Warning: Tools may modify original files)"})
            else
                colour_print{colour=Colours.YELLOW, message="  Note: Source is read-only (e.g., ISO/disc). Only copy option is available."}
            end
            
            -- Display options
            for _, opt in ipairs(options) do
                colour_print{colour=Colours.CYAN, message="  " .. opt.id .. ") " .. opt.label}
            end
            
            -- Build valid choices string
            local valid_choices = {}
            for _, opt in ipairs(options) do
                table.insert(valid_choices, opt.id)
            end
            local choices_str = table.concat(valid_choices, ", ")
            if #valid_choices == 1 then
                choices_str = valid_choices[1]
            elseif #valid_choices == 2 then
                choices_str = valid_choices[1] .. " or " .. valid_choices[2]
            else
                choices_str = table.concat(valid_choices, ", ", 1, #valid_choices - 1) .. ", or " .. valid_choices[#valid_choices]
            end

            while true do
                local choice = (prompt("Enter your choice (" .. choices_str .. "):") or ""):match("^%s*(.-)%s*$")
                if choice == '1' then
                    local src = normalize(copy_source_root or path_from_config)
                    local src_name = basename(src)
                    local dst = join(local_data_path, src_name) -- Nest the folder inside Source
                    colour_print{colour=Colours.BLUE, message="Copying folder '" .. src_name .. "' into '" .. local_data_path .. "'..."}
                    ensure_dir(local_data_path)
                    local copied = false
                    if sdk and sdk.copy_dir then
                        -- Use engine SDK to bypass sandbox file IO restrictions
                        local ok = sdk.copy_dir(src, dst, true)
                        if not ok then
                            colour_print{colour=Colours.RED, message="Copy via SDK failed. Falling back to Lua copy (may be restricted)."}
                        else
                            copied = true
                        end
                    end
                    if not copied then
                        local total = count_files(src)
                        local state = { count = 0 }
                        ensure_dir(dst)
                        -- copy entire folder to dst preserving structure
                        copy_tree(src, dst, total, state)
                    end
                    if io and type(io.write) == "function" then io.write("\n") end
                    if io and type(io.flush) == "function" then io.flush() end
                    colour_print{colour=Colours.GREEN, message="Copy complete."}
                    -- Set effective_source_path to the USRDIR inside the copied folder
                    local copied_usrdir = join(dst, "USRDIR")
                    if is_dir(copied_usrdir) then
                        effective_source_path = copied_usrdir
                    else
                        effective_source_path = dst
                    end
                    break
                elseif choice == '2' and source_is_writable then
                    local src = normalize(copy_source_root or path_from_config)
                    local target_dir = join(local_data_path, basename(src))
                    colour_print{colour=Colours.YELLOW, message="Moving folder '" .. basename(src) .. "' into '" .. local_data_path .. "'..."}
                    ensure_dir(local_data_path)
                    local ok_move = false
                    if sdk and sdk.move_dir then
                        -- Move into a nested target under local_data_path to preserve original folder name
                        ok_move = sdk.move_dir(src, target_dir, true)
                    else
                        ok_move = move_tree(src, local_data_path)
                    end
                    if ok_move then
                        local moved_dir = target_dir
                        colour_print{colour=Colours.GREEN, message="Move complete."}
                        -- Set effective_source_path to the USRDIR inside the moved folder
                        local moved_usrdir = join(moved_dir, "USRDIR")
                        if is_dir(moved_usrdir) then
                            effective_source_path = moved_usrdir
                        elseif ends_with_usrdir(moved_dir) then
                            effective_source_path = moved_dir
                        else
                            effective_source_path = moved_dir
                        end
                        break
                    else
                        colour_print{colour=Colours.RED, message="Move failed. Please check permissions/paths and try again."}
                    end
                elseif choice == '3' and source_is_writable then
                    colour_print{colour=Colours.YELLOW, message="Using original path directly."}
                    effective_source_path = path_from_config
                    break
                else
                    colour_print{colour=Colours.YELLOW, message="Invalid choice. Please enter " .. choices_str .. "."}
                end
            end
        else
            -- Local data already exists; try to point to the correct subdir
            local direct_usrdir = join(local_data_path, "USRDIR")
            if is_dir(direct_usrdir) then
                effective_source_path = direct_usrdir
            else
                local subs = list_subdirs(local_data_path)
                if #subs == 1 then
                    local only = join(local_data_path, subs[1])
                    if is_dir(join(only, "USRDIR")) then
                        effective_source_path = join(only, "USRDIR")
                    else
                        effective_source_path = only
                    end
                else
                    effective_source_path = local_data_path
                end
            end
        end
    else
        effective_source_path = path_from_config
    end

    -- Persist the effective SourcePath in config.toml
    colour_print{colour=Colours.YELLOW, message="  Updating config.toml with effective Source Path..."}
    placeholders["SourcePath"] = effective_source_path
    write_placeholders(cfg_path, placeholders)
    colour_print{colour=Colours.GREEN, message="  Config updated."}

    -- Final validation (switch to USRDIR if present) and persist validated path
    colour_print{colour=Colours.BLUE, message="\nValidating final source location: '" .. effective_source_path .. "'"}
    local potential_usrdir_path = join(effective_source_path, "USRDIR")
    local path_to_validate = is_dir(potential_usrdir_path) and potential_usrdir_path or effective_source_path

    local found_original = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")
    local found_usrdir = false
    if not found_original then
        colour_print{colour=Colours.BLUE, message="  ORIGINAL list not fully present. Checking USRDIR_DIRS..."}
        found_usrdir = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")
    end

    if found_original or found_usrdir then
        placeholders["SourcePath"] = path_to_validate
        write_placeholders(cfg_path, placeholders)
        colour_print{colour=Colours.GREEN, message="Success: Source validated and saved: " .. path_to_validate}
        return true
    else
        colour_print{colour=Colours.RED, message="Error: Validation failed for path '" .. path_to_validate .. "'."}
        colour_print{colour=Colours.YELLOW, message="Please verify the directory contents and re-run this initializer."}
        return false
    end
end

-- Execute immediately when run as a script
do
    local ok, result = pcall(main)
    if not ok then
        colour_print{colour=Colours.RED, message="Initialization failed with error: " .. tostring(result)}
        -- Non-zero exit so the host marks the operation as failed
        os.exit(1)
    end
    -- If main returned false (explicit failure), exit non-zero
    if result == false then
        os.exit(1)
    end
    -- Success
    -- do not exit, the operation should just complete
end
