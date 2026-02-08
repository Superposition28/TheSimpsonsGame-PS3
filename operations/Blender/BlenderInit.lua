if not sqlite then
    error("sqlite module is not available; ensure LuaScriptAction exposes sqlite helpers")
end

local path_sep = package.config:sub(1, 1)
local PREFIX = "BlendInit"
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

local VERBOSE = false

local function log(colour, message)
    sdk.colour_print({ colour = colour or Colours.DEFAULT, message = string.format("[%s] %s", PREFIX, message or "") })
end

local function normalize_separators(path)
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

local function ends_with(str, suffix)
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

local function parent_dir(path)
    if not path then
        return nil
    end
    local normalized = normalize_separators(path)
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

local function is_absolute(path)
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
local function absolute_path(path)
    if not path then
        return path
    end
    -- Use sdk.realpath directly (always available in engine runtime)
    local resolved = sdk.realpath(path)
    if resolved and #resolved > 0 then
        return normalize_separators(resolved)
    end
    if is_absolute(path) then
        return normalize_separators(path)
    end
    local cwd = sdk.currentdir()
    return normalize_separators(cwd .. path_sep .. path)
end

local PreinstancedFileProcessor = {}
PreinstancedFileProcessor.__index = PreinstancedFileProcessor

function PreinstancedFileProcessor.new(opts)
    local self = setmetatable({}, PreinstancedFileProcessor)
    self.input_dir = absolute_path(opts.input_dir)
    self.blend_dir = absolute_path(opts.blend_dir)
    self.glb_dir = absolute_path(opts.glb_dir)
    self.blank_blend_source = absolute_path(opts.blank_blend_source)
    self.debug_mode_enabled = not not opts.debug_mode_enabled
    self.verbose = not not opts.verbose
    return self
end


local function join(...)
    local parts = { ... }
    local buffer = {}
    for index = 1, #parts do
        local part = parts[index]
        if part and part ~= "" then
            if type(part) ~= 'string' then
                part = tostring(part)
            end
            part = normalize_separators(part)
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

local function iterate_files(root_dir, visitor)
    if not sdk.is_dir(root_dir) then
        log(Colours.RED, string.format("Directory '%s' does not exist for iteration.", root_dir))
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

