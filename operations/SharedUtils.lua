---@diagnostic disable: lowercase-global

---@class SharedUtilsColourPrintOptions
---@field colour string?
---@field message string?
---@field newline boolean?

---@class SharedUtilsColours
---@field [string] string
---@field DEFAULT string
---@field WHITE string
---@field RED string
---@field GREEN string
---@field YELLOW string
---@field BLUE string
---@field MAGENTA string
---@field CYAN string
---@field GRAY string
---@field GREY string
---@field DARK_GREEN string
---@field DARKGRAY string
---@field DARKGREY string
---@field DARKCYAN string
---@field DARKYELLOW string
---@field DARKRED string

---@class SharedUtilsCopyState
---@field count integer

---@class SharedUtils
---@field normalize fun(path: any): any
---@field Normalize fun(path: any): any
---@field colour_print fun(opts: any)
---@field log fun(colour: string, message: string, prefix?: string)
---@field path_sep string
---@field Colours SharedUtilsColours
---@field basename fun(path: any): any
---@field dirname fun(path: any): string
---@field is_absolute fun(path: string): boolean
---@field absolute_path fun(path: string): string|nil
---@field to_long_path fun(path: any): any
---@field get_path fun(base_path: string, filename: string, extension: string): string
---@field split_drive fun(path: string|nil): (string|nil, string|nil)
---@field get_relative_path fun(base: any, target: any): any
---@field get_canonical_id fun(rel_path: string|nil): string|nil
---@field trim fun(s: any): any
---@field ends_with fun(str: string|nil, suffix: string|nil): boolean
---@field count_files fun(path: string): integer
---@field list_subdirs fun(path: string): string[]
---@field iterate_files fun(root_dir: string, visitor: fun(full_path: string, filename: string): nil)
---@field copy_tree fun(src: string, dst: string, total: integer?, state: SharedUtilsCopyState?)


path_sep = package.config:sub(1,1) or "/"

