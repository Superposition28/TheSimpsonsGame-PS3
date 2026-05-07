-- Simple file/directory rename script using CLI arguments
-- Usage: --old_path <path> --new_path <path>

---@type SharedUtils
import("./SharedUtils.lua")

---@type string|nil
local old_path = nil
---@type string|nil
local new_path = nil

---@param message string
---@return nil
local function Fail(message)
    error(message)
    os.exit(1)
end

-- Parse command-line arguments
for i = 1, argc do
    local arg = argv[i]
    if arg == "--old_path" and i < argc then
        old_path = normalize(argv[i + 1])
    elseif arg == "--new_path" and i < argc then
        new_path = normalize(argv[i + 1])
    end
end

-- Validate arguments
if not old_path or not new_path then
    Fail("Usage: --old_path <path> --new_path <path>")
end

-- Check if source exists
if not sdk.path_exists(old_path) then
    Fail("Source path does not exist: " .. old_path)
end

-- Check if destination already exists
if sdk.path_exists(new_path) then
    Fail("Destination path already exists: " .. new_path)
end

-- Perform rename
sdk.colour_print({ colour = "Cyan", message = "Renaming: " .. old_path })
sdk.colour_print({ colour = "Cyan", message = "      To: " .. new_path })

local success = sdk.rename_file(old_path, new_path, true) -- true = overwrite if exists (we already check for this, but just in case)

if success then
    sdk.colour_print({ colour = "Green", message = "✓ Rename successful" })
else
    Fail("Failed to rename: " .. old_path)
end
