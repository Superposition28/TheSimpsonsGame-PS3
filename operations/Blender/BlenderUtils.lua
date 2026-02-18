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

local M = {}
M.path_sep = path_sep
M.Colours = Colours

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
    if path_sep == "\\" and result:match("^%a:") and not result:find("^\\\\%?\\") then
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

function M.md5_hash(value)
    if sdk and sdk.md5 then
        return sdk.md5(value)
    end
    error("sdk.md5 helper is unavailable")
end

function M.get_canonical_id(rel_path, rename_map)
    if not rel_path then return nil end
    local normalized = M.normalize_separators(rel_path):gsub("\\", "/")

    local parts = {}
    for part in normalized:gmatch("[^/]+") do
        table.insert(parts, part)
    end

    if #parts > 0 and rename_map then
        local first = parts[1]:lower()
        if rename_map[first] then
            parts[1] = rename_map[first]
        end
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

    local hash = M.md5_hash(stem)
    if not hash or hash == "" then return "000000" end
    return string.lower(hash:sub(1, 6))
end

return M
