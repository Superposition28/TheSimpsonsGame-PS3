if not sqlite then
    error("sqlite module is not available; ensure LuaScriptAction exposes sqlite helpers")
end

-- Load module helper for the sandboxed environment
local function load_module(path)
    local fh, open_err = io.open(path, "r")
    if not fh then
        error(string.format("Failed to open module '%s': %s", path, tostring(open_err)))
    end
    local src = fh:read("*a")
    fh:close()
    local chunk, err = load(src, "@" .. path, "t", _ENV)
    if not chunk then
        error(string.format("Failed to compile module '%s': %s", path, err))
    end
    local module = chunk()
    if type(module) ~= "table" then
        error(string.format("Module '%s' did not return a table", path))
    end
    return module
end

local function run(args)
    -- Determine the directory where this script and its modules reside
    local base_path = args.blender_dir or (args.output_dir and sdk.realpath(args.output_dir)) or sdk.currentdir()

    local function join(p1, p2)
        local sep = package.config:sub(1, 1)
        return p1 .. sep .. p2
    end

    -- Load sub-modules
    local init_path = join(base_path, "init")
    local Utils = load_module(join(init_path, "BlenderUtils.lua"))
    local DB_Module = load_module(join(init_path, "BlenderDB.lua")).setup(Utils)
    local Processor_Module = load_module(join(init_path, "BlenderProcessor.lua")).setup(Utils)
    local Symlink_Module = load_module(join(init_path, "BlenderSymlink.lua")).setup(Utils)

    local VERBOSE = not not args.verbose
    Utils.log(Utils.Colours.CYAN, string.format("Input args: %s", sdk.text.json.encode(args)))

    local marker = args.marker
    local preinstanced_dir = Utils.absolute_path(args.preinstanced_dir)
    local blend_dir = Utils.absolute_path(args.blend_dir)
    local glb_dir = Utils.absolute_path(args.glb_dir)
    local database_output_directory = Utils.absolute_path(args.output_dir)
    sdk.ensure_dir(database_output_directory)

    local db_filename = args.db_file_path
    local symlink_path = Utils.absolute_path(args.symlink_path)
    local blank_blend_source = Utils.absolute_path(args.blank_blend_source)
    local debug_mode_enabled = not not args.debug_sleep

    local db
    -- Ensure parent directory for DB file exists
    local db_dir = Utils.parent_dir(db_filename)
    if db_dir and not sdk.is_dir(db_dir) then
        Utils.log(Utils.Colours.CYAN, string.format("Ensuring database directory exists: %s", db_dir))
        sdk.ensure_dir(db_dir)
    end

    local ok, err = pcall(function()
        Utils.log(Utils.Colours.CYAN, "--- Initializing Database ---")
        if sdk.path_exists and sdk.path_exists(db_filename) and debug_mode_enabled then
            if not (sdk.remove_file and sdk.remove_file(db_filename)) then
                error("Failed to delete existing database file: " .. db_filename)
            end
            Utils.log(Utils.Colours.GREEN, string.format("Deleted existing database file: %s", db_filename))
        end

        if (sdk.path_exists(db_filename) and not debug_mode_enabled) then
            -- db exists, check if tables are empty before skipping re-initialization
            local temp_db = DB_Module.init_db(db_filename)
            local row_count = temp_db.query("SELECT COUNT(*) as count FROM asset_map")[1].count
            temp_db.close()

            if row_count == 0 then
                Utils.log(Utils.Colours.YELLOW, string.format("Database file %s exists but asset_map table is empty; deleting and re-initializing.", db_filename))

                if collectgarbage then collectgarbage("collect") end
                if sdk.sleep then sdk.sleep(0.1) end

                local delete_success = sdk.remove_file and sdk.remove_file(db_filename)
                if not delete_success then
                    Utils.log(Utils.Colours.RED, string.format("Failed to delete empty database file: %s. File may be locked. Attempting to continue anyway.", db_filename))
                end

                db = DB_Module.init_db(db_filename)
                Utils.log(Utils.Colours.GREEN, string.format("Empty database deleted and re-initialized at: %s", db_filename))
            else
                Utils.log(Utils.Colours.CYAN, string.format("Database file %s already exists with %d records; skipping re-initialization.", db_filename, row_count))
                db = DB_Module.init_db(db_filename)
                return
            end
        else
            db = DB_Module.init_db(db_filename)
        end
        Utils.log(Utils.Colours.GREEN, string.format("Database initialized/opened at: %s", db_filename))
        if debug_mode_enabled then sdk.sleep(2) end

        Utils.log(Utils.Colours.CYAN, "--- Step 1: Processing Preinstanced Files (Copy blank blends, create dir structure) ---")
        local processor = Processor_Module.PreinstancedFileProcessor.new({
            input_dir = preinstanced_dir,
            blend_dir = blend_dir,
            glb_dir = glb_dir,
            blank_blend_source = blank_blend_source,
            debug_mode_enabled = debug_mode_enabled,
            verbose = VERBOSE
        })
        if debug_mode_enabled then sdk.sleep(2) end
        processor:process_files()
        Utils.log(Utils.Colours.GREEN, "--- Step 1: Completed ---")
        if debug_mode_enabled then sdk.sleep(2) end

        Utils.log(Utils.Colours.CYAN, "--- Step 2: Generating Asset Map & Populating Database ---")
        if debug_mode_enabled then sdk.sleep(2) end


        local asset_count = DB_Module.generate_asset_mapping(db, symlink_path, preinstanced_dir, blend_dir, marker, glb_dir, false, VERBOSE, args.game_root)
        Utils.log(Utils.Colours.GREEN, string.format("Generated and stored map for %d assets in the database.", asset_count))
        if debug_mode_enabled then sdk.sleep(2) end

        Utils.log(Utils.Colours.CYAN, "--- Step 3: Creating Symbolic Links ---")
        Symlink_Module.create_symbolic_links(db, symlink_path, preinstanced_dir, blend_dir, marker, glb_dir, debug_mode_enabled, VERBOSE)
        Utils.log(Utils.Colours.GREEN, "--- Step 3: Completed ---")
    end)

    if not ok then
        Utils.log(Utils.Colours.RED, string.format("An unexpected ERROR occurred: %s", tostring(err)))
        if db and db.close then db.close() end
        error(err)
    end

    if db and db.close then
        db.close()
        Utils.log(Utils.Colours.CYAN, "Database connection closed.")
    end
end

local M = {}
M.main = run

return M
