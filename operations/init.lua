-- RemakeEngine Module Init (The Simpsons Game - PS3)
-- Initializes source files by optionally copying/moving them to a local workspace
-- to avoid modifying originals (unless the user chooses to use-in-place).
-- Uses a module-local config.toml ([[placeholders]]) with path components:
--   MainSourcePath: Full path to USRDIR (e.g., A:\...\Source\EU\PS3_GAME\USRDIR)
--   SourcePath: Base Source directory (e.g., A:\...\Source)
--   PostSourcePath: Relative path from Source to USRDIR (e.g., EU\PS3_GAME\USRDIR)
-- Supports regions: US, EU, or Both (prompts for both, stores EU as primary)
--

-- Bootstrap the Utils module

local Utils = import("SharedUtils")
local Colours = Utils.Colours

-- Local application-specific helpers
local function ends_with_usrdir(p)
    if not p then return false end
    local name = Utils.basename(p)
    return name and name:lower() == "usrdir"
end

local function normalize_region(value)
    if type(value) ~= "string" then return nil end
    local region = Utils.trim(value)
    if not region or region == "" then return nil end
    region = region:upper()
    if region == "US" or region == "EU" or region == "BOTH" then
        return region
    end
    return nil
end

-- Input helper using engine's guaranteed prompt() global
local function get_input(msg, id)
    return prompt(msg, id or "tsg_init", false)
end

-- Required directory sets (either original or USRDIR layout is accepted)
local USRDIR_DIRS = {
    "A1_Audio", "A1_Video", "A2_Characters",
    "A2_Frontend", "LHub-00_GameHub", "LHub-00_SprHub", "L01_LandOfChocolate",
    "L02_BartmanBegins", "L03_HungryHungryHomer", "L04_TreeHugger",
    "L05_MobRules", "L06_EnterTheCheatrix", "L07_DayOfTheDolphin",
    "L08_TheColossalDonut", "L09_Invasion", "L10_BargainBin",
    "L11_NeverQuest", "L12_GrandTheftScratchy", "L13_MedalOfHomer",
    "L14_BigSuperHappy", "L15_Rhymes", "L16_MeetThyPlayer",
}

local USRDIR_DIRS_ORIGINAL = {
    "audiostreams", "bargainbin", "bigsuperhappy", "brt", "cheater", "colossaldonut",
    "dayofthedolphins", "dayspringfieldstoodstill", "eighty_bites", "frontend", "gamehub",
    "grand_theft_scratchy", "loc", "medal_of_homer", "meetthyplayer", "mob_rules",
    "movies", "neverquest", "rhymes", "simpsons_chars", "spr_hub", "text", "tree_hugger",
}

local function check_dirs_exist(base_path, required_dirs)
    if not sdk.is_dir(base_path) then return false end
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not sdk.is_dir(full_path) then return false end
    end
    return true
end

