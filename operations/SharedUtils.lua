-- SharedUtils.lua
-- Globally shared utility functions for RemakeEngine scripts
-- Combined from module helpers and BlenderUtils specialized logic

local M = {}

M.path_sep = package.config:sub(1,1) or "/"

M.Colours = {
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
function M.colour_print(opts)
    opts = opts or {}
    local colour = opts.colour or M.Colours.DEFAULT
    local message = opts.message or ""
    local newline = true
    if opts.newline ~= nil then newline = opts.newline end
    sdk.colour_print({ colour = colour, message = message, newline = newline })
end

--- Log wrapper used by Blender scripts (maintains compatibility)
function M.log(colour, message, prefix)
    prefix = prefix or "SharedUtils"
    M.colour_print({ colour = colour or M.Colours.DEFAULT, message = string.format("[%s] %s", prefix, message or "") })
end

--- Path Manipulations -------------------------------------------------------

--- Normalize path separators to host OS default
function M.normalize(path)
    if not path then return path end
    if type(path) ~= "string" then path = tostring(path) end
    local sep = M.path_sep
    if sep == "\\" then
        path = path:gsub("/", "\\")
    else
        path = path:gsub("\\", "/")
    end
    -- Also collapse multiple separators (optional, but robust)
    path = path:gsub("[/\\]+", sep)
    return path
end

--- Join path parts safely
function M.join(...)
    local res = join(...)
    return M.normalize(res)
end

function M.basename(path)
    return (path and path:match("([^/\\]+)$")) or path
end

function M.dirname(p)
    if not p or p == "" then return "." end
    local d = p:match("(.+)[/\\][^/\\]+$") or p:match("(.+)[/\\]$") or ""
    if d == "" then
        -- Handle drive letters on Windows (e.g. C:\)
        if p:match("^%a:[/\\]?$") then return p end
        return "."
    end
    return d
end

function M.is_absolute(path)
    if not path then return false end
    if path:match("^%a:[/\\]") then return true end -- Windows drive
    if path:sub(1, 2) == "\\\\" then return true end -- Windows UNC
    if path:sub(1, 1) == "/" then return true end -- Unix root
    return false
end

--- Get absolute path (robust version with long path support on Windows)
function M.absolute_path(path)
    if not path then return path end
    local resolved = sdk.realpath(path)
    local result = path
    if resolved and #resolved > 0 then
        result = resolved
    elseif not M.is_absolute(path) then
        local cwd = sdk.currentdir()
        result = M.join(cwd, path)
    end

    result = M.normalize(result)

    -- Ensure \\?\ prefix on Windows for long path support in Blender 4.5+
    -- Only apply if the path is actually long (> 255 chars) to avoid "saved with @" errors for short paths.
    if M.path_sep == "\\" and result:match("^%a:") and not result:find("^\\\\%?\\") and #result > 255 then
        result = "\\\\?\\" .. result
    end

    return result
end

--- Prefix with \\?\ on Windows for long path support
function M.to_long_path(path)
    if not path or path == "" or M.path_sep ~= "\\" then return path end
    if path:find("^\\\\%?\\") then return path end

    local normalized = M.normalize(path)
    if normalized:match("^%a:") and #normalized > 255 then
        return "\\\\?\\" .. normalized
    end
    return normalized
end

--- Build a full path string for specific filename + extension, ensuring it's valid
function M.get_path(base_path, filename, extension)
    if not base_path or base_path == "" then return "" end
    base_path = M.normalize(base_path)
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
        local dir = M.dirname(base_path)
        result = M.join(dir, expected_suffix)
    else
        -- Otherwise it's a directory
        result = M.join(base_path, expected_suffix)
    end

    return M.to_long_path(result)
end

function M.split_drive(path)
    if not path then return nil, path end
    local drive = path:match("^(%a:)")
    if drive then
        local remainder = path:sub(#drive + 1)
        return drive, remainder
    end
    return nil, path
end

--- Calculate relative path from base to target
function M.get_relative_path(base, target)
    if not base or not target then return target end
    base = M.normalize(base)
    target = M.normalize(target)
    local sep = M.path_sep

    if base:sub(-1) ~= sep then base = base .. sep end
    if target:sub(1, #base):lower() == base:lower() then
        return target:sub(#base + 1)
    end
    return target
end

--- Get a 6-character hash ID for a path (used for assets)
function M.get_canonical_id(rel_path)
    if not rel_path then return nil end
    local normalized = M.normalize(rel_path):gsub("\\", "/")

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

function M.trim(s)
    if not s or type(s) ~= "string" then return s end
    return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

function M.ends_with(str, suffix)
    if not str or not suffix then return false end
    if #suffix == 0 then return true end
    if #str < #suffix then return false end
    return str:sub(-#suffix) == suffix
end

--- File & Directory Iteration -----------------------------------------------

--- Recursive list of file count
function M.count_files(path)
    local count = 0
    if not sdk.is_dir(path) then return count end
    local entries = sdk.list_dir(path)
    for _, file in ipairs(entries) do
        local full = M.join(path, file)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "file" then
            count = count + 1
        elseif attr and attr.mode == "directory" then
            count = count + M.count_files(full)
        end
    end
    return count
end

--- Get a flat list of immediate subdirectories
function M.list_subdirs(path)
    local dirs = {}
    if not sdk.is_dir(path) then return dirs end
    for _, f in ipairs(sdk.list_dir(path)) do
        local full = M.join(path, f)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "directory" then
            table.insert(dirs, f)
        end
    end
    return dirs
end

--- Standardized visitor-based file iteration
function M.iterate_files(root_dir, visitor)
    if not sdk.is_dir(root_dir) then
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

--- Recursive directory tree copy using SDK and progress tracking
function M.copy_tree(src, dst, total, state)
    if not sdk.is_dir(src) then return end
    sdk.ensure_dir(dst)

    local entries = sdk.list_dir(src)
    for _, file in ipairs(entries) do
        local src_path = M.join(src, file)
        local dst_path = M.join(dst, file)
        local attr = sdk.attributes(src_path)
        if attr and attr.mode == "directory" then
            M.copy_tree(src_path, dst_path, total, state)
        elseif attr and attr.mode == "file" then
            sdk.ensure_dir(M.dirname(dst_path))
            sdk.copy_file(src_path, dst_path, true)
            if state and total then
                state.count = state.count + 1
                local progress_val = (total > 0) and ((state.count / total) * 100) or 100
                sdk.colour_print({
                    colour = M.Colours.YELLOW,
                    message = string.format("Copying... %d/%d files (%.1f%%) ", state.count, total, progress_val),
                    newline = false
                })
            end
        end
    end
end

return M
