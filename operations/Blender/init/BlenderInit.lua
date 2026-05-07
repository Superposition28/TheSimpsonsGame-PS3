---@type SharedUtils
import(join(Game_Root, "operations", "SharedUtils"))

---@class BlenderInit
---@field main fun(args: BlenderInitOptions): nil

---@class BlenderInitOptions
---@field blender_dir string|nil
---@field output_dir string|nil
---@field verbose boolean|nil
---@field marker string|nil
---@field preinstanced_dir string|nil
---@field blend_dir string|nil
---@field glb_dir string|nil
---@field db_file_path string|nil
---@field symlink_path string|nil
---@field blank_blend_source string|nil
---@field debug_sleep boolean|nil
---@field game_root string|nil

---@param args BlenderInitOptions
---@return nil
local function run(args)

    log(Colours.CYAN, "Starting Blender Initialization with arguments:", "BlenderInit")

    -- Determine the directory where this script and its modules reside
    local base_path = args.blender_dir or (args.output_dir and sdk.realpath(args.output_dir)) or sdk.currentdir()

    -- Load sub-modules
    local init_path = base_path .. package.config:sub(1, 1) .. "init"
    ---@type BlenderUtils
    import(join(base_path, "init", "BlenderUtils.lua"))
    ---@type BlenderDbModule
    local DB_Module = import(join(base_path, "init", "BlenderDB.lua")).setup()
    ---@type BlenderProcessorModule
    local Processor_Module = import(join(init_path, "BlenderProcessor.lua")).setup()
    ---@type BlenderSymlinkLib
    local Symlink_Module = import(join(init_path, "BlenderSymlink.lua")).setup()

    local VERBOSE = not not args.verbose
    log(Colours.CYAN, string.format("Input args: %s", sdk.text.json.encode(args)), "BlenderInit")

    local marker = args.marker
    local preinstanced_dir = absolute_path(args.preinstanced_dir)
    local blend_dir = absolute_path(args.blend_dir)
    local glb_dir = absolute_path(args.glb_dir)
    local database_output_directory = absolute_path(args.output_dir)
    sdk.ensure_dir(database_output_directory)

    local db_filename = args.db_file_path
    if not db_filename or db_filename == "" then
        error("db_file_path is required for BlenderInit")
    end
    ---@cast db_filename string
    local symlink_path = absolute_path(args.symlink_path)
    local blank_blend_source = absolute_path(args.blank_blend_source)
    local debug_mode_enabled = not not args.debug_sleep

    local db
    -- Ensure parent directory for DB file exists
    local db_dir = parent_dir(db_filename)
    if db_dir and not sdk.is_dir(db_dir) then
        log(Colours.CYAN, string.format("Ensuring database directory exists: %s", db_dir), "BlenderInit")
        sdk.ensure_dir(db_dir)
    end

    local ok, err = pcall(function()
        log(Colours.CYAN, "--- Initializing Database ---", "BlenderInit")
        if sdk.path_exists and sdk.path_exists(db_filename) and debug_mode_enabled then
            if not (sdk.remove_file and sdk.remove_file(db_filename)) then
                error("Failed to delete existing database file: " .. db_filename)
            end
            log(Colours.GREEN, string.format("Deleted existing database file: %s", db_filename), "BlenderInit")
        end

        if (sdk.path_exists(db_filename) and not debug_mode_enabled) then
            -- db exists, check if tables are empty before skipping re-initialization
            local temp_db = DB_Module.init_db(db_filename)
            local row_count = temp_db.query("SELECT COUNT(*) as count FROM asset_map")[1].count
            temp_db.close()

            if row_count == 0 then
                log(Colours.YELLOW, string.format("Database file %s exists but asset_map table is empty; deleting and re-initializing.", db_filename))

                --if collectgarbage then collectgarbage("collect") end
                if sdk.sleep then sdk.sleep(0.1) end

                local delete_success = sdk.remove_file and sdk.remove_file(db_filename)
                if not delete_success then
                    log(Colours.RED, string.format("Failed to delete empty database file: %s. File may be locked. Attempting to continue anyway.", db_filename))
                end

                db = DB_Module.init_db(db_filename)
                log(Colours.GREEN, string.format("Empty database deleted and re-initialized at: %s", db_filename))
            else
                log(Colours.CYAN, string.format("Database file %s already exists with %d records; skipping re-initialization.", db_filename, row_count))
                db = DB_Module.init_db(db_filename)
                return
            end
        else
            db = DB_Module.init_db(db_filename)
        end
        log(Colours.GREEN, string.format("Database initialized/opened at: %s", db_filename))
        if debug_mode_enabled then sdk.sleep(2) end

        log(Colours.CYAN, "--- Step 1: Processing Preinstanced Files (Copy blank blends, create dir structure) ---")
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
        log(Colours.GREEN, "--- Step 1: Completed ---")
        if debug_mode_enabled then sdk.sleep(2) end

        log(Colours.CYAN, "--- Step 2: Generating Asset Map & Populating Database ---")
        if debug_mode_enabled then sdk.sleep(2) end

        local asset_count = DB_Module.generate_asset_mapping(db, symlink_path, preinstanced_dir, blend_dir, marker, glb_dir, false, VERBOSE, args.game_root)
        log(Colours.GREEN, string.format("Generated and stored map for %d assets in the database.", asset_count))
        if debug_mode_enabled then sdk.sleep(2) end

        log(Colours.CYAN, "--- Step 3: Creating Symbolic Links ---")
        Symlink_Module.create_symbolic_links(db, symlink_path, preinstanced_dir, blend_dir, marker, glb_dir, debug_mode_enabled, VERBOSE)
        log(Colours.GREEN, "--- Step 3: Completed ---")
    end)

    if not ok then
        log(Colours.RED, string.format("An unexpected ERROR occurred: %s", tostring(err)))
        if db and db.close then db.close() end
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