-- Verbose variant for logging which list is being checked
local function check_dirs_exist_verbose(base_path, required_dirs, list_name)
    if not sdk.is_dir(base_path) then return false end
    local missing = {}
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not sdk.is_dir(full_path) then table.insert(missing, dir_name) end
    end
    if #missing == 0 then
        Utils.colour_print{colour=Colours.GREEN, message=(list_name and ("All %d required '%s' subdirectories found in '"..base_path.."'."):format(#required_dirs, list_name) or ("All %d required subdirectories found in '"..base_path.."'."):format(#required_dirs))}
        return true
    end
    return false
end

-- TOML helpers via engine SDK
local function read_placeholders(cfg_path)
    local doc = sdk.toml_read_file(cfg_path)
    if not doc then return {} end
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
    local doc = {}
    doc["placeholders"] = { new_placeholders }
    sdk.toml_write_file(cfg_path, doc)
end

-- Count files recursively (files only)
local function count_files(path)
    local count = 0
    for _, file in ipairs(sdk.list_dir(path)) do
        local full = join(path, file)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "file" then
            count = count + 1
        elseif attr and attr.mode == "directory" then
            count = count + count_files(full)
        end
    end
    return count
end


-- Check if a folder contains USRDIR, PARAM.SFO, and at least one PNG (PS3_GAME folder structure)
local function is_ps3_game_folder(path)
    if not sdk.is_dir(path) then return false end
    local has_usrdir = sdk.is_dir(join(path, "USRDIR"))
    local has_sfo = sdk.path_exists(join(path, "PARAM.SFO"))
    local has_png = false
    -- Check for any PNG file
    for _, file in ipairs(sdk.list_dir(path)) do
        if file:match("%.png$") or file:match("%.PNG$") then
            has_png = true
            break
        end
    end
    return has_usrdir and has_sfo and has_png
end

-- Validate and resolve the source path, checking multiple possible locations for USRDIR
-- Returns: ok (bool), usrdir_path (for validation), folder_to_copy (the PS3_GAME parent folder)
local function validate_source_path(path)
    if not path or path == "" or not sdk.is_dir(path) then return false, path, path end

    -- Check if path itself is USRDIR (has game directories)
    local ok = check_dirs_exist(path, USRDIR_DIRS_ORIGINAL) or check_dirs_exist(path, USRDIR_DIRS)
    if ok then
        -- This is the USRDIR folder, so copy its parent (PS3_GAME)
        local parent = Utils.dirname(path)
        if is_ps3_game_folder(parent) then
            return true, path, parent
        end
        -- Fallback if parent doesn't have PS3_GAME structure
        return true, path, path
    end

    -- Check if path contains USRDIR subfolder (this is PS3_GAME folder)
    local usrdir = join(path, "USRDIR")
    if sdk.is_dir(usrdir) then
        ok = check_dirs_exist(usrdir, USRDIR_DIRS_ORIGINAL) or check_dirs_exist(usrdir, USRDIR_DIRS)
        if ok and is_ps3_game_folder(path) then
            -- This is the PS3_GAME folder itself, copy this folder
            return true, usrdir, path
        end
    end

    -- Check path/PS3_GAME/USRDIR (for disc root like D:\)
    local ps3_game = join(path, "PS3_GAME")
    if sdk.is_dir(ps3_game) then
        local ps3_usrdir = join(path, "PS3_GAME", "USRDIR")
        if sdk.is_dir(ps3_usrdir) then
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
    local module_dir = Utils.dirname(script_dir)
    local cfg_path = join(module_dir, "config.toml")

    -- Ensure config.toml exists with a placeholders block
    if not sdk.path_exists(cfg_path) then
        Utils.colour_print{colour=Colours.YELLOW, message="Config not found. Creating: " .. cfg_path}
        -- Include isRenamed = "notRenamed" by default
        write_placeholders(cfg_path, { MainSourcePath = "", SourcePath = "", PostSourcePath = "", Region = "", isRenamed = "notRenamed" })
        Utils.colour_print{colour=Colours.GREEN, message="Created config.toml with default placeholders."}
    end

    Utils.colour_print{colour=Colours.BLUE, message="Reading module config: " .. cfg_path}
    local placeholders = read_placeholders(cfg_path)
    -- Auto-add with defaults if missing
    local defaults = {
        isRenamed = "notRenamed",
        num = "1",
        audio_state = "audio_none",
        Type = "Full"
    }

    local updated = false
    for k, v in pairs(defaults) do
        if placeholders[k] == nil then
            placeholders[k] = v
            Utils.colour_print{colour=Colours.GREEN, message="Initialized placeholders." .. k .. " = \"" .. v .. "\""}
            updated = true
        end
    end

    if updated then
        write_placeholders(cfg_path, placeholders)
    end

    -- ensure out placeholder exists if not set
    --if placeholders["STROUT"] == nil then
    --    placeholders["STROUT"] = "STROUT"
    --    write_placeholders(cfg_path,placeholders)
    --    Utils.colour_print{colour=Colours.GREEN, message="Initialized placeholders.STROUT = \"STROUT\""}
    --end

    local region = normalize_region(placeholders["Region"])
    if region then
        placeholders["Region"] = region
    else
        Utils.colour_print{colour=Colours.YELLOW, message="No valid Region set in config.toml. You'll be prompted to set one (US, EU, or Both)."}
                while true do
            local input = get_input("Enter the game region (US, EU, or Both) and press Enter (leave blank to cancel):", "tsg_region")
            if not input or input == "" then
                Utils.colour_print{colour=Colours.RED, message="Initialization aborted: no valid Region provided."}
                Utils.colour_print{colour=Colours.YELLOW, message="Please update '" .. cfg_path .. "' with Region = \"US\", \"EU\", or \"Both\" and re-run this initializer."}
                return false
            end
            local normalized = normalize_region(input)
            if normalized then
                region = normalized
                if region == "BOTH" then
                    placeholders["Region"] = "EU" -- store EU as primary for "Both"
                else
                    placeholders["Region"] = region
                end
                write_placeholders(cfg_path, placeholders)
                Utils.colour_print{colour=Colours.GREEN, message="Set Region to '" .. region .. "'."}
                break
            else
                Utils.colour_print{colour=Colours.RED, message="Invalid region. Please enter 'US', 'EU', or 'Both'."}
            end
        end
    end

    -- Define local_data_path AFTER region is known
    -- For "Both" region, create separate EU and US directories, but use EU as primary
    local local_data_path_eu = Utils.normalize(join(module_dir, "Source", "EU"))
    local local_data_path_us = Utils.normalize(join(module_dir, "Source", "US"))
    local local_data_path = (region == "BOTH") and local_data_path_eu or Utils.normalize(join(module_dir, "Source", region))

    Utils.colour_print(placeholders)
    local existing = placeholders["MainSourcePath"]
    local copy_source_root = nil -- exact folder provided by user (or existing), used for copy/move semantics

    -- Phase A: If existing MainSourcePath is invalid/missing, prompt user to provide a valid path
    local path_from_config = nil
    local path_from_config_us = nil -- For "Both" region only

    -- Handle "Both" region - need to get both EU and US paths
    if region == "BOTH" then
        Utils.colour_print{colour=Colours.CYAN, message="\n--- Setting up BOTH regions (EU and US) ---"}
        Utils.colour_print{colour=Colours.YELLOW, message="You will be prompted to provide paths for both EU and US versions."}
        Utils.colour_print{colour=Colours.YELLOW, message="The EU version will be used as the primary source path."}

        -- Get EU path
        Utils.colour_print{colour=Colours.MAGENTA, message="\n--- EU Version ---"}
        while not path_from_config do
            local input = prompt("Enter the path to your EU game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
            if not input or input == "" then
                Utils.colour_print{colour=Colours.RED, message="Initialization aborted: no valid EU path provided."}
                return false
            end
            -- Trim and normalize the input path
            input = Utils.trim(input)
            input = Utils.normalize(Utils.is_absolute(input) and input or join(sdk.currentdir(), input))
            Utils.colour_print{colour=Colours.CYAN, message="Checking path: '" .. input .. "'"}
            if  sdk.is_dir(input) then
                local ok, resolved, folder_to_copy = validate_source_path(input)
                if ok then
                    path_from_config = Utils.normalize(resolved)
                    copy_source_root = folder_to_copy
                    Utils.colour_print{colour=Colours.GREEN, message="EU path validated: '" .. path_from_config .. "'"}
                    if path_from_config ~= input then
                        Utils.colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. Utils.basename(copy_source_root) .. "'"}
                    end
                else
                    Utils.colour_print{colour=Colours.RED, message="The provided path does not look like a valid game root/USRDIR. Please try again."}
                end
            else
                Utils.colour_print{colour=Colours.RED, message="The provided path is not a directory. Please try again."}
            end
        end

        -- Get US path
        Utils.colour_print{colour=Colours.MAGENTA, message="\n--- US Version ---"}
        local copy_source_root_us = nil
        while not path_from_config_us do
            local input = prompt("Enter the path to your US game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
            if not input or input == "" then
                Utils.colour_print{colour=Colours.RED, message="Initialization aborted: no valid US path provided."}
                return false
            end
            -- Trim and normalize the input path
            input = Utils.trim(input)
            input = Utils.normalize(Utils.is_absolute(input) and input or join(sdk.currentdir(), input))
            Utils.colour_print{colour=Colours.CYAN, message="Checking path: '" .. input .. "'"}
            if  sdk.is_dir(input) then
                local ok, resolved, folder_to_copy = validate_source_path(input)
                if ok then
                    path_from_config_us = Utils.normalize(resolved)
                    copy_source_root_us = folder_to_copy
                    Utils.colour_print{colour=Colours.GREEN, message="US path validated: '" .. path_from_config_us .. "'"}
                    if path_from_config_us ~= input then
                        Utils.colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. Utils.basename(copy_source_root_us) .. "'"}
                    end
                else
                    Utils.colour_print{colour=Colours.RED, message="The provided path does not look like a valid game root/USRDIR. Please try again."}
                end
            else
                Utils.colour_print{colour=Colours.RED, message="The provided path is not a directory. Please try again."}
            end
        end

        -- Store US source root for later copy/move operation
        placeholders["_temp_us_source_root"] = copy_source_root_us
        placeholders["_temp_us_path"] = path_from_config_us
    else
        -- Single region mode (existing logic)
        if existing and existing ~= "" then
        existing = Utils.normalize(existing)
        copy_source_root = existing
        local ok, resolved, folder_to_copy = validate_source_path(existing)
        if ok then
            path_from_config = Utils.normalize(resolved)
            copy_source_root = folder_to_copy -- Update to use the folder that should be copied
            if path_from_config ~= existing then
                Utils.colour_print{colour=Colours.YELLOW, message="Detected USRDIR under provided path; using '" .. path_from_config .. "' as source root."}
                Utils.colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. Utils.basename(copy_source_root) .. "'"}
            end
        else
            Utils.colour_print{colour=Colours.YELLOW, message="Existing MainSourcePath is not valid. You'll be prompted to set a valid one."}
        end
        else
            Utils.colour_print{colour=Colours.YELLOW, message="No MainSourcePath set in config.toml. You'll be prompted to set one."}
        end

        while not path_from_config do
            local input = prompt("Enter the path to your game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
            if not input or input == "" then
                Utils.colour_print{colour=Colours.RED, message="Initialization aborted: no valid MainSourcePath is configured and no input was provided."}
                Utils.colour_print{colour=Colours.YELLOW, message="Please update '" .. cfg_path .. "' with a valid MainSourcePath and re-run this initializer."}
                return false
            end
            -- Trim and normalize the input path
            input = Utils.trim(input)
            input = Utils.normalize(Utils.is_absolute(input) and input or join(sdk.currentdir(), input))
            Utils.colour_print{colour=Colours.CYAN, message="Checking path: '" .. input .. "'"}
            if  sdk.is_dir(input) then
                local ok, resolved, folder_to_copy = validate_source_path(input)
                if ok then
                    path_from_config = Utils.normalize(resolved)
                    copy_source_root = folder_to_copy -- Use the folder that should be copied
                    if path_from_config ~= input then
                        Utils.colour_print{colour=Colours.YELLOW, message="Detected USRDIR under provided path; using '" .. path_from_config .. "' as source root."}
                        Utils.colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. Utils.basename(copy_source_root) .. "'"}
                    end
                else
                    Utils.colour_print{colour=Colours.RED, message="The provided path does not look like a valid game root/USRDIR. Please try again."}
                end
            else
                Utils.colour_print{colour=Colours.RED, message="The provided path is not a directory. Please try again."}
            end
        end
    end

    -- Phase B: Offer to Copy/Move/Use-in-place into local workspace under the module
    Utils.colour_print{colour=Colours.MAGENTA, message="\n--- Source Path Handling ---"}
    Utils.colour_print{colour=Colours.CYAN, message="Validated source path (EU): '" .. path_from_config .. "'"}
    if path_from_config_us then
        Utils.colour_print{colour=Colours.CYAN, message="Validated source path (US): '" .. path_from_config_us .. "'"}
    end
    Utils.colour_print{colour=Colours.CYAN, message="Local project data path: '" .. local_data_path .. "'"}

    local effective_source_path = path_from_config
    local effective_source_path_us = nil

    -- If SourcePath is already inside local_data_path, assume it was set to local previously
    local function starts_with(a, b)
        return a:sub(1, #b):lower() == b:lower()
    end

    -- Process EU files (always)
    if not starts_with(path_from_config, local_data_path) then
        if not sdk.path_exists(local_data_path) then
            Utils.colour_print{colour=Colours.YELLOW, message="\n" .. (region == "BOTH" and "EU Region - " or "") .. "Choose how to use the source files:"}
            local display_name = Utils.basename(copy_source_root or path_from_config)

            -- Check if source path is writable (not read-only like an ISO)
            local source_is_writable = sdk and sdk.is_writable and sdk.is_writable(copy_source_root or path_from_config) or false

            -- Build options based on writability
            local options = {}
            table.insert(options, {id = "1", label = "Copy folder '" .. display_name .. "' into local '" .. Utils.basename(local_data_path) .. "' (Recommended, Safe)"})

            local auto_choice = nil
            if source_is_writable then
                table.insert(options, {id = "2", label = "Move folder '" .. display_name .. "' into local '" .. Utils.basename(local_data_path) .. "' (Warning: Deletes originals)"})
                table.insert(options, {id = "3", label = "Use original path '" .. display_name .. "' directly (Warning: Tools may modify original files)"})
            else
                Utils.colour_print{colour=Colours.YELLOW, message="  Note: Source is read-only (e.g., ISO/disc). Automatically selecting Copy option."}
                auto_choice = '1'
            end

            -- Display options and build prompt message
            local prompt_msg = "Choose how to use the source files:\n"
            if not auto_choice then
                for _, opt in ipairs(options) do
                    Utils.colour_print{colour=Colours.CYAN, message="  " .. opt.id .. ") " .. opt.label}
                    prompt_msg = prompt_msg .. opt.id .. ") " .. opt.label .. "\n"
                end
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

            prompt_msg = prompt_msg .. "\nEnter your choice (" .. choices_str .. "):"

            while true do
                local choice = auto_choice or Utils.trim(prompt(prompt_msg, "Source Option") or "")
                if choice == '1' then
                    local src = Utils.normalize(copy_source_root or path_from_config)
                    local src_name = Utils.basename(src)
                    local dst = join(local_data_path, src_name) -- Nest the folder inside Source
                    Utils.colour_print{colour=Colours.BLUE, message="Copying folder '" .. src_name .. "' into '" .. local_data_path .. "'..."}
                    sdk.ensure_dir(local_data_path)
                    local copied = false
                    if sdk and sdk.copy_dir then
                        -- Use engine SDK to bypass sandbox file IO restrictions
                        local ok = sdk.copy_dir(src, dst, true)
                        if not ok then
                            Utils.colour_print{colour=Colours.RED, message="Copy via SDK failed. Falling back to Lua copy (may be restricted)."}
                        else
                            copied = true
                        end
                    end
                    if not copied then
                        local total = count_files(src)
                        local state = { count = 0 }
                        sdk.ensure_dir(dst)
                        -- copy entire folder to dst preserving structure
                        Utils.copy_tree(src, dst, total, state)
                    end
                    if io and type(io.write) == "function" then io.write("\n") end
                    if io and type(io.flush) == "function" then io.flush() end -- todo: update to use sdk file handler as io.flush is disabled
                    Utils.colour_print{colour=Colours.GREEN, message="Copy complete."}
                    -- Set effective_source_path to the USRDIR inside the copied folder
                    local copied_usrdir = join(dst, "USRDIR")
                    if  sdk.is_dir(copied_usrdir) then
                        effective_source_path = copied_usrdir
                    else
                        effective_source_path = dst
                    end
                    break
                elseif choice == '2' and source_is_writable then
                    local src = Utils.normalize(copy_source_root or path_from_config)
                    local target_dir = join(local_data_path, Utils.basename(src))
                    Utils.colour_print{colour=Colours.YELLOW, message="Moving folder '" .. Utils.basename(src) .. "' into '" .. local_data_path .. "'..."}
                    sdk.ensure_dir(local_data_path)
                    local ok_move = false
                    if sdk and sdk.move_dir then
                        -- Move into a nested target under local_data_path to preserve original folder name
                        ok_move = sdk.move_dir(src, target_dir, true)
                    else
                        ok_move = Utils.move_tree(src, local_data_path)
                    end
                    if ok_move then
                        local moved_dir = target_dir
                        Utils.colour_print{colour=Colours.GREEN, message="Move complete."}
                        -- Set effective_source_path to the USRDIR inside the moved folder
                        local moved_usrdir = join(moved_dir, "USRDIR")
                        if  sdk.is_dir(moved_usrdir) then
                            effective_source_path = moved_usrdir
                        elseif ends_with_usrdir(moved_dir) then
                            effective_source_path = moved_dir
                        else
                            effective_source_path = moved_dir
                        end
                        break
                    else
                        Utils.colour_print{colour=Colours.RED, message="Move failed. Please check permissions/paths and try again."}
                    end
                elseif choice == '3' and source_is_writable then
                    Utils.colour_print{colour=Colours.YELLOW, message="Using original path directly."}
                    effective_source_path = path_from_config
                    break
                else
                    Utils.colour_print{colour=Colours.YELLOW, message="Invalid choice. Please enter " .. choices_str .. "."}
                end
            end
        else
            -- Local data already exists; try to point to the correct subdir
            local direct_usrdir = join(local_data_path, "USRDIR")
            if  sdk.is_dir(direct_usrdir) then
                effective_source_path = direct_usrdir
            else
                local subs = Utils.list_subdirs(local_data_path)
                if #subs == 1 then
                    local only = join(local_data_path, subs[1])
                    if  sdk.is_dir(join(only, "USRDIR")) then
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

    -- Process US files if region is "Both"
    if region == "BOTH" and path_from_config_us then
        local us_source_root = placeholders["_temp_us_source_root"]
        local us_path = placeholders["_temp_us_path"]

        if not starts_with(us_path, local_data_path_us) then
            if not sdk.path_exists(local_data_path_us) then
                Utils.colour_print{colour=Colours.YELLOW, message="\nUS Region - Choose how to use the source files:"}
                local display_name_us = Utils.basename(us_source_root or us_path)

                local source_is_writable_us = sdk and sdk.is_writable and sdk.is_writable(us_source_root or us_path) or false

                local options_us = {}
                table.insert(options_us, {id = "1", label = "Copy folder '" .. display_name_us .. "' into local 'US' (Recommended, Safe)"})

                local auto_choice_us = nil
                if source_is_writable_us then
                    table.insert(options_us, {id = "2", label = "Move folder '" .. display_name_us .. "' into local 'US' (Warning: Deletes originals)"})
                    table.insert(options_us, {id = "3", label = "Use original path '" .. display_name_us .. "' directly (Warning: Tools may modify original files)"})
                else
                    Utils.colour_print{colour=Colours.YELLOW, message="  Note: Source is read-only (e.g., ISO/disc). Automatically selecting US Copy option."}
                    auto_choice_us = '1'
                end

                local prompt_msg_us = "Choose how to use the US source files:\n"
                if not auto_choice_us then
                    for _, opt in ipairs(options_us) do
                        Utils.colour_print{colour=Colours.CYAN, message="  " .. opt.id .. ") " .. opt.label}
                        prompt_msg_us = prompt_msg_us .. opt.id .. ") " .. opt.label .. "\n"
                    end
                end

                local valid_choices_us = {}
                for _, opt in ipairs(options_us) do
                    table.insert(valid_choices_us, opt.id)
                end
                local choices_str_us = table.concat(valid_choices_us, ", ")
                if #valid_choices_us == 1 then
                    choices_str_us = valid_choices_us[1]
                elseif #valid_choices_us == 2 then
                    choices_str_us = valid_choices_us[1] .. " or " .. valid_choices_us[2]
                else
                    choices_str_us = table.concat(valid_choices_us, ", ", 1, #valid_choices_us - 1) .. ", or " .. valid_choices_us[#valid_choices_us]
                end

                prompt_msg_us = prompt_msg_us .. "\nEnter your choice for US region (" .. choices_str_us .. "):"

                while true do
                    local choice = auto_choice_us or Utils.trim(prompt(prompt_msg_us, "US Source Option") or "")
                    if choice == '1' then
                        local src = Utils.normalize(us_source_root or us_path)
                        local src_name = Utils.basename(src)
                        local dst = join(local_data_path_us, src_name)
                        Utils.colour_print{colour=Colours.BLUE, message="Copying US folder '" .. src_name .. "' into '" .. local_data_path_us .. "'..."}
                        sdk.ensure_dir(local_data_path_us)
                        local copied = false
                        if sdk and sdk.copy_dir then
                            local ok = sdk.copy_dir(src, dst, true)
                            if not ok then
                                Utils.colour_print{colour=Colours.RED, message="Copy via SDK failed. Falling back to Lua copy (may be restricted)."}
                            else
                                copied = true
                            end
                        end
                        if not copied then
                            local total = count_files(src)
                            local state = { count = 0 }
                            sdk.ensure_dir(dst)
                            Utils.copy_tree(src, dst, total, state)
                        end
                        if io and type(io.write) == "function" then io.write("\n") end
                        if io and type(io.flush) == "function" then io.flush() end
                        Utils.colour_print{colour=Colours.GREEN, message="US copy complete."}
                        local copied_usrdir = join(dst, "USRDIR")
                        if  sdk.is_dir(copied_usrdir) then
                            effective_source_path_us = copied_usrdir
                        else
                            effective_source_path_us = dst
                        end
                        break
                    elseif choice == '2' and source_is_writable_us then
                        local src = Utils.normalize(us_source_root or us_path)
                        local target_dir = join(local_data_path_us, Utils.basename(src))
                        Utils.colour_print{colour=Colours.YELLOW, message="Moving US folder '" .. Utils.basename(src) .. "' into '" .. local_data_path_us .. "'..."}
                        sdk.ensure_dir(local_data_path_us)
                        local ok_move = false
                        if sdk and sdk.move_dir then
                            ok_move = sdk.move_dir(src, target_dir, true)
                        else
                            ok_move = Utils.move_tree(src, local_data_path_us)
                        end
                        if ok_move then
                            Utils.colour_print{colour=Colours.GREEN, message="US move complete."}
                            local moved_usrdir = join(target_dir, "USRDIR")
                            if  sdk.is_dir(moved_usrdir) then
                                effective_source_path_us = moved_usrdir
                            elseif ends_with_usrdir(target_dir) then
                                effective_source_path_us = target_dir
                            else
                                effective_source_path_us = target_dir
                            end
                            break
                        else
                            Utils.colour_print{colour=Colours.RED, message="US move failed. Please check permissions/paths and try again."}
                        end
                    elseif choice == '3' and source_is_writable_us then
                        Utils.colour_print{colour=Colours.YELLOW, message="Using original US path directly."}
                        effective_source_path_us = us_path
                        break
                    else
                        Utils.colour_print{colour=Colours.YELLOW, message="Invalid choice. Please enter " .. choices_str_us .. "."}
                    end
                end
            else
                local direct_usrdir_us = join(local_data_path_us, "USRDIR")
                if  sdk.is_dir(direct_usrdir_us) then
                    effective_source_path_us = direct_usrdir_us
                else
                    local subs = Utils.list_subdirs(local_data_path_us)
                    if #subs == 1 then
                        local only = join(local_data_path_us, subs[1])
                        if  sdk.is_dir(join(only, "USRDIR")) then
                            effective_source_path_us = join(only, "USRDIR")
                        else
                            effective_source_path_us = only
                        end
                    else
                        effective_source_path_us = local_data_path_us
                    end
                end
            end
        else
            effective_source_path_us = us_path
        end

        -- Clean up temporary placeholders
        placeholders["_temp_us_source_root"] = nil
        placeholders["_temp_us_path"] = nil
    end

    -- Persist the effective SourcePath in config.toml as three components (EU path is primary)
    Utils.colour_print{colour=Colours.YELLOW, message="  Updating config.toml with effective Source Path..."}
    local base_source_dir = Utils.normalize(join(module_dir, "Source"))
    -- Calculate PostSourcePath relative to the region folder, not the Source folder
    local post_source_relative = Utils.get_relative_path(local_data_path, effective_source_path)

    placeholders["MainSourcePath"] = effective_source_path
    placeholders["SourcePath"] = base_source_dir
    placeholders["PostSourcePath"] = post_source_relative
    write_placeholders(cfg_path, placeholders)
    Utils.colour_print{colour=Colours.GREEN, message="  Config updated."}

    -- Final validation (switch to USRDIR if present) and persist validated path
    Utils.colour_print{colour=Colours.BLUE, message="\nValidating final source location: '" .. effective_source_path .. "'"}
    local potential_usrdir_path = join(effective_source_path, "USRDIR")
    local path_to_validate =  sdk.is_dir(potential_usrdir_path) and potential_usrdir_path or effective_source_path

    local found_original = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")
    local found_usrdir = false
    if not found_original then
        Utils.colour_print{colour=Colours.BLUE, message="  ORIGINAL list not fully present. Checking USRDIR_DIRS..."}
        found_usrdir = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")
    end

    if found_original or found_usrdir then
        local base_source_dir = Utils.normalize(join(module_dir, "Source"))
        -- Calculate PostSourcePath relative to the region folder, not the Source folder
        local post_source_relative = Utils.get_relative_path(local_data_path, path_to_validate)

        placeholders["MainSourcePath"] = path_to_validate
        placeholders["SourcePath"] = base_source_dir
        placeholders["PostSourcePath"] = post_source_relative
        write_placeholders(cfg_path, placeholders)
        Utils.colour_print{colour=Colours.GREEN, message="Success: Source validated and saved: " .. path_to_validate}
        return true
    else
        Utils.colour_print{colour=Colours.RED, message="Error: Validation failed for path '" .. path_to_validate .. "'."}
        Utils.colour_print{colour=Colours.YELLOW, message="Please verify the directory contents and re-run this initializer."}
        return false
    end
end

-- Execute immediately when run as a script
do
    local ok, result = pcall(main)
    if not ok then
        Utils.colour_print{colour=Colours.RED, message="Initialization failed with error: " .. tostring(result)}
        -- Non-zero exit so the host marks the operation as failed
        os.exit(1)
    end
    -- If main returned false (explicit failure), exit non-zero
    if result == false then
        os.exit(1)
    end
end
