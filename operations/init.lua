-- RemakeEngine Module Init (The Simpsons Game - PS3)
-- Initializes source files by optionally copying/moving them to a local workspace
-- to avoid modifying originals (unless the user chooses to use-in-place).
-- Uses a module-local config.toml ([[placeholders]]) with only SourcePath persisted.

local lfs = require("lfs")
local path_sep = package.config:sub(1,1)
local sdk = rawget(_G, "sdk")

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

--- Print a coloured message via SDK if available; falls back to print().
-- @param opts table { colour: string, message: string }
-- @usage colour_print{ colour = Colours.GREEN, message = "Done" }
local function colour_print(opts)
    opts = opts or {}
    local colour = opts.colour or Colours.DEFAULT
    local message = opts.message or ""
    if sdk and sdk.colour_print then
        sdk.colour_print({ colour = colour, message = message, newline = true })
    else
        print(message)
    end
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
    local attr = lfs.attributes(path)
    return attr and attr.mode == "directory"
end

local function file_exists(path)
    local attr = lfs.attributes(path)
    return attr ~= nil
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

-- Input helper compatible with RemakeEngine's embedded Lua environment
local function get_input(msg, id)
    -- Prefer engine-provided global prompt() if available
    local global_prompt = rawget(_G, "prompt")
    if type(global_prompt) == "function" then
        return global_prompt(msg, id or "tsg_init", false)
    end
    -- Fallback to sdk.prompt if exposed
    if sdk and type(sdk.prompt) == "function" then
        return sdk.prompt(msg, id or "tsg_init", false)
    end
    -- Last resort: try standard io (may be sandboxed/absent)
    if io and type(io.write) == "function" then io.write(msg .. "\n") end
    if io and type(io.flush) == "function" then io.flush() end
    if io and type(io.read) == "function" then
        local ok, line = pcall(io.read, "*l")
        if ok then return line end
    end
    return nil
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

-- TOML helpers via engine SDK
local function read_placeholders(cfg_path)
    if not sdk or not sdk.toml_read_file then return {} end
    local doc = sdk.toml_read_file(cfg_path)
    if not doc then return {} end
    -- Accept either tables or arrays-of-tables for 'placeholders'
    local ph = doc["placeholders"]
    if type(ph) == "table" then
        -- If it's an array-of-tables, take the first
        if ph[1] and type(ph[1]) == "table" then
            return ph[1]
        end
        return ph
    end
    return {}
end

local function write_placeholders(cfg_path, new_placeholders)
    if not sdk or not sdk.toml_write_file then return end
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

-- ensure_dir: create directory (and parents) if needed
local ensure_dir -- forward decl
ensure_dir = function(path)
    local target = normalize(path)
    if is_dir(target) then return true end
    if lfs and type(lfs.mkdir) == "function" then
        -- attempt to create parent first
        local parent = dirname(target)
        if parent and parent ~= target and not is_dir(parent) then
            ensure_dir(parent)
        end
        local ok = lfs.mkdir(target)
        if ok then return true end
    end
    -- fallback to shell mkdir for deep paths
    local cmd
    if path_sep == "\\" then
        cmd = string.format('cmd /C mkdir "%s"', target)
    else
        cmd = string.format('mkdir -p "%s"', target)
    end
    local _ = os.execute(cmd)
    return is_dir(target)
end

-- copy a file (binary)
local function copy_file(src, dst)
    ensure_dir(dirname(dst))
    local infile = assert(io.open(src, "rb"))
    local data = infile:read("*a")
    infile:close()
    local outfile = assert(io.open(dst, "wb"))
    outfile:write(data)
    outfile:close()
end

-- copy a directory tree with simple progress
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
                if io and type(io.write) == "function" then
                    io.write(string.format("\rCopying... %d/%d files (%.1f%%) ", state.count, total, progress))
                    if type(io.flush) == "function" then io.flush() end
                elseif sdk and sdk.color_print then
                    sdk.color_print({ color = 'yellow', message = string.format("Copying... %d/%d", state.count, total), newline = false })
                end
            end
        end
    end
end

-- move a directory tree using shell
local function move_tree(src, dst)
    local cmd
    if path_sep == "\\" then
        cmd = string.format('cmd /C move "%s" "%s"', src, dst)
    else
        cmd = string.format('mv "%s" "%s"', src, dst)
    end
    return os.execute(cmd)
end

local function validate_source_path(path)
    if not path or path == "" or not is_dir(path) then return false, path end
    local usrdir = join(path, "USRDIR")
    local check_path = is_dir(usrdir) and usrdir or path
    local ok = check_dirs_exist(check_path, USRDIR_DIRS_ORIGINAL) or check_dirs_exist(check_path, USRDIR_DIRS)
    return ok, check_path
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
        placeholders["Type"] = "full"
        write_placeholders(cfg_path,placeholders)
        colour_print{colour=Colours.GREEN, message="Initialized placeholders.Type = \"full\""}
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
        local ok, resolved = validate_source_path(existing)
        if ok then
            path_from_config = normalize(resolved)
            if path_from_config ~= existing then
                colour_print{colour=Colours.YELLOW, message="Detected USRDIR under provided path; using '" .. path_from_config .. "' as source root."}
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
            local ok, resolved = validate_source_path(input)
            if ok then
                path_from_config = normalize(resolved)
                copy_source_root = input -- preserve exactly what the user provided for copy/move
                if path_from_config ~= input then
                    colour_print{colour=Colours.YELLOW, message="Detected USRDIR under provided path; using '" .. path_from_config .. "' as source root."}
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
            colour_print{colour=Colours.CYAN, message="  1) Copy folder '" .. display_name .. "' into local '" .. basename(local_data_path) .. "' (Recommended, Safe)"}
            colour_print{colour=Colours.CYAN, message="  2) Move folder '" .. display_name .. "' into local '" .. basename(local_data_path) .. "' (Warning: Deletes originals)"}
            colour_print{colour=Colours.CYAN, message="  3) Use original path '" .. display_name .. "' directly (Warning: Tools may modify original files)"}

            while true do
                local choice = (prompt("Enter your choice (1, 2, or 3):") or ""):match("^%s*(.-)%s*$")
                if choice == '1' then
                    local src = normalize(copy_source_root or path_from_config)
                    local dst = local_data_path
                    colour_print{colour=Colours.BLUE, message="Copying contents of folder '" .. basename(src) .. "' into '" .. dst .. "'..."}
                    ensure_dir(dst)
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
                        -- copy contents of src directly into dst (no extra nesting)
                        copy_tree(src, dst, total, state)
                    end
                    if io and type(io.write) == "function" then io.write("\n") end
                    if io and type(io.flush) == "function" then io.flush() end
                    colour_print{colour=Colours.GREEN, message="Copy complete."}
                    if is_dir(join(dst, "USRDIR")) then
                        effective_source_path = join(dst, "USRDIR")
                    else
                        effective_source_path = dst
                    end
                    break
                elseif choice == '2' then
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
                        if is_dir(join(moved_dir, "USRDIR")) then
                            effective_source_path = join(moved_dir, "USRDIR")
                        elseif ends_with_usrdir(moved_dir) then
                            effective_source_path = moved_dir
                        else
                            effective_source_path = moved_dir
                        end
                        break
                    else
                        colour_print{colour=Colours.RED, message="Move failed. Please check permissions/paths and try again."}
                    end
                elseif choice == '3' then
                    colour_print{colour=Colours.YELLOW, message="Using original path directly."}
                    effective_source_path = path_from_config
                    break
                else
                    colour_print{colour=Colours.YELLOW, message="Invalid choice. Please enter 1, 2, or 3."}
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
