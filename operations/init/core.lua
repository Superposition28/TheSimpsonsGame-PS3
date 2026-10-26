---@class InitPlaceholders
---@field MainSourcePath string?
---@field SourcePath string?
---@field PostSourcePath string?
---@field Platform string?
---@field Region string?
---@field isRenamed string?
---@field num string?
---@field audio_state string?
---@field Type string?

---@class InitSourceLocation
---@field resolved string
---@field copy_root string
---@field version_info GameVersionInfo|nil
---@field validation SourceValidationResult|nil

---@class InitCore
local Core = {}

---@param value string|nil
---@return ("PS3"|"XBOX360")|nil
local function NormalizePlatform(value)
    if type(value) ~= "string" then
        return nil
    end

    local cleaned = trim(value):upper()
    if cleaned == "PS3" then
        return "PS3"
    end
    if cleaned == "XBOX 360" or cleaned == "XBOX360" or cleaned == "XBOX" or cleaned == "360" then
        return "XBOX360"
    end
    return nil
end

---@param value string|nil
---@return ("copy"|"move"|"use")|nil
local function NormalizeAction(value)
    if type(value) ~= "string" then
        return nil
    end

    local cleaned = trim(value):lower()
    if cleaned == "1" or cleaned == "copy" then
        return "copy"
    end
    if cleaned == "2" or cleaned == "move" then
        return "move"
    end
    if cleaned == "3" or cleaned == "use" or cleaned == "original" or cleaned == "use-original" then
        return "use"
    end
    return nil
end

---@param path string|nil
---@return InitSourceLocation|nil location, SourceValidationResult|nil validation
local function ValidateInputPath(path)
    if type(path) ~= "string" or trim(path) == "" then
        return nil, nil
    end

    local cleaned = trim(path)
    local absolute_path = normalize(is_absolute(cleaned) and cleaned or join(sdk.currentdir(), cleaned))
    local validation = Inspect_source_path(absolute_path)
    if not validation.valid then
        return nil, validation
    end

    ---@type InitSourceLocation
    local location = {
        resolved = normalize(validation.resolved),
        copy_root = normalize(validation.copy_root),
        version_info = validation.version_info,
        validation = validation,
    }
    return location, validation
end

---@param configured_path string|nil
---@param supplied_path string|nil
---@param message string
---@param title string
---@return InitSourceLocation|nil
local function ResolveSourcePath(configured_path, supplied_path, message, title)
    if supplied_path ~= nil then
        local supplied, validation = ValidateInputPath(supplied_path)
        if supplied and validation then
            Print_version_report(validation)
            return supplied
        end

        colour_print({
            colour = Colours.RED,
            message = (validation and validation.error_message)
                or ("Invalid command-line source path: '" .. tostring(supplied_path) .. "'.")
        })
        return nil
    end

    if type(configured_path) == "string" and trim(configured_path) ~= "" then
        local configured, configured_validation = ValidateInputPath(configured_path)
        if configured and configured_validation then
            Print_version_report(configured_validation)
            return configured
        end
        if configured_validation and configured_validation.error_message then
            colour_print({
                colour = Colours.YELLOW,
                message = "Configured MainSourcePath is not valid (" .. configured_validation.error_message .. "). Prompting for a new path..."
            })
        end
    end

    while true do
        local input = prompt(message, title)
        if not input or trim(input) == "" then
            return nil
        end

        local prompted, validation = ValidateInputPath(input)
        if prompted and validation then
            Print_version_report(validation)
            return prompted
        end

        colour_print({
            colour = Colours.RED,
            message = (validation and validation.error_message)
                or "The provided path does not look like a valid game root/USRDIR. Please try again."
        })
    end
end

---@param path string
---@param root string
---@return boolean
local function StartsWithPath(path, root)
    return path:sub(1, #root):lower() == root:lower()
end

---@param local_data_path string
---@return string
local function ResolveExistingLocalPath(local_data_path)
    local direct_usrdir = join(local_data_path, "USRDIR")
    if sdk.is_dir(direct_usrdir) then
        return direct_usrdir
    end

    local subdirectories = list_subdirs(local_data_path)
    if #subdirectories == 1 then
        local only_directory = join(local_data_path, subdirectories[1])
        local nested_usrdir = join(only_directory, "USRDIR")
        return sdk.is_dir(nested_usrdir) and nested_usrdir or only_directory
    end

    return local_data_path
end

---@param path string
---@param expected_type ("Full"|"Demo")|nil
---@return string|nil
local function ValidateFinalSource(path, expected_type)
    local potential_usrdir = join(path, "USRDIR")
    local path_to_validate = sdk.is_dir(potential_usrdir) and potential_usrdir or path

    local has_executable = sdk.is_file(join(path_to_validate, "EBOOT.BIN"))
        or sdk.is_file(join(path_to_validate, "default.xex"))
    if not has_executable then
        colour_print({
            colour = Colours.RED,
            message = "Missing required executable ('EBOOT.BIN' or 'default.xex') in '" .. path_to_validate .. "'."
        })
        return nil
    end

    if expected_type == "Demo" then
        local found_demo = Check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_DEMO, "USRDIR_DIRS_DEMO")
        return found_demo and path_to_validate or nil
    end

    local found_original = Check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")
    local found_usrdir = not found_original and Check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")
    local found_demo = not found_original and not found_usrdir and Check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_DEMO, "USRDIR_DIRS_DEMO")
    return (found_original or found_usrdir or found_demo) and path_to_validate or nil
