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

---@type SharedUtils
require("SharedUtils")
---@type SharedUtilsColours
local Colours = Colours

---@type init
import("init/util")

---@class InitPlaceholders
---@field MainSourcePath string?
---@field SourcePath string?
---@field PostSourcePath string?
---@field Region string?
---@field isRenamed string?
---@field num string?
---@field audio_state string?
---@field Type string?
---@field _temp_us_source_root string?
---@field _temp_us_path string?

local function main()
    -- Determine module directory (two levels up from this script: operations/init.lua -> module root)
    local module_dir = dirname(script_dir)
    local cfg_path = normalize(join(module_dir, "config.toml"))

    -- Ensure config.toml exists with a placeholders block
    if not sdk.path_exists(cfg_path) then
        colour_print{colour=Colours.YELLOW, message="Config not found. Creating: " .. cfg_path}
        -- Include isRenamed = "notRenamed" by default
        write_placeholders(cfg_path, { MainSourcePath = "", SourcePath = "", PostSourcePath = "", Region = "", isRenamed = "notRenamed" })
        colour_print{colour=Colours.GREEN, message="Created config.toml with default placeholders."}
    end

    colour_print{colour=Colours.BLUE, message="Reading module config: " .. cfg_path}
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
            colour_print{colour=Colours.GREEN, message="Initialized placeholders." .. k .. " = \"" .. v .. "\""}
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
    --    colour_print{colour=Colours.GREEN, message="Initialized placeholders.STROUT = \"STROUT\""}
    --end

    local region = normalize_region(placeholders["Region"])
    if region then
        placeholders["Region"] = region
    else
        colour_print{colour=Colours.YELLOW, message="No valid Region set in config.toml. You'll be prompted to set one (US, EU, or Both)."}
                while true do
            local input = get_input("Enter the game region (US, EU, or Both) and press Enter (leave blank to cancel):", "tsg_region")
            if not input or input == "" then
                colour_print{colour=Colours.RED, message="Initialization aborted: no valid Region provided."}
                colour_print{colour=Colours.YELLOW, message="Please update '" .. cfg_path .. "' with Region = \"US\", \"EU\", or \"Both\" and re-run this initializer."}
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
                colour_print{colour=Colours.GREEN, message="Set Region to '" .. region .. "'."}
                break
            else
                colour_print{colour=Colours.RED, message="Invalid region. Please enter 'US', 'EU', or 'Both'."}
            end
        end
    end

    -- Define local_data_path AFTER region is known
    -- For "Both" region, create separate EU and US directories, but use EU as primary
    local local_data_path_eu = join(module_dir, "Source", "EU")
    local local_data_path_us = join(module_dir, "Source", "US")
    local local_data_path = (region == "BOTH") and local_data_path_eu or join(module_dir, "Source", region)

    colour_print(placeholders)
    local existing = placeholders["MainSourcePath"]
    local copy_source_root = nil -- exact folder provided by user (or existing), used for copy/move semantics

    -- Phase A: If existing MainSourcePath is invalid/missing, prompt user to provide a valid path
    local path_from_config = nil
    local path_from_config_us = nil -- For "Both" region only

    -- Handle "Both" region - need to get both EU and US paths
    if region == "BOTH" then
        colour_print{colour=Colours.CYAN, message="\n--- Setting up BOTH regions (EU and US) ---"}
        colour_print{colour=Colours.YELLOW, message="You will be prompted to provide paths for both EU and US versions."}
        colour_print{colour=Colours.YELLOW, message="The EU version will be used as the primary source path."}

        -- Get EU path
        colour_print{colour=Colours.MAGENTA, message="\n--- EU Version ---"}
        while not path_from_config do
            local input = prompt("Enter the path to your EU game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
            if not input or input == "" then
                colour_print{colour=Colours.RED, message="Initialization aborted: no valid EU path provided."}
                return false
            end
            -- Trim and normalize the input path
            input = trim(input)
            input = normalize(is_absolute(input) and input or join(sdk.currentdir(), input))
            colour_print{colour=Colours.CYAN, message="Checking path: '" .. input .. "'"}
            if  sdk.is_dir(input) then
                local ok, resolved, folder_to_copy = validate_source_path(input)
                if ok then
                    path_from_config = normalize(resolved)
                    copy_source_root = folder_to_copy
                    colour_print{colour=Colours.GREEN, message="EU path validated: '" .. path_from_config .. "'"}
                    if path_from_config ~= input then
                        colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. basename(copy_source_root) .. "'"}
                    end
                else
                    colour_print{colour=Colours.RED, message="The provided path does not look like a valid game root/USRDIR. Please try again."}
                end
            else
                colour_print{colour=Colours.RED, message="The provided path is not a directory. Please try again."}
            end
        end

        -- Get US path
        colour_print{colour=Colours.MAGENTA, message="\n--- US Version ---"}
        local copy_source_root_us = nil
        while not path_from_config_us do
            local input = prompt("Enter the path to your US game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
            if not input or input == "" then
                colour_print{colour=Colours.RED, message="Initialization aborted: no valid US path provided."}
                return false
            end
            -- Trim and normalize the input path
            input = trim(input)
            input = normalize(is_absolute(input) and input or join(sdk.currentdir(), input))
            colour_print{colour=Colours.CYAN, message="Checking path: '" .. input .. "'"}
            if  sdk.is_dir(input) then
                local ok, resolved, folder_to_copy = validate_source_path(input)
                if ok then
                    path_from_config_us = normalize(resolved)
                    copy_source_root_us = folder_to_copy
                    colour_print{colour=Colours.GREEN, message="US path validated: '" .. path_from_config_us .. "'"}
                    if path_from_config_us ~= input then
                        colour_print{colour=Colours.CYAN, message="Will copy folder: '" .. basename(copy_source_root_us) .. "'"}
                    end
                else
                    colour_print{colour=Colours.RED, message="The provided path does not look like a valid game root/USRDIR. Please try again."}
                end
            else
                colour_print{colour=Colours.RED, message="The provided path is not a directory. Please try again."}
            end
        end

        -- Store US source root for later copy/move operation
        placeholders["_temp_us_source_root"] = copy_source_root_us
        placeholders["_temp_us_path"] = path_from_config_us
    else
        -- Single region mode (existing logic)
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
            colour_print{colour=Colours.YELLOW, message="Existing MainSourcePath is not valid. You'll be prompted to set a valid one."}
        end
        else
            colour_print{colour=Colours.YELLOW, message="No MainSourcePath set in config.toml. You'll be prompted to set one."}
        end

        while not path_from_config do
            local input = prompt("Enter the path to your game root (this folder should contain a folder named USRDIR) and press Enter (leave blank to cancel):")
            if not input or input == "" then
                colour_print{colour=Colours.RED, message="Initialization aborted: no valid MainSourcePath is configured and no input was provided."}
                colour_print{colour=Colours.YELLOW, message="Please update '" .. cfg_path .. "' with a valid MainSourcePath and re-run this initializer."}
                return false
            end
            -- Trim and normalize the input path
            input = trim(input)
            input = normalize(is_absolute(input) and input or join(sdk.currentdir(), input))
            colour_print{colour=Colours.CYAN, message="Checking path: '" .. input .. "'"}
            if  sdk.is_dir(input) then
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
    end

    -- Phase B: Offer to Copy/Move/Use-in-place into local workspace under the module
    colour_print{colour=Colours.MAGENTA, message="\n--- Source Path Handling ---"}
    colour_print{colour=Colours.CYAN, message="Validated source path (EU): '" .. path_from_config .. "'"}
    if path_from_config_us then
        colour_print{colour=Colours.CYAN, message="Validated source path (US): '" .. path_from_config_us .. "'"}
    end
    colour_print{colour=Colours.CYAN, message="Local project data path: '" .. local_data_path .. "'"}

    local effective_source_path = path_from_config
    local effective_source_path_us = nil

    -- If SourcePath is already inside local_data_path, assume it was set to local previously
    ---@param a string|nil
    ---@param b string|nil
    ---@return boolean
    local function starts_with(a, b)
        if not a or not b then
            return false
        end
        return a:sub(1, #b):lower() == b:lower()
    end

    -- Process EU files (always)
    if not starts_with(path_from_config, local_data_path) then
        if not sdk.path_exists(local_data_path) then
            colour_print{colour=Colours.YELLOW, message="\n" .. (region == "BOTH" and "EU Region - " or "") .. "Choose how to use the source files:"}
            local display_name = basename(copy_source_root or path_from_config)

            -- Check if source path is writable (not read-only like an ISO)
            local source_is_writable = sdk.is_writable(copy_source_root or path_from_config)

            -- Build options based on writability
            local options = {}
            table.insert(options, {id = "1", label = "Copy folder '" .. display_name .. "' into local '" .. basename(local_data_path) .. "' (Recommended, Safe)"})

            local auto_choice = nil
            if source_is_writable then
                table.insert(options, {id = "2", label = "Move folder '" .. display_name .. "' into local '" .. basename(local_data_path) .. "' (Warning: Deletes originals)"})
                table.insert(options, {id = "3", label = "Use original path '" .. display_name .. "' directly (Warning: Tools may modify original files)"})
            else
                colour_print{colour=Colours.YELLOW, message="  Note: Source is read-only (e.g., ISO/disc). Automatically selecting Copy option."}
                auto_choice = '1'
            end

            -- Display options and build prompt message
            local prompt_msg = "Choose how to use the source files:\n"
            if not auto_choice then
                for _, opt in ipairs(options) do
                    colour_print{colour=Colours.CYAN, message="  " .. opt.id .. ") " .. opt.label}
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
                local choice = auto_choice or trim(prompt(prompt_msg, "Source Option") or "")
                if choice == '1' then
                    local src = normalize(copy_source_root or path_from_config)
                    local src_name = basename(src)
                    local dst = join(local_data_path, src_name) -- Nest the folder inside Source
                    colour_print{colour=Colours.BLUE, message="Copying folder '" .. src_name .. "' into '" .. local_data_path .. "'..."}
                    sdk.ensure_dir(local_data_path)
                    local copied = false
                    -- Use engine SDK to bypass sandbox file IO restrictions
                    local ok = sdk.copy_dir(src, dst, true)
                    if not ok then
                        colour_print{colour=Colours.RED, message="Copy via SDK failed. Falling back to Lua copy (may be restricted)."}
                    else
                        copied = true
                    end
                    if not copied then
                        local total = count_files(src)
                        local state = { count = 0 }
                        sdk.ensure_dir(dst)
                        -- copy entire folder to dst preserving structure
                        copy_tree(src, dst, total, state)
                    end
                    if io and type(io.write) == "function" then io.write("\n") end
                    --if io and type(io.flush) == "function" then io.flush() end
                    colour_print{colour=Colours.GREEN, message="Copy complete."}
                    -- Set effective_source_path to the USRDIR inside the copied folder
                    local copied_usrdir = join(dst, "USRDIR")
                    if  sdk.is_dir(copied_usrdir) then
                        effective_source_path = copied_usrdir
                    else
                        effective_source_path = dst
                    end
                    break
                elseif choice == '2' and source_is_writable then
                    local src = normalize(copy_source_root or path_from_config)
                    local target_dir = join(local_data_path, basename(src))
                    colour_print{colour=Colours.YELLOW, message="Moving folder '" .. basename(src) .. "' into '" .. local_data_path .. "'..."}
                    sdk.ensure_dir(local_data_path)
                    local ok_move = false
                    -- Move into a nested target under local_data_path to preserve original folder name
                    ok_move = sdk.move_dir(src, target_dir, true)
                    if ok_move then
                        local moved_dir = target_dir
                        colour_print{colour=Colours.GREEN, message="Move complete."}
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
            if sdk.is_dir(direct_usrdir) then
                effective_source_path = direct_usrdir
            else
                local subs = list_subdirs(local_data_path)
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
                colour_print{colour=Colours.YELLOW, message="\nUS Region - Choose how to use the source files:"}
                local display_name_us = basename(us_source_root or us_path)

                local source_is_writable_us = sdk.is_writable(us_source_root or us_path)

                local options_us = {}
                table.insert(options_us, {id = "1", label = "Copy folder '" .. display_name_us .. "' into local 'US' (Recommended, Safe)"})

                local auto_choice_us = nil
                if source_is_writable_us then
                    table.insert(options_us, {id = "2", label = "Move folder '" .. display_name_us .. "' into local 'US' (Warning: Deletes originals)"})
                    table.insert(options_us, {id = "3", label = "Use original path '" .. display_name_us .. "' directly (Warning: Tools may modify original files)"})
                else
                    colour_print{colour=Colours.YELLOW, message="  Note: Source is read-only (e.g., ISO/disc). Automatically selecting US Copy option."}
                    auto_choice_us = '1'
                end

                local prompt_msg_us = "Choose how to use the US source files:\n"
                if not auto_choice_us then
                    for _, opt in ipairs(options_us) do
                        colour_print{colour=Colours.CYAN, message="  " .. opt.id .. ") " .. opt.label}
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
                    local choice = auto_choice_us or trim(prompt(prompt_msg_us, "US Source Option") or "")
                    if choice == '1' then
                        local src = normalize(us_source_root or us_path)
                        local src_name = basename(src)
                        local dst = join(local_data_path_us, src_name)
                        colour_print{colour=Colours.BLUE, message="Copying US folder '" .. src_name .. "' into '" .. local_data_path_us .. "'..."}
                        sdk.ensure_dir(local_data_path_us)
                        local copied = false
                        local ok = sdk.copy_dir(src, dst, true)
                        if not ok then
                            colour_print{colour=Colours.RED, message="Copy via SDK failed. Falling back to Lua copy (may be restricted)."}
                        else
                            copied = true
                        end
                        if not copied then
                            local total = count_files(src)
                            local state = { count = 0 }
                            sdk.ensure_dir(dst)
                            copy_tree(src, dst, total, state)
                        end
                        if io and type(io.write) == "function" then io.write("\n") end
                        --if io and type(io.flush) == "function" then io.flush() end
                        colour_print{colour=Colours.GREEN, message="US copy complete."}
                        local copied_usrdir = normalize(join(dst, "USRDIR"))
                        if  sdk.is_dir(copied_usrdir) then
                            effective_source_path_us = copied_usrdir
                        else
                            effective_source_path_us = dst
                        end
                        break
                    elseif choice == '2' and source_is_writable_us then
                        local src = normalize(us_source_root or us_path)
                        local target_dir = normalize(join(local_data_path_us, basename(src)))
                        colour_print{colour=Colours.YELLOW, message="Moving US folder '" .. basename(src) .. "' into '" .. local_data_path_us .. "'..."}
                        sdk.ensure_dir(local_data_path_us)
                        local ok_move = false
                        ok_move = sdk.move_dir(src, target_dir, true) colour_print{colour=Colours.GREEN, message="US move complete."}
                        local moved_usrdir = normalize(join(target_dir, "USRDIR"))
                        if  sdk.is_dir(moved_usrdir) then
                            effective_source_path_us = moved_usrdir
                        elseif ends_with_usrdir(target_dir) then
                            effective_source_path_us = target_dir
                        else
                            effective_source_path_us = target_dir
                        end
                        break
                    elseif choice == '3' and source_is_writable_us then
                        colour_print{colour=Colours.YELLOW, message="Using original US path directly."}
                        effective_source_path_us = us_path
                        break
                    else
                        colour_print{colour=Colours.YELLOW, message="Invalid choice. Please enter " .. choices_str_us .. "."}
                    end
                end
            else
                local direct_usrdir_us = join(local_data_path_us, "USRDIR")
                if  sdk.is_dir(direct_usrdir_us) then
                    effective_source_path_us = direct_usrdir_us
                else
                    local subs = list_subdirs(local_data_path_us)
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
    colour_print{colour=Colours.YELLOW, message="  Updating config.toml with effective Source Path..."}
    local base_source_dir = join(module_dir, "Source")
    -- Calculate PostSourcePath relative to the region folder, not the Source folder
    local post_source_relative = get_relative_path(local_data_path, effective_source_path)

    placeholders["MainSourcePath"] = effective_source_path
    placeholders["SourcePath"] = base_source_dir
    placeholders["PostSourcePath"] = post_source_relative
    write_placeholders(cfg_path, placeholders)
    colour_print{colour=Colours.GREEN, message="  Config updated."}

    -- Final validation (switch to USRDIR if present) and persist validated path
    colour_print{colour=Colours.BLUE, message="\nValidating final source location: '" .. effective_source_path .. "'"}
    local potential_usrdir_path = join(effective_source_path, "USRDIR")
    local path_to_validate =  sdk.is_dir(potential_usrdir_path) and potential_usrdir_path or effective_source_path

    local found_original = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")
    local found_usrdir = false
    if not found_original then
        colour_print{colour=Colours.BLUE, message="  ORIGINAL list not fully present. Checking USRDIR_DIRS..."}
        found_usrdir = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")
    end

    if found_original or found_usrdir then
        local base_source_dir = join(module_dir, "Source")
        -- Calculate PostSourcePath relative to the region folder, not the Source folder
        local post_source_relative = get_relative_path(local_data_path, path_to_validate)

        placeholders["MainSourcePath"] = path_to_validate
        placeholders["SourcePath"] = base_source_dir
        placeholders["PostSourcePath"] = post_source_relative
        write_placeholders(cfg_path, placeholders)
        colour_print{colour=Colours.GREEN, message="Success: Source validated and saved: " .. path_to_validate}
        return true
    else
        colour_print{colour=Colours.RED, message="Error: Validation failed for path '" .. path_to_validate .. "'."}
        colour_print{colour=Colours.YELLOW, message="Please verify the directory contents and re-run this initializer."}
        return false
    end
end


local ok, result = pcall(main)
if not ok or not result then
    colour_print{colour=Colours.RED, message="Initialization failed with error: " .. tostring(result)}
    os.exit(1)
end
