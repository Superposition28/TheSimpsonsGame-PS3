
---@class BlenderUtils
---@field path_sep string
---@field Colours table
---@field log fun(colour: string, message: string, prefix?: string)
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
import(join("..", "..", "SharedUtils.lua"))


---@param path string
---@return string|nil
function parent_dir(path)
    local dir = dirname(path)
    if dir == "." or dir == path then return nil end
    return dir
end

-- Byte-wise helpers to avoid Lua pattern engine entirely
---@param b integer
---@return boolean
function is_space_byte(b)
    return b == 9 or b == 10 or b == 11 or b == 12 or b == 13 or b == 32
end

---@param s any
---@return string|nil
function trim_ascii(s)
    if s == nil then return s end
    local str = tostring(s)
    local i, j = 1, #str
    while i <= j do
        local b = string.byte(str, i)
        if not is_space_byte(b) then break end
        i = i + 1
    end
    while j >= i do
        local b = string.byte(str, j)
        if not is_space_byte(b) then break end
        j = j - 1
    end
    if i > j then return "" end
    return string.sub(str, i, j)
end

---@param s string|nil
---@return string|nil
function strip_surrounding_quotes(s)
    if not s or #s < 2 then return s end
    local first = string.sub(s, 1, 1)
    local last = string.sub(s, -1)
    if (first == '"' and last == '"') or (first == "'" and last == "'") then
        return string.sub(s, 2, -2)
    end
    return s
end

---@param s string|nil
---@return string|nil
function trim_trailing_punct_ws(s)
    if not s or #s == 0 then return s end
    local j = #s
    while j >= 1 do
        local ch = string.sub(s, j, j)
        local b = string.byte(ch)
        if ch == ',' or ch == ';' or is_space_byte(b) then
            j = j - 1
        else
            break
        end
    end
    if j < 1 then return "" end
    return string.sub(s, 1, j)
end

---@param v any
---@return string|nil
function clean_value(v)
    if v == nil then return v end
    local s =  trim_ascii(tostring(v))
    s =  strip_surrounding_quotes(s)
    s =  trim_trailing_punct_ws(s)
    return trim_ascii(s)
end

---@param token string
---@return string
---@return string|nil
function match_assignment(token)
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
