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

---@class InitCore
local Core = {}

---@param value string|nil
---@return string|nil
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
---@return string|nil
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
---@return InitSourceLocation|nil
local function ValidateInputPath(path)
    if type(path) ~= "string" or trim(path) == "" then
        return nil
    end

    local absolute_path = normalize(is_absolute(path) and path or join(sdk.currentdir(), path))
    if not sdk.is_dir(absolute_path) then
        return nil
    end

    local valid, resolved, copy_root = validate_source_path(absolute_path)
    if not valid then
        return nil
    end

    return {
        resolved = normalize(resolved),
        copy_root = normalize(copy_root)
    }
end

---@param configured_path string|nil
---@param supplied_path string|nil
---@param message string
---@param title string
---@return InitSourceLocation|nil
local function ResolveSourcePath(configured_path, supplied_path, message, title)
    if supplied_path ~= nil then
        local supplied = ValidateInputPath(supplied_path)
        if supplied then
            return supplied
        end

        colour_print({
            colour = Colours.RED,
            message = "Invalid command-line source path: '" .. tostring(supplied_path) .. "'."
        })
        return nil
    end

    local configured = ValidateInputPath(configured_path)
    if configured then
        return configured
    end

    while true do
        local input = prompt(message, title)
        if not input or trim(input) == "" then
            return nil
        end

        local prompted = ValidateInputPath(input)
        if prompted then
            return prompted
        end

        colour_print({
            colour = Colours.RED,
            message = "The provided path does not look like a valid game root/USRDIR. Please try again."
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

---@param source InitSourceLocation
---@param local_data_path string
---@param supplied_action string|nil
---@param label string
---@return string|nil
local function PlaceSource(source, local_data_path, supplied_action, label)
    if StartsWithPath(source.resolved, local_data_path) then
        return source.resolved
    end

    if sdk.path_exists(local_data_path) then
        return ResolveExistingLocalPath(local_data_path)
    end

    local source_is_writable = sdk.is_writable(source.copy_root)
    local action = NormalizeAction(supplied_action)
    if supplied_action ~= nil and action == nil then
        colour_print({
            colour = Colours.RED,
            message = "Invalid command-line " .. label .. " action: '" .. tostring(supplied_action) .. "'."
        })
        return nil
    end

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

---@param path string
---@return string|nil
local function ValidateFinalSource(path)
    local potential_usrdir = join(path, "USRDIR")
    local path_to_validate = sdk.is_dir(potential_usrdir) and potential_usrdir or path
    local found_original = check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")
    local found_usrdir = not found_original and check_dirs_exist_verbose(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")
    return (found_original or found_usrdir) and path_to_validate or nil
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
            isRenamed = "notRenamed"
        })
    end

    ---@type InitPlaceholders
    local placeholders = read_placeholders(config_path)
    local defaults = { Platform = "", Region = "", isRenamed = "notRenamed", num = "1", audio_state = "audio_none", Type = "Full" }
    for key, value in pairs(defaults) do
        if placeholders[key] == nil then
            placeholders[key] = value
        end
    end

    local platform = NormalizePlatform(cli_arguments.platform)
    if cli_arguments.platform ~= nil and platform == nil then
        colour_print({ colour = Colours.RED, message = "Invalid command-line platform: '" .. tostring(cli_arguments.platform) .. "'." })
        return false
    end
    platform = platform or NormalizePlatform(placeholders.Platform)
    while not platform do
        platform = NormalizePlatform(prompt("Enter the game platform (PS3 or XBOX360):", "Game Platform"))
    end

    local region = normalize_region(cli_arguments.region)
    if cli_arguments.region ~= nil and region == nil then
        colour_print({ colour = Colours.RED, message = "Invalid command-line region: '" .. tostring(cli_arguments.region) .. "'." })
        return false
    end
    region = region or normalize_region(placeholders.Region)
    while not region do
        region = normalize_region(prompt("Enter the game region (US, EU, or Both):", "Game Region"))
    end

    local instance_number = placeholders.num
    if type(instance_number) ~= "string" or not instance_number:match("^%d+$") then
        instance_number = "1"
    end

    local source_platform_dir = join(module_dir, "Source", platform)
    local eu_data_path = join(source_platform_dir, "EU", instance_number)
    local us_data_path = join(source_platform_dir, "US", instance_number)
    local primary_data_path = region == "BOTH" and eu_data_path or join(source_platform_dir, region, instance_number)
    local primary_source = ResolveSourcePath(placeholders.MainSourcePath, cli_arguments.path, region == "BOTH" and "Enter the path to your EU game root:" or "Enter the path to your game root:", region == "BOTH" and "EU File Path" or "Game Root Path")
    if not primary_source then
        return false
    end

    local effective_source = PlaceSource(primary_source, primary_data_path, cli_arguments.action, "Primary")
    if not effective_source then
        return false
    end

    if region == "BOTH" then
        local us_source = ResolveSourcePath(nil, cli_arguments.us_path, "Enter the path to your US game root:", "US File Path")
        if not us_source or not PlaceSource(us_source, us_data_path, cli_arguments.us_action, "US") then
            return false
        end
    end

    local validated_source = ValidateFinalSource(effective_source)
    if not validated_source then
        colour_print({ colour = Colours.RED, message = "Source validation failed for '" .. effective_source .. "'." })
        return false
    end

    placeholders.Platform = platform
    placeholders.Region = region == "BOTH" and "EU" or region
    placeholders.num = instance_number
    placeholders.MainSourcePath = validated_source
    placeholders.SourcePath = source_platform_dir
    placeholders.PostSourcePath = join(instance_number, get_relative_path(primary_data_path, validated_source))
    write_placeholders(config_path, placeholders)
    colour_print({ colour = Colours.GREEN, message = "Success: Source validated and saved: " .. validated_source })
    return true
end

return Core