function PreinstancedFileProcessor:process_files()
    if not sdk.is_dir(self.input_dir) then
        log(Colours.RED, string.format("InputDirectory '%s' is not set or does not exist.", self.input_dir))
        error(string.format("InputDirectory '%s' is not set or does not exist.", self.input_dir))
    end
    if not self.blend_dir then
        log(Colours.RED, "BlendDirectory is not set.")
        error("BlendDirectory is not set.")
    end
    sdk.ensure_dir(self.blend_dir)
    if not self.glb_dir then
        log(Colours.RED, "GLBOutputDirectory is not set.")
        error("GLBOutputDirectory is not set.")
    end
    sdk.ensure_dir(self.glb_dir)
    if not sdk.is_file(self.blank_blend_source) then
        log(Colours.RED, string.format("BlankBlendSource '%s' is not set or does not exist.", self.blank_blend_source))
        error(string.format("BlankBlendSource '%s' is not set or does not exist.", self.blank_blend_source))
    end

    local files = {}
    iterate_files(self.input_dir, function(full_path, filename)
        if ends_with(filename:lower(), ".preinstanced") then
            table.insert(files, full_path)
        end
    end)

    log(Colours.CYAN, string.format("Found %d .preinstanced files in %s.", #files, self.input_dir))
    local input_dir_abs = self.input_dir

    for _, preinst_path in ipairs(files) do
        if self.verbose then
            log(Colours.CYAN, string.format("Processing preinstanced file: %s", preinst_path))
        end

        local rel = normalize_separators(preinst_path):sub(#input_dir_abs + 2)
        -- Replace heavy Lua pattern with simple last-separator search
        local rel_ns = normalize_separators(rel)
        local last_sep = 0
        for i = 1, #rel_ns do
            local ch = rel_ns:sub(i,i)
            if ch == '/' or ch == '\\' then last_sep = i end
        end
        local rel_dir = last_sep > 0 and rel_ns:sub(1, last_sep - 1) or nil
        local blend_dest_dir = rel_dir and join(self.blend_dir, rel_dir) or self.blend_dir
        local glb_dest_dir = rel_dir and join(self.glb_dir, rel_dir) or self.glb_dir

        sdk.ensure_dir(blend_dest_dir)
        sdk.ensure_dir(glb_dest_dir)

        -- Derive base name without using complex patterns
        local fn_ns = normalize_separators(preinst_path)
        local last2 = 0
        for i = 1, #fn_ns do
            local ch = fn_ns:sub(i,i)
            if ch == '/' or ch == '\\' then last2 = i end
        end
        local fname = last2 > 0 and fn_ns:sub(last2 + 1) or fn_ns
        local suffix = '.preinstanced'
        local base_name = fname
        if #fname > #suffix and fname:sub(#fname - #suffix + 1):lower() == suffix then
            base_name = fname:sub(1, #fname - #suffix)
        end
        local blend_dest_filename = base_name .. ".blend"
        local blend_dest_full_path = join(blend_dest_dir, blend_dest_filename)

        if not sdk.is_file(blend_dest_full_path) then
            local copied = sdk.copy_file and sdk.copy_file(self.blank_blend_source, blend_dest_full_path, false)
            if copied then
                if self.verbose then
                    log(Colours.CYAN, string.format("Copied %s to %s", self.blank_blend_source, blend_dest_full_path))
                end
            else
                log(Colours.RED, string.format("Error copying blank blend file to '%s'", blend_dest_full_path))
                if self.debug_mode_enabled then
                    sdk.sleep(1)
                end
            end
        end

        if self.debug_mode_enabled then
            sdk.sleep(0.05)
        end
    end

    log(Colours.GREEN, string.format("Total .preinstanced files processed for blend/glb structure setup: %d", #files))
end

local function extract_map_subdirectory(full_path, marker)
    local normalized_path = normalize_separators(full_path or "")
    local normalized_marker = normalize_separators(marker or "")

    if normalized_marker == "" then
        log(Colours.YELLOW, string.format("Warning: Marker is not provided. Cannot extract map subdirectory from path: %s. Returning _UNKNOWN_MAP_NO_MARKER.", normalized_path))
        return "_UNKNOWN_MAP_NO_MARKER"
    end

    local lower_path = normalized_path:lower()
    local lower_marker = normalized_marker:lower()
    local idx = lower_path:find(lower_marker, 1, true)

    if not idx then
        log(Colours.YELLOW, string.format("Warning: Marker '%s' was not found in path: %s. Returning _UNKNOWN_MAP_NOT_FOUND.", normalized_marker, normalized_path))
        return "_UNKNOWN_MAP_NOT_FOUND"
    end

    local start_of_remainder = idx + #normalized_marker
    local remaining = normalized_path:sub(start_of_remainder)
    remaining = remaining:gsub("^[" .. path_sep .. "]+", "")

    if remaining == "" then
        log(Colours.CYAN, string.format("Info: Marker '%s' found in '%s', but path ends with marker or only separators follow. Returning _NO_SUBDIR_AFTER_MARKER.", normalized_marker, normalized_path))
        return "_NO_SUBDIR_AFTER_MARKER"
    end

    local parts = {}
    for component in remaining:gmatch("[^" .. path_sep .. "]+") do
        table.insert(parts, component)
    end

    if #parts == 0 then
        log(Colours.YELLOW, string.format("Warning: Marker '%s' found in '%s', but could not isolate a subdirectory. Returning _NO_SUBDIR_PARTS_FOUND.", normalized_marker, normalized_path))
        return "_NO_SUBDIR_PARTS_FOUND"
    end

    local subdir = parts[1]
    if VERBOSE then
        log(Colours.GREEN, string.format("Success: Marker '%s', Path '%s', Subdir Part '%s'", normalized_marker, normalized_path, subdir))
    end
    return subdir
end

local function md5_hash(value)
    if sdk and sdk.md5 then
        return sdk.md5(value)
    end
    error("sdk.md5 helper is unavailable")
end

local function init_db(db_file_path)
    local db = sqlite.open(db_file_path)
    db.exec([[CREATE TABLE IF NOT EXISTS asset_map (
        identifier TEXT PRIMARY KEY,
        map_subdirectory TEXT,
        filename TEXT,
        preinstanced_full TEXT,
        blend_full TEXT,
        glb_full TEXT,
        preinstanced_symlink TEXT,
        blend_symlink TEXT,
        glb_symlink TEXT
    )]])
    return db
end



local function generate_asset_mapping(db, root_drive, preinstanced_root, blend_root, marker, glb_root, check_existence)
    check_existence = not not check_existence

    if not sdk.is_dir(preinstanced_root) then
        error(string.format("Preinstanced root directory not found: %s", preinstanced_root))
    end
    if not sdk.is_dir(blend_root) then
        error(string.format("Blend root directory not found: %s", blend_root))
    end
    if glb_root and not sdk.is_dir(glb_root) then
        log(Colours.CYAN, string.format("GLB root directory %s not found, creating it.", glb_root))
        sdk.ensure_dir(glb_root)
    end

    local assets_processed = 0
    local preinstanced_root_abs = absolute_path(preinstanced_root)
    local blend_root_abs = absolute_path(blend_root)
    local glb_root_abs = glb_root and absolute_path(glb_root) or nil

    db.begin()
    iterate_files(preinstanced_root_abs, function(full_path, filename)
        local lower_name = filename:lower()
        if not ends_with(lower_name, ".preinstanced") then
            return
        end

        local rel = normalize_separators(full_path):sub(#preinstanced_root_abs + 2)
        local blend_rel = rel:gsub("%.preinstanced$", ".blend")
        local blend_full = join(blend_root_abs, blend_rel)

        local glb_full = nil
        if glb_root_abs then
            local glb_rel = rel:gsub("%.preinstanced$", ".glb")
            glb_full = join(glb_root_abs, glb_rel)
        end

        if check_existence and (not sdk.is_file(blend_full)) then
            log(Colours.YELLOW, string.format("Warning: Corresponding blend file not found: %s", blend_full))
            return
        end

        local map_subdir = extract_map_subdirectory(full_path, marker)
        if VERBOSE then
            log(Colours.CYAN, string.format("Extracted Map Subdirectory: '%s' for %s", map_subdir, full_path))
        end

        local identifier = md5_hash(rel:gsub("\\", "/"))
        local base_filename = filename:gsub("%.preinstanced$", "")
        local params = {
            identifier = identifier,
            map_subdirectory = map_subdir,
            filename = base_filename,
            preinstanced_full = full_path,
            blend_full = blend_full,
            glb_full = glb_full
        }

        db.exec([[INSERT OR REPLACE INTO asset_map (
                identifier, map_subdirectory, filename, preinstanced_full, blend_full, glb_full)
                VALUES (:identifier, :map_subdirectory, :filename, :preinstanced_full, :blend_full, :glb_full)
            ]], params)
        assets_processed = assets_processed + 1
    end)
    db.commit()

    return assets_processed
end

local function create_symlink_entry(src, dst, is_dir, debug_sleep_duration)
    if not sdk.create_symlink then
        error("sdk.create_symlink helper is unavailable; symbolic links require the C# engine helper.")
    end

    if is_dir then
        if not sdk.is_dir(src) then
            error(string.format("Source directory for symlink does not exist: %s", tostring(src)))
        end
    else
        if not sdk.is_file(src) then
            error(string.format("Source file for symlink does not exist: %s", tostring(src)))
        end
    end

    if sdk.lexists and sdk.lexists(dst) then
        if sdk.is_symlink and sdk.is_symlink(dst) then
            if VERBOSE then
                log(Colours.YELLOW, string.format("Symlink already exists and will be validated: %s", dst))
            end
        else
            local removed
            if sdk.is_dir and sdk.is_dir(dst) then
                removed = sdk.remove_dir and sdk.remove_dir(dst)
            else
                removed = sdk.remove_file and sdk.remove_file(dst)
            end
            if not removed then
                local msg = string.format("Unable to remove existing path prior to creating symlink: %s", dst)
                log(Colours.RED, msg)
                error(string.format("error during removal: %s", msg))
            end
        end
    end

    local success = sdk.create_symlink(src, dst, is_dir)
    if success then
        if VERBOSE then
            log(Colours.GREEN, string.format("Created symlink: %s -> %s", dst, src))
        end
        return true
    end

    local msg = string.format("Failed to create symlink %s -> %s. Ensure Developer Mode or elevated privileges are enabled.", dst, src)
    log(Colours.RED, msg)
    if debug_sleep_duration and debug_sleep_duration > 0 then
        sdk.sleep(debug_sleep_duration)
    end
    error(string.format("error : %s", msg))
end

local function verify_symlink(link_folder_path, src_folder_path, asset_id, link_type_name)
    if not (sdk.lexists and sdk.lexists(link_folder_path)) then
        local msg = string.format("%s symlink %s for asset %s was not created.", link_type_name, tostring(link_folder_path), tostring(asset_id))
        log(Colours.RED, msg)
        error(msg)
    end

    if sdk.is_dir and not sdk.is_dir(link_folder_path) then
        local msg = string.format("%s symlink %s for asset %s does not point to a directory.", link_type_name, tostring(link_folder_path), tostring(asset_id))
        log(Colours.RED, msg)
        error(msg)
    end

    -- Normalize for case-insensitive comparisons on Windows and trim trailing separators
    local function normalize_for_compare(p)
        if not p then return p end
        local n = normalize_separators(p)
        -- drop trailing separators
        n = n:gsub("" .. path_sep .. "+$", "")
        -- Windows is case-insensitive
        if path_sep == "\\" then
            n = n:lower()
        end
        return n
    end

    -- Resolve the link target preferring readlink() over realpath(), since on Windows
    -- realpath() can return the link path itself for directory symlinks/junctions.
    local raw_target = sdk.readlink and sdk.readlink(link_folder_path) or nil

    local function resolve_target(target, link_path)
        if not target or target == "" then return nil end
        local t = target
        if not is_absolute(t) then
            -- Resolve relative link targets relative to the link's parent directory
            t = join(parent_dir(link_path) or "", t)
        end
        t = absolute_path(t)
        local rp = sdk.realpath and sdk.realpath(t)
        if rp and #rp > 0 then
            t = rp
        end
        return normalize_for_compare(t)
    end

    local got = resolve_target(raw_target, link_folder_path)
        or normalize_for_compare((sdk.realpath and sdk.realpath(link_folder_path)) or link_folder_path)
    local want = normalize_for_compare((sdk.realpath and sdk.realpath(src_folder_path)) or src_folder_path)

    if got ~= want then
        local msg = string.format(
            "%s symlink %s for asset %s points to '%s' (raw: '%s') instead of '%s'.",
            link_type_name,
            tostring(link_folder_path),
            tostring(asset_id),
            tostring(got),
            tostring(raw_target or "unknown"),
            tostring(want)
        )
        log(Colours.RED, msg)
        error(msg)
    end

    if VERBOSE and DEBUG then
        log(Colours.GREEN, string.format("Verified %s symlink for %s: %s -> %s", link_type_name, tostring(asset_id), tostring(link_folder_path), tostring(want)))
    end
    return true
end

local function create_symbolic_links(db, root_drive, debug_mode_enabled)
    VERBOSE = true
    local rows = db.query("SELECT identifier, map_subdirectory, preinstanced_full, blend_full, glb_full FROM asset_map")
    local updated = 0
    local debug_sleep = debug_mode_enabled and 5 or 0

    for _, asset in ipairs(rows) do
        local identifier = asset.identifier
        local map_subdir = asset.map_subdirectory
        local preinstanced_full = asset.preinstanced_full
        local blend_full = asset.blend_full
        local glb_path_from_db = asset.glb_full

        if VERBOSE then
            log(Colours.CYAN, string.format("Processing asset: %s, map_subdir: %s", tostring(identifier), tostring(map_subdir)))
        end

        local invalid_map_subdir = (not map_subdir) or map_subdir:match("^_UNKNOWN_MAP") or map_subdir == "_NO_SUBDIR_AFTER_MARKER"
        if invalid_map_subdir then
            log(Colours.YELLOW, string.format("Map subdirectory '%s' for asset %s is not suitable for symlink creation. Skipping.", tostring(map_subdir), tostring(identifier)))
        else
            local target_base = join(root_drive, map_subdir)
            sdk.ensure_dir(target_base)

            local symlink_updates = {}

            if preinstanced_full and sdk.is_file and sdk.is_file(preinstanced_full) then
                local src_folder = parent_dir(preinstanced_full)
                if not src_folder then
                    error(string.format("Unable to resolve source directory for preinstanced asset %s (%s)", tostring(identifier), tostring(preinstanced_full)))
                end
                local link_folder = join(target_base, string.format("%s_preinstanced", identifier))
                if VERBOSE then
                    log(Colours.CYAN, string.format("Creating preinstanced symlink: %s -> %s", link_folder, src_folder))
                end
                create_symlink_entry(src_folder, link_folder, true, debug_sleep)
                verify_symlink(link_folder, src_folder, identifier, "preinstanced")
                symlink_updates.preinstanced_symlink = link_folder
            else
                error(string.format("Missing preinstanced source for asset %s (%s)", tostring(identifier), tostring(preinstanced_full)))
            end

            if blend_full and sdk.is_file and sdk.is_file(blend_full) then
                local src_folder = parent_dir(blend_full)
                if not src_folder then
                    error(string.format("Unable to resolve source directory for blend asset %s (%s)", tostring(identifier), tostring(blend_full)))
                end
                local link_folder = join(target_base, string.format("%s_blend", identifier))
                if VERBOSE then
                    log(Colours.CYAN, string.format("Creating blend symlink: %s -> %s", link_folder, src_folder))
                end
                create_symlink_entry(src_folder, link_folder, true, debug_sleep)
                verify_symlink(link_folder, src_folder, identifier, "blend")
                symlink_updates.blend_symlink = link_folder
            else
                error(string.format("Missing blend source for asset %s (%s)", tostring(identifier), tostring(blend_full)))
            end

            if glb_path_from_db then
                local src_folder = parent_dir(glb_path_from_db)
                if src_folder and sdk.is_dir and sdk.is_dir(src_folder) then
                    local link_folder = join(target_base, string.format("%s_glb", identifier))
                    if VERBOSE then
                        log(Colours.CYAN, string.format("Creating GLB symlink: %s -> %s", link_folder, src_folder))
                    end
                    create_symlink_entry(src_folder, link_folder, true, debug_sleep)
                    verify_symlink(link_folder, src_folder, identifier, "GLB")
                    symlink_updates.glb_symlink = link_folder
                elseif VERBOSE then
                    log(Colours.YELLOW, string.format("GLB source folder %s for asset %s does not exist; GLB symlink not created.", tostring(src_folder), tostring(identifier)))
                end
            end

            if next(symlink_updates) then
                symlink_updates.identifier = identifier
                local set_clauses = {}
                for key, _ in pairs(symlink_updates) do
                    if key ~= "identifier" then
                        table.insert(set_clauses, string.format("%s = :%s", key, key))
                    end
                end
                local update_sql = string.format("UPDATE asset_map SET %s WHERE identifier = :identifier", table.concat(set_clauses, ", "))
                db.exec(update_sql, symlink_updates)
                updated = updated + 1
                if VERBOSE then
                    log(Colours.GREEN, string.format("Updated symlink paths in DB for %s", tostring(identifier)))
                end
            else
                error(string.format("No symlinks were created for asset %s; expected at least one.", tostring(identifier)))
            end

        end
    end

    log(Colours.GREEN, string.format("Total assets updated with symlink information in DB: %d", updated))
end

local function run(args)
    VERBOSE = not not args.verbose

    log(Colours.CYAN, string.format("Input args: %s", sdk.text.json.encode(args)))

    local marker = args.marker
    log(Colours.CYAN, string.format("Marker: %s", tostring(marker)))

    local preinstanced_dir = absolute_path(args.preinstanced_dir)
    log(Colours.CYAN, string.format("Preinstanced Directory: %s", preinstanced_dir))

    local blend_dir = absolute_path(args.blend_dir)
    log(Colours.CYAN, string.format("Blend Directory: %s", blend_dir))

    local glb_dir = absolute_path(args.glb_dir)
    log(Colours.CYAN, string.format("GLB Directory: %s", glb_dir))

    local database_output_directory = absolute_path(args.output_dir)
    log(Colours.CYAN, string.format("Database Output Directory: %s", database_output_directory))
    sdk.ensure_dir(database_output_directory)

    local db_filename = args.db_file_path
    log(Colours.CYAN, string.format("Database file will be at: %s", db_filename))

    local root_drive = absolute_path(args.root_drive)
    log(Colours.CYAN, string.format("Root Drive for Symlinks: %s", root_drive))

    local blank_blend_source = absolute_path(args.blank_blend_source)
    log(Colours.CYAN, string.format("Blank Blend Source: %s", blank_blend_source))

    local debug_mode_enabled = not not args.debug_sleep
    log(Colours.CYAN, string.format("Debug Mode Enabled: %s", tostring(debug_mode_enabled)))

    local db
    -- Ensure parent directory for DB file exists
    local db_dir = parent_dir(db_filename)
    if db_dir and not sdk.is_dir(db_dir) then
        log(Colours.CYAN, string.format("Ensuring database directory exists: %s", db_dir))
        sdk.ensure_dir(db_dir)
    end

    local ok, err = pcall(function()
        log(Colours.CYAN, "--- Initializing Database ---")
        if sdk.path_exists and sdk.path_exists(db_filename) and debug_mode_enabled then
            if not (sdk.remove_file and sdk.remove_file(db_filename)) then
                error("Failed to delete existing database file: " .. db_filename)
            end
            log(Colours.GREEN, string.format("Deleted existing database file: %s", db_filename))
        end

        if (sdk.path_exists(db_filename) and not debug_mode_enabled) then
            -- db exists, check if tables are empty before skipping re-initialization
            local temp_db = init_db(db_filename)
            local row_count = temp_db.query("SELECT COUNT(*) as count FROM asset_map")[1].count
            temp_db.close()
            --temp_db = nil

            if row_count == 0 then
                log(Colours.YELLOW, string.format("Database file %s exists but asset_map table is empty; deleting and re-initializing.", db_filename))

                -- Force garbage collection to ensure file handles are released
                if collectgarbage then
                    collectgarbage("collect")
                end

                -- Small delay to allow OS to release file locks
                if sdk.sleep then
                    sdk.sleep(0.1)
                end

                local delete_success = sdk.remove_file and sdk.remove_file(db_filename)
                if not delete_success then
                    log(Colours.RED, string.format("Failed to delete empty database file: %s. File may be locked. Attempting to continue anyway.", db_filename))
                    -- Try to proceed anyway - init_db might overwrite it
                end

                db = init_db(db_filename)
                log(Colours.GREEN, string.format("Empty database deleted and re-initialized at: %s", db_filename))
            else
                log(Colours.CYAN, string.format("Database file %s already exists with %d records; skipping re-initialization.", db_filename, row_count))
                db = init_db(db_filename)
                return
            end
        else
            db = init_db(db_filename)
        end
        log(Colours.GREEN, string.format("Database initialized/opened at: %s", db_filename))
        if debug_mode_enabled then
            sdk.sleep(2)
        end

        log(Colours.CYAN, "--- Step 1: Processing Preinstanced Files (Copy blank blends, create dir structure) ---")
        local processor = PreinstancedFileProcessor.new({
            input_dir = preinstanced_dir,
            blend_dir = blend_dir,
            glb_dir = glb_dir,
            blank_blend_source = blank_blend_source,
            debug_mode_enabled = debug_mode_enabled,
            verbose = VERBOSE
        })
        if debug_mode_enabled then
            sdk.sleep(2)
        end
        processor:process_files()
        log(Colours.GREEN, "--- Step 1: Completed ---")
        if debug_mode_enabled then
            sdk.sleep(2)
        end

        log(Colours.CYAN, string.format("--- Step 2: Preparing Symbolic Link Root Directory: %s ---", root_drive))
        if sdk.path_exists and sdk.path_exists(root_drive) then
            if not sdk.is_dir(root_drive) then
                error(string.format("Symlink root path %s exists but is not a directory. Please resolve this.", root_drive))
            end
            log(Colours.CYAN, string.format("Symlink root directory %s already exists. Proceeding.", root_drive))
            if not (sdk.remove_dir and sdk.remove_dir(root_drive)) then
                error(string.format("Could not remove existing directory %s", root_drive))
            end
        end
        sdk.ensure_dir(root_drive)
        log(Colours.GREEN, string.format("Root directory for symbolic links ensured: %s", root_drive))
        if debug_mode_enabled then
            sdk.sleep(2)
        end

        log(Colours.CYAN, "--- Step 3: Generating Asset Map & Populating Database ---")
        if debug_mode_enabled then
            sdk.sleep(2)
        end
        local asset_count = generate_asset_mapping(db, root_drive, preinstanced_dir, blend_dir, marker, glb_dir, false)
        log(Colours.GREEN, string.format("Generated and stored map for %d assets in the database.", asset_count))
        if debug_mode_enabled then
            sdk.sleep(2)
        end

        log(Colours.CYAN, string.format("--- Step 4: Creating Symbolic Links in: %s ---", root_drive))
        if debug_mode_enabled then
            sdk.sleep(2)
        end
        create_symbolic_links(db, root_drive, debug_mode_enabled)
        log(Colours.GREEN, "--- Step 4: Symbolic links creation and DB update process completed. ---")
        if debug_mode_enabled then
            sdk.sleep(2)
        end
    end)

    if not ok then
        log(Colours.RED, string.format("An unexpected ERROR occurred: %s", tostring(err)))
        if db and db.close then
            db.close()
        end
        error(err)
    end

    if db and db.close then
        db.close()
        log(Colours.CYAN, "Database connection closed.")
    end
end

local M = {}
M.main = run

return M