end

---@param source InitSourceLocation
---@param local_data_path string
---@param supplied_action string|nil
---@param label string
---@return string|nil
local function PlaceSource(source, local_data_path, supplied_action, label)
    if StartsWithPath(source.resolved, local_data_path) then
        return source.resolved
    end

    local action = NormalizeAction(supplied_action)
    if supplied_action ~= nil and action == nil then
        colour_print({
            colour = Colours.RED,
            message = "Invalid command-line " .. label .. " action: '" .. tostring(supplied_action) .. "'."
        })
        return nil
    end

    if action == nil and sdk.path_exists(local_data_path) then
        local existing_local = ResolveExistingLocalPath(local_data_path)
        local expected_type = source.version_info and source.version_info.game_type or nil
        if ValidateFinalSource(existing_local, expected_type) then
            return existing_local
        end
    end

    local source_is_writable = sdk.is_writable(source.copy_root)
    if action == nil and not source_is_writable then
        action = "copy"
    end

    while action == nil do
        local input = prompt("1) Copy\n2) Move\n3) Use Original\nEnter choice:", label .. " Source Option")
        action = NormalizeAction(input)
        if action == nil then
            colour_print({ colour = Colours.YELLOW, message = "Invalid choice. Please enter 1, 2, or 3." })
        end
    end

    if (action == "move" or action == "use") and not source_is_writable then
        colour_print({ colour = Colours.RED, message = "The " .. label .. " source is read-only and must be copied." })
        return nil
    end

    if action == "use" then
        return source.resolved
    end

    local destination = join(local_data_path, basename(source.copy_root))
    sdk.ensure_dir(local_data_path)
    if action == "copy" then
        if not sdk.copy_dir(source.copy_root, destination, true) then
            sdk.ensure_dir(destination)
            copy_tree(source.copy_root, destination, count_files(source.copy_root), { count = 0 })
        end
    elseif not sdk.move_dir(source.copy_root, destination, true) then
        colour_print({ colour = Colours.RED, message = "Failed to move " .. label .. " source." })
        return nil
    end

    local copied_usrdir = join(destination, "USRDIR")
    return sdk.is_dir(copied_usrdir) and copied_usrdir or destination
end

