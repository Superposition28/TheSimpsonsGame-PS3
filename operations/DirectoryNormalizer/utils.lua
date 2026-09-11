
---@class DirectoryNormalizerUtils


Path_sep = package.config:sub(1,1) or "/"

--- Normalize slashes in a path according to the current platform
---@param p string|nil
---@return string|nil
function norm_slashes(p)
    if not p then return p end
    if Path_sep == "\\" then
        p = p:gsub("/", "\\")
    else
        p = p:gsub("\\", "/")
    end
    p = p:gsub("[/\\]+", Path_sep)
    return p
end

--- Convert a path to POSIX style (forward slashes)
---@param p string|nil
---@return string|nil
---@return integer? count
function ToPosix(p)
    if not p then return p end
    return p:gsub("\\", "/")
end


--- Split a path into its components
---@param p string
---@return string[]
function split_path(p)
    local parts = {}
    for part in p:gmatch("[^/\\]+") do table.insert(parts, part) end
    return parts
end

---@param path string
---@param data string
---@return boolean
function write_all_text(path, data)
    local parent = path:match("^(.*)[/\\][^/\\]+$")
    if parent and parent ~= "" then sdk.ensure_dir(parent) end
    local f = io.open(path, "wb")
    if not f then return false end
    ---@cast f FileHandle
    f:write(data)
    f:close()
    return true
end

--- Get the directory name of a path
---@param p string
---@return string
function dirname(p)
    local s = norm_slashes(p)
    local last = 0
    for i=1,#s do
        local ch = s:sub(i,i)
        if ch == '/' or ch == '\\' then last = i end
    end
    if last == 0 then return "" end
    return s:sub(1, last-1)
end

--- Get the base name of a path
---@param p string
---@return string
function basename(p)
    local s = norm_slashes(p)
    local last = 0
    for i=1,#s do
        local ch = s:sub(i,i)
        if ch == '/' or ch == '\\' then last = i end
    end
    if last == 0 then return s end
    return s:sub(last+1)
end

--- Encode an object as JSON
---@param obj any
---@param indent boolean
---@return string
function json_encode(obj, indent)
    return sdk.text.json.encode(obj, { indent = indent ~= false })
end

--- Get a hexadecimal UID for a string
---@param s string
---@param length integer
---@return string
function get_hex_uid(s, length)
    length = length or 6
    local hex = sdk.md5(s) or ""
    if hex == "" then return string.rep("0", length) end -- Fallback
    return string.lower(hex:sub(1, length))
end

--- Get the name and extension of a file, supporting multiple dots
---@param name string
---@return string, string
function multi_ext(name)
    local idx = nil
    for i = 1, #name do
        if name:sub(i, i) == '.' then
            idx = i
        end
    end
    if not idx then return name, "" end
    return name:sub(1, idx-1), name:sub(idx)
end

--- Check if a directory should be ignored based on an ignore list
---@param name string
---@param ignore_list string[]
---@return boolean
function should_ignore_dir(name, ignore_list)
    local lname = string.lower(name)
    for _,ig in ipairs(ignore_list) do
        local v = string.lower(ig or "")
        if v ~= "" and lname == v then return true end
    end
    return false
end

--- Get the lowercase extension of a file
---@param name string
---@return string
function ext_lower(name)
    local last = nil
    for i=1,#name do
        if name:sub(i,i) == '.' then last = i end
    end
    if not last then return "" end
    return string.lower(name:sub(last))
end

--- Get the relative path from a root directory
---@param full string
---@param root string
---@return string
function rel_path(full, root)
    local f = norm_slashes(full)
    local r = norm_slashes(root)
    if f:sub(1, #r) == r then
        local rest = f:sub(#r+1)
        if rest:sub(1,1) == Path_sep then rest = rest:sub(2) end
        return rest
    end
    return full
end

--- Copy a file to a destination, handling name collisions by appending a suffix
---@param src string
---@param dst string
---@return boolean
function copy_with_collision_handling(src, dst)
    local parent = dirname(dst)
    if parent and parent ~= "" then sdk.ensure_dir(parent) end
    local target = dst
    if sdk.path_exists(target) then
        local ext = ext_lower(dst)
        local base
        if ext ~= "" then
            base = dst:sub(1, #dst - #ext)
        else
            base = dst
        end
        local i = 1
        repeat
            local suffix = (i==1) and "" or tostring(i)
            target = string.format("%s_dup%s%s", base, suffix, ext)
            i = i + 1
        until not sdk.path_exists(target)
    end
    return sdk.copy_file(src, target, false)
end
