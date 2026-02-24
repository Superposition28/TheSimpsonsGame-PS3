local path_sep = package.config:sub(1, 1)
local PREFIX = "BlenderUtils"
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

local M = {
    path_sep = path_sep,
    Colours = Colours
}

function M.log(colour, message)
    sdk.colour_print({ colour = colour or Colours.DEFAULT, message = string.format("[%s] %s", PREFIX, message or "") })
end

function M.normalize_separators(path)
    if not path then
        return path
    end
    if type(path) ~= "string" then
        path = tostring(path)
    end
    if path_sep == "\\" then
        path = path:gsub("/", "\\")
    else
        path = path:gsub("\\", "/")
    end
    return path
end

function M.ends_with(str, suffix)
    if not str or not suffix then
        return false
    end
    if #suffix == 0 then
        return true
    end
    if #str < #suffix then
        return false
    end
    return str:sub(-#suffix) == suffix
end

function M.parent_dir(path)
    if not path then
        return nil
    end
    local normalized = M.normalize_separators(path)
    local last_sep = 0
    for i = 1, #normalized do
        local ch = normalized:sub(i, i)
        if ch == '/' or ch == '\\' then last_sep = i end
    end
    if last_sep > 0 then
        local dir = normalized:sub(1, last_sep - 1)
        if #dir > 0 then return dir end
    end
    return nil
end

function M.is_absolute(path)
    if not path then
        return false
    end
    if path:match("^%a:[/\\]") then
        return true
    end
    if path:sub(1, 2) == "\\\\" then
        return true
    end
    if path:sub(1, 1) == "/" then
        return true
    end
    return false
end

function M.absolute_path(path)
    if not path then
        return path
    end
    -- Use sdk.realpath directly (always available in engine runtime)
    local resolved = sdk.realpath(path)
    local result = path
    if resolved and #resolved > 0 then
        result = resolved
    elseif not M.is_absolute(path) then
        local cwd = sdk.currentdir()
        result = cwd .. path_sep .. path
    end

    result = M.normalize_separators(result)

    -- Ensure \\?\ prefix on Windows for long path support in Blender 4.5+
    -- Only apply if the path is actually long (> 255 chars) to avoid "saved with @" errors for short paths.
    if path_sep == "\\" and result:match("^%a:") and not result:find("^\\\\%?\\") and #result > 255 then
        result = "\\\\?\\" .. result
    end

    return result
end

function M.join(...)
    local parts = { ... }
    local buffer = {}
    for index = 1, #parts do
        local part = parts[index]
        if part and part ~= "" then
            if type(part) ~= 'string' then
                part = tostring(part)
            end
            part = M.normalize_separators(part)
            if index > 1 then
                part = part:gsub("^" .. path_sep .. "+", "")
            end
            if index < #parts then
                part = part:gsub(path_sep .. "+$", "")
            end
            table.insert(buffer, part)
        end
    end
    return table.concat(buffer, path_sep)
end

function M.iterate_files(root_dir, visitor)
    if not sdk.is_dir(root_dir) then
        M.log(Colours.RED, string.format("Directory '%s' does not exist for iteration.", root_dir))
        return
    end

    local entries = sdk.list_dir(root_dir)
    for _, entry in ipairs(entries) do
        local full_path = M.join(root_dir, entry)
        if sdk.is_dir(full_path) then
            M.iterate_files(full_path, visitor)
        elseif sdk.is_file(full_path) then
            visitor(full_path, entry)
        end
    end
end

function M.to_long_path(path)
    if not path or path == "" or path_sep ~= "\\" then return path end
    if path:find("^\\\\%?\\") then return path end
    
    local normalized = M.normalize_separators(path)
    if normalized:match("^%a:") and #normalized > 255 then
        return "\\\\?\\" .. normalized
    end
    return normalized
end

function M.get_path(base_path, filename, extension)
    if not base_path or base_path == "" then return "" end
    base_path = M.normalize_separators(base_path)
    local expected_suffix = filename .. extension

    local lower_base = base_path:lower()
    local lower_suffix = expected_suffix:lower()
    local lower_ext = extension:lower()

    local result = ""
    if lower_base:sub(-#lower_suffix) == lower_suffix or lower_base:sub(-#lower_ext) == lower_ext then
        result = base_path
    elseif base_path:match("%.[a-zA-Z0-9]+$") then
        local dir = base_path:match("(.*)[\\/]")
        result = dir and M.join(dir, expected_suffix) or expected_suffix
    else
        result = M.join(base_path, expected_suffix)
    end

    return M.to_long_path(result)
end

function M.split_drive(path)
    if not path then
        return nil, path
    end
    local drive = path:match("^(%a:)")
    if drive then
        local remainder = path:sub(#drive + 1)
        return drive, remainder
    end
    return nil, path
end

function M.get_canonical_id(rel_path)
    if not rel_path then return nil end
    local normalized = M.normalize_separators(rel_path):gsub("\\", "/")

    local parts = {}
    for part in normalized:gmatch("[^/]+") do
        table.insert(parts, part)
    end

    local canonical = table.concat(parts, "/")

    -- Strip last extension (stem logic matching DirectoryNormalizer's multi_ext)
    local stem = canonical
    local last_dot = 0
    for i = 1, #canonical do
        if canonical:sub(i, i) == "." then last_dot = i end
    end
    if last_dot > 0 then
        stem = canonical:sub(1, last_dot - 1)
    end

    local hash = sdk.md5(stem)
    if not hash or hash == "" then return "000000" end
    return string.lower(hash:sub(1, 6))
end

-- Expose polyfill global for the sandbox
function _G.import(path)
    local fh, open_err = io.open(path, "r")
    if not fh then error(string.format("Failed to open module '%s': %s", path, tostring(open_err))) end
    local src = fh:read("*a")
    fh:close()
    
    local chunk, err = load(src, "@" .. path, "t", _ENV)
    if not chunk then error(string.format("Failed to compile module '%s': %s", path, err)) end
    return chunk()
end

return M