---@param cli_arguments InitCliArguments|nil
---@return boolean
function Core.main(cli_arguments)
    cli_arguments = cli_arguments or {}
    local module_dir = Game_Root
    local config_path = normalize(join(module_dir, "config.toml"))

    if not sdk.path_exists(config_path) then
        write_placeholders(config_path, {
            MainSourcePath = "",
            SourcePath = "",
            PostSourcePath = "",
            Platform = "",
            Region = "",
            isRenamed = "notRenamed",
            num = "1",
            audio_state = "audio_none",
            Type = "Full",
        })
    end

    ---@type InitPlaceholders
    local placeholders = Read_placeholders(config_path)
    local defaults = { Platform = "", Region = "", isRenamed = "notRenamed", num = "1", audio_state = "audio_none", Type = "Full" }
    for key, value in pairs(defaults) do
        if placeholders[key] == nil then
            placeholders[key] = value
        end
    end

    local cli_platform = NormalizePlatform(cli_arguments.platform)
    if cli_arguments.platform ~= nil and cli_platform == nil then
        colour_print({ colour = Colours.RED, message = "Invalid command-line platform: '" .. tostring(cli_arguments.platform) .. "'." })
        return false
    end

    local cli_region = Normalize_region(cli_arguments.region)
    if cli_arguments.region ~= nil and cli_region == nil then
        colour_print({ colour = Colours.RED, message = "Invalid command-line region: '" .. tostring(cli_arguments.region) .. "'." })
        return false
    end

    local prompt_msg = cli_region == "BOTH"
        and "Enter the path to your EU game root (ISO root, PS3_GAME, USRDIR, or extracted Xbox 360 folder):"
        or "Enter the path to your game root (ISO root, PS3_GAME, USRDIR, or extracted Xbox 360 folder):"
    local prompt_title = cli_region == "BOTH" and "EU File Path" or "Game Root Path"

    local primary_source = ResolveSourcePath(placeholders.MainSourcePath, cli_arguments.path, prompt_msg, prompt_title)
    if not primary_source then
        return false
    end

    local detected_info = primary_source.version_info

    -- Resolve Platform (prefer detected from source, fallback to CLI/config/prompt)
    ---@type ("PS3"|"XBOX360")|nil
    local platform = detected_info and detected_info.platform or cli_platform or NormalizePlatform(placeholders.Platform)
    if cli_platform and detected_info and cli_platform ~= detected_info.platform then
        colour_print({
            colour = Colours.YELLOW,
            message = string.format(
                "Warning: CLI specified platform '%s', but source files were detected as '%s'. Using '%s'.",
                cli_platform,
                detected_info.platform,
                detected_info.platform
            )
        })
    end
    while not platform do
        local input = prompt("Enter the game platform (PS3 or XBOX360):", "Game Platform")
        if not input or trim(input) == "" then
            return false
        end
        platform = NormalizePlatform(input)
        if not platform then
            colour_print({ colour = Colours.RED, message = "Invalid platform. Please enter PS3 or XBOX360." })
        end
    end

    -- Resolve Game Edition ("Full" or "Demo") for folder validation
    ---@type "Full"|"Demo"
    local game_edition = (detected_info and detected_info.game_type) or "Full"

    -- Resolve Region (prefer SFO/tree-detected region unless BOTH is requested; prompt only when SFO is absent)
    ---@type ("US"|"EU"|"DEMO"|"BOTH")|nil
    local region = nil
    if cli_region == "BOTH" or cli_arguments.us_path ~= nil then
        region = "BOTH"
    elseif detected_info and detected_info.region ~= nil then
        if cli_region ~= nil and cli_region ~= detected_info.region then
            colour_print({
                colour = Colours.YELLOW,
                message = string.format(
                    "Warning: CLI specified region '%s', but source was identified as '%s' (%s). Using '%s'.",
                    cli_region,
                    detected_info.region,
                    tostring(detected_info.title_id or detected_info.game_type or "SFO"),
                    detected_info.region
                )
            })
        end
        region = detected_info.region
    else
        region = cli_region or Normalize_region(placeholders.Region)
        while not region do
            local input = prompt("Enter the game region (US, EU, DEMO, or Both):", "Game Region")
            if not input or trim(input) == "" then
                return false
            end
            region = Normalize_region(input)
            if not region then
                colour_print({ colour = Colours.RED, message = "Invalid region. Please enter US, EU, DEMO, or Both." })
            end
        end

        if region == "DEMO" then
            game_edition = "Demo"
        end

        if platform == "PS3" then
            local resolved_reg = region == "BOTH" and "EU" or region
            ---@cast resolved_reg "EU"|"US"|"DEMO"
            local sup_level, sup_msg = build_support_info(platform, resolved_reg, game_edition, nil)
            colour_print({
                colour = sup_level == "full" and Colours.GREEN or Colours.YELLOW,
                message = "  " .. sup_msg
            })
        end
    end

    local instance_number = placeholders.num
    if type(instance_number) ~= "string" or not instance_number:match("^%d+$") then
        instance_number = "1"
    end

    local effective_region = region == "BOTH" and "EU" or region
    local source_platform_dir = join(module_dir, "Source", platform)
    local primary_region_root = join(source_platform_dir, effective_region)
    local primary_data_path = join(primary_region_root, instance_number)

    local effective_source = PlaceSource(primary_source, primary_data_path, cli_arguments.action, "Primary")
    if not effective_source then
        return false
    end

    if region == "BOTH" then
        local us_source = ResolveSourcePath(
            nil,
            cli_arguments.us_path,
            "Enter the path to your US game root (ISO root, PS3_GAME, USRDIR, or extracted Xbox 360 folder):",
            "US File Path"
        )
        if not us_source then
            return false
        end
        local us_region_root = join(source_platform_dir, "US")
        local us_data_path = join(us_region_root, instance_number)
        if not PlaceSource(us_source, us_data_path, cli_arguments.us_action, "US") then
            return false
        end
    end

    local validated_source = ValidateFinalSource(effective_source, game_edition)
    if not validated_source then
        colour_print({ colour = Colours.RED, message = "Source validation failed for '" .. effective_source .. "'." })
        return false
    end

    placeholders.Platform = platform
    placeholders.Region = effective_region
    if placeholders.Type ~= "Full" and placeholders.Type ~= "FullFlattened" then
        placeholders.Type = "Full"
    end
    placeholders.num = instance_number
    placeholders.MainSourcePath = validated_source
    placeholders.SourcePath = source_platform_dir
    placeholders.PostSourcePath = join(instance_number, get_relative_path(primary_data_path, validated_source))
    write_placeholders(config_path, placeholders)
    colour_print({ colour = Colours.GREEN, message = "Success: Source validated and saved: " .. validated_source })
    return true
end

return Core