---@type SharedUtilsColours
Colours = {
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

--- Print a coloured message via SDK
---@param opts any
function colour_print(opts)
    opts = opts or {}
    local colour = opts.colour or Colours.DEFAULT
    local message = opts.message or ""
    local newline = true
    if opts.newline ~= nil then newline = opts.newline end
    sdk.colour_print({ colour = colour, message = message, newline = newline })
end


---@param colour string
---@param message string
---@param prefix string?
function log(colour, message, prefix)
    --prefix should be filename to identify source of log, e.g. "BlenderRun" for blender/run.lua
    local prefix_str = tostring(prefix or "LOG")
    colour_print({ colour = colour or Colours.DEFAULT, message = string.format("[%s] %s", prefix_str, message or "") })
end

--- Path Manipulations -------------------------------------------------------

--- Normalize path separators to host OS default
---@param path any
---@return any
function Normalize(path)
    return normalize(path)
end
---@param path any
---@return any
function normalize(path)
    if not path then return path end
    if type(path) ~= "string" then path = tostring(path) end
    local sep = path_sep
    if sep == "\\" then
        path = path:gsub("/", "\\")
    else
        path = path:gsub("\\", "/")
    end
    -- Also collapse multiple separators (optional, but robust)
    path = path:gsub("[/\\]+", sep)
    return path
end

---@param path string|nil
---@return any
function basename(path)
    return (path and path:match("([^/\\]+)$")) or path
end

---@param p string|nil
---@return string
function dirname(p)
    if not p or p == "" then return "." end
    local d = p:match("(.+)[/\\][^/\\]+$") or p:match("(.+)[/\\]$") or ""
    if d == "" then
        -- Handle drive letters on Windows (e.g. C:\)
        if p:match("^%a:[/\\]?$") then return p end
        return "."
    end
    return d
end

---@param path string
---@return boolean
function is_absolute(path)
    return sdk.is_absolute(path)
end

--- Get absolute path (robust version with long path support on Windows)
---@param path string
---@return string|nil
function absolute_path(path)
    return sdk.absolute_path(path)
end

--- Prefix with \\?\ on Windows for long path support
---@param path string|nil
---@return any
function to_long_path(path)
    if not path or path == "" or path_sep ~= "\\" then return path end
    if path:find("^\\\\%?\\") then return path end

    local normalized = normalize(path)
    if normalized:match("^%a:") and #normalized > 255 then
        return "\\\\?\\" .. normalized
    end
    return normalized
end

--- Build a full path string for specific filename + extension, ensuring it's valid
---@param base_path string
---@param filename string
---@param extension string
---@return string
function get_path(base_path, filename, extension)
    if not base_path or base_path == "" then return "" end
    base_path = normalize(base_path)
    local expected_suffix = filename .. extension

    local lower_base = base_path:lower()
    local lower_suffix = expected_suffix:lower()
    local lower_ext = extension:lower()

    local result = ""
    -- If base_path already includes filename+ext, use it directly
    if lower_base:sub(-#lower_suffix) == lower_suffix or lower_base:sub(-#lower_ext) == lower_ext then
        result = base_path
    elseif base_path:match("%.[a-zA-Z0-9]+$") then
        -- If it's a file but doesn't match, swap it
        local dir = dirname(base_path)
        result = join(dir, expected_suffix)
    else
        -- Otherwise it's a directory
        result = join(base_path, expected_suffix)
    end

    return to_long_path(result)
end

---@param path string|nil
---@return string|nil drive
---@return string|nil remainder
function split_drive(path)
    if not path then return nil, path end
    local drive = path:match("^(%a:)")
    if drive then
        local remainder = path:sub(#drive + 1)
        return drive, remainder
    end
    return nil, path
end

--- Calculate relative path from base to target
---@param base any
---@param target any
---@return any
function get_relative_path(base, target)
    if not base or not target then return target end
    base = normalize(base)
    target = normalize(target)
    local sep = path_sep

    if base:sub(-1) ~= sep then base = base .. sep end
    if target:sub(1, #base):lower() == base:lower() then
        return target:sub(#base + 1)
    end
    return target
end

--- Get a 6-character hash ID for a path (used for assets)
---@param rel_path string|nil
---@return string|nil
function get_canonical_id(rel_path)
    if not rel_path then return nil end
    local normalized = normalize(rel_path):gsub("\\", "/")

    -- Strip last extension (stem logic)
    local stem = normalized
    local last_dot = 0
    for i = 1, #normalized do
        if normalized:sub(i, i) == "." then last_dot = i end
    end
    if last_dot > 0 then
        stem = normalized:sub(1, last_dot - 1)
    end

    local hash = sdk.md5(stem)
    if not hash or hash == "" then return "000000" end
    return string.lower(hash:sub(1, 6))
end

--- String Manipulations -----------------------------------------------------

---@param s any
---@return any
function trim(s)
    if not s or type(s) ~= "string" then return s end
    return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

---@param str string|nil
---@param suffix string|nil
---@return boolean
function ends_with(str, suffix)
    if not str or not suffix then return false end
    if #suffix == 0 then return true end
    if #str < #suffix then return false end
    return str:sub(-#suffix) == suffix
end

--- File & Directory Iteration -----------------------------------------------

--- Recursive list of file count
---@param path string
---@return integer
function count_files(path)
    local count = 0
    if not sdk.is_dir(path) then return count end
    local entries = sdk.list_dir(path)
    for _, file in ipairs(entries) do
        local full = join(path, file)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "file" then
            count = count + 1
        elseif attr and attr.mode == "directory" then
            count = count + count_files(full)
        end
    end
    return count
end

--- Get a flat list of immediate subdirectories
---@param path string
---@return string[]
function list_subdirs(path)
    local dirs = {}
    if not sdk.is_dir(path) then return dirs end
    for _, f in ipairs(sdk.list_dir(path)) do
        local full = join(path, f)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "directory" then
            table.insert(dirs, f)
        end
    end
    return dirs
end

--- Standardized visitor-based file iteration
---@param root_dir string
---@param visitor fun(full_path: string, filename: string): nil
function iterate_files(root_dir, visitor)
    if not sdk.is_dir(root_dir) then
        return
    end

    local entries = sdk.list_dir(root_dir)
    for _, entry in ipairs(entries) do
        local full_path = join(root_dir, entry)
        if sdk.is_dir(full_path) then
            iterate_files(full_path, visitor)
        elseif sdk.is_file(full_path) then
            visitor(full_path, entry)
        end
    end
end

--- Recursive directory tree copy using SDK and progress tracking
---@param src string
---@param dst string
---@param total integer?
---@param state SharedUtilsCopyState?
function copy_tree(src, dst, total, state)
    if not sdk.is_dir(src) then return end
    sdk.ensure_dir(dst)

    local entries = sdk.list_dir(src)
    for _, file in ipairs(entries) do
        local src_path = join(src, file)
        local dst_path = join(dst, file)
        local attr = sdk.attributes(src_path)
        if attr and attr.mode == "directory" then
            copy_tree(src_path, dst_path, total, state)
        elseif attr and attr.mode == "file" then
            sdk.ensure_dir(dirname(dst_path))
            sdk.copy_file(src_path, dst_path, true)
            if state and total then
                state.count = state.count + 1
                local progress_val = (total > 0) and ((state.count / total) * 100) or 100
                sdk.colour_print({
                    colour = Colours.YELLOW,
                    message = string.format("Copying... %d/%d files (%.1f%%) ", state.count, total, progress_val),
                    newline = false
                })
            end
        end
    end
end

