
---@class BlenderUtils
---@field path_sep string
---@field Colours table
---@field log fun(colour: string, message: string, prefix?: string)
---@field normalize_separators fun(path: string): string|nil
---@field ends_with fun(str: string, suffix: string): boolean
---@field parent_dir fun(path: string): string|nil
---@field is_absolute fun(path: string): boolean
---@field absolute_path fun(path: string): string
---@field join fun(...: string): string
---@field iterate_files fun(root_dir: string, visitor: fun(full_path: string, filename: string))
---@field to_long_path fun(path: string): string
---@field get_path fun(base_path: string, filename: string, extension: string): string
---@field split_drive fun(path: string): (string?, string)
---@field get_canonical_id fun(rel_path: string): string
---@field is_space_byte fun(b: integer): boolean
---@field trim_ascii fun(s: any): string|nil
---@field strip_surrounding_quotes fun(s: string|nil): string|nil
---@field trim_trailing_punct_ws fun(s: string|nil): string|nil
---@field clean_value fun(v: any): string|nil
---@field match_assignment fun(token: string): string, string|nil

---@type SharedUtils
Utils = import(join(Game_Root, "operations", "SharedUtils"))

local path_sep = Utils.path_sep
local Colours = Utils.Colours

local M = {
    path_sep = path_sep,
    Colours = Colours,
    log = Utils.log
}

function M.normalize_separators(path)
    return Utils.normalize(path)
end

function M.ends_with(str, suffix)
    return Utils.ends_with(str, suffix)
end

function M.parent_dir(path)
    local dir = Utils.dirname(path)
    if dir == "." or dir == path then return nil end
    return dir
end

function M.is_absolute(path)
    return Utils.is_absolute(path)
end

function M.absolute_path(path)
    return Utils.absolute_path(path)
end

function M.join(...)
    return Utils.join(...)
end

function M.iterate_files(root_dir, visitor)
    return Utils.iterate_files(root_dir, visitor)
end

function M.to_long_path(path)
    return Utils.to_long_path(path)
end

function M.get_path(base_path, filename, extension)
    return Utils.get_path(base_path, filename, extension)
end

function M.split_drive(path)
    return Utils.split_drive(path)
end

function M.get_canonical_id(rel_path)
    return Utils.get_canonical_id(rel_path)
end

-- Byte-wise helpers to avoid Lua pattern engine entirely
function M.is_space_byte(b)
    return b == 9 or b == 10 or b == 11 or b == 12 or b == 13 or b == 32
end
function M.trim_ascii(s)
    if s == nil then return s end
    local str = tostring(s)
    local i, j = 1, #str
    while i <= j do
        local b = string.byte(str, i)
        if not M.is_space_byte(b) then break end
        i = i + 1
    end
    while j >= i do
        local b = string.byte(str, j)
        if not M.is_space_byte(b) then break end
        j = j - 1
    end
    if i > j then return "" end
    return string.sub(str, i, j)
end
function M.strip_surrounding_quotes(s)
    if not s or #s < 2 then return s end
    local first = string.sub(s, 1, 1)
    local last = string.sub(s, -1)
    if (first == '"' and last == '"') or (first == "'" and last == "'") then
        return string.sub(s, 2, -2)
    end
    return s
end
function M.trim_trailing_punct_ws(s)
    if not s or #s == 0 then return s end
    local j = #s
    while j >= 1 do
        local ch = string.sub(s, j, j)
        local b = string.byte(ch)
        if ch == ',' or ch == ';' or M.is_space_byte(b) then
            j = j - 1
        else
            break
        end
    end
    if j < 1 then return "" end
    return string.sub(s, 1, j)
end
function M.clean_value(v)
    if v == nil then return v end
    local s =  M.trim_ascii(tostring(v))
    s =  M.strip_surrounding_quotes(s)
    s =  M.trim_trailing_punct_ws(s)
    return M.trim_ascii(s)
end
function M.match_assignment(token)
    local eq = string.find(token, "=", 1, true)
    local colon = string.find(token, ":", 1, true)
    local idx
    if eq and colon then
        if eq < colon then
            idx = eq
        else
            idx = colon
        end
    else
        idx = eq or colon
    end
    if idx then
        local opt = string.sub(token, 1, idx - 1)
        local value = string.sub(token, idx + 1)
        return opt, value
    end
    return token, nil
end


---@cast M BlenderUtils
return M
