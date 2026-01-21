-- Simple file/directory rename script using CLI arguments
-- Usage: --old_path <path> --new_path <path>

local old_path = nil
local new_path = nil

-- Parse command-line arguments
for i = 1, argc do
    local arg = argv[i]
    if arg == "--old_path" and i < argc then
        old_path = argv[i + 1]
    elseif arg == "--new_path" and i < argc then
        new_path = argv[i + 1]
    end
end

-- Validate arguments
if not old_path or not new_path then
    error("Usage: --old_path <path> --new_path <path>")
    return
end

-- Check if source exists
if not sdk.path_exists(old_path) then
    error("Source path does not exist: " .. old_path)
    return
end

-- Check if destination already exists
if sdk.path_exists(new_path) then
    error("Destination path already exists: " .. new_path)
    return
end

-- Perform rename
sdk.colour_print({ colour = "Cyan", message = "Renaming: " .. old_path })
sdk.colour_print({ colour = "Cyan", message = "      To: " .. new_path })

local success = sdk.rename_file(old_path, new_path)

if success then
    sdk.colour_print({ colour = "Green", message = "✓ Rename successful" })
else
    error("Failed to rename: " .. old_path)
end
