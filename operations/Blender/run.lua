--[[
Blender operations runner for TheSimpsonsGame-PS3

Responsibilities
- Parse CLI flags and prepare environment
- Normalize paths cross-platform (Windows/Unix) and join segments safely
- Ensure required directories exist
- Load and run two phases: BlenderInit (setup/linking) and BlenderCore (processing/export)

CLI
- --verbose       : print extra diagnostics
- --debug-sleep   : optional sleep points for attaching debuggers
- --export <fmt>… : one or more export format strings (e.g., glb, fbx)

Usage
    [ [operation] ]
    id = 8
    Name = "Convert Models (.preinstanced -> .blend)"
    run-all = true
    depends-on = [7] # depends on blender, str extraction for assets, and texture extraction and conversion for materials
    script_type = "lua"
    script = "{{Game_Root}}/operations/Blender/run.lua"
    args = [
        "--game-root", "{{Game_Root}}",
        "--base-dir", "{{Game_Root}}",
        "--operations-dir", "{{Game_Root}}/operations",
        "--blender-dir", "{{Game_Root}}/operations/Blender",
        "--GameFiles", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
        "--blank-blend", "{{Game_Root}}/blank.blend",
        "--symlink-path", "{{Game_Root}}/TMP_TSG_LNKS-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}", # symbolic link root to avoid path length issues
        "--asset-map-db", "{{Game_Root}}/GameFiles/config/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}/AssetMap.sqlite",
    ]
--]]

sdk.color_print({ colour = "cyan", message = "[BlenderRun] Starting Blender operations runner..." })

---@type SharedUtils
import(join("..", "SharedUtils.lua"))

sdk.color_print({ colour = "cyan", message = "[BlenderRun] Imported SharedUtils." })

-- Bootstrap central utilities using the environment's script_dir
local path_sep = package.config:sub(1, 1)

sdk.color_print({ colour = "cyan", message = string.format("[BlenderRun] Detected path separator: '%s'", path_sep) })

---@type BlenderUtils
import(join("init", "BlenderUtils.lua"))

sdk.color_print({ colour = "cyan", message = "[BlenderRun] Imported BlenderUtils." })

---@class BlenderCliOptions
---@field formats table<integer, string>
---@field export boolean
---@field verbose boolean
---@field debug_sleep boolean
---@field operations_dir string|nil
---@field blender_dir string|nil
---@field preinstanced_dir string|nil
---@field blend_dir string|nil
---@field blank_blend_source string|nil
---@field symlink_path string|nil
---@field asset_map_db string|nil
---@field game_root string|nil
---@field rename_map_file string|nil

---@param args table<integer, string>|nil
---@return BlenderCliOptions
local function parse_arguments(args)
    local result = {
        formats = {},
        export = false,
        verbose = false,
        debug_sleep = false,
        operations_dir = nil,
        blender_dir = nil,
        preinstanced_dir = nil,
        blend_dir = nil,
        blank_blend_source = nil,
        symlink_path = nil,
        asset_map_db = nil,
    }
    ---@cast result BlenderCliOptions

    -- Map flags to result table keys
    local arg_map = {
        ["--blank-blend"]    = "blank_blend_source",
        ["--operations-dir"] = "operations_dir",
        ["--blender-dir"]    = "blender_dir",
        ["--symlink-path"]   = "symlink_path",
        ["--asset-map-db"]   = "asset_map_db",
    }
    ---@cast arg_map table<string, string>

    local i = 1
    while args and i <= #args do
        local token = tostring(args[i])
        -- Normalize token by trimming whitespace and trailing punctuation
        local arg_token = trim_trailing_punct_ws(trim_ascii(token))
        
        if arg_token == "--verbose" then
            result.verbose = true
        elseif arg_token == "--debug-sleep" then
            result.debug_sleep = true
        elseif arg_token == "--export" then
            result.export = true
            -- Handle --export formats
            while i + 1 <= #args and string.sub(tostring(args[i+1]), 1, 2) ~= "--" do
                i = i + 1
                table.insert(result.formats, clean_value(args[i]))
            end
        elseif arg_token == "--GameFiles" then
            i = i + 1
            local val = args[i] or error("Expected value after --GameFiles")
            result.preinstanced_dir = clean_value(val)
            result.blend_dir = clean_value(val)
        elseif arg_map[arg_token] then
            local key = arg_map[arg_token]
            i = i + 1
            local val = args[i] or error("Expected value after " .. arg_token)
            result[key] = clean_value(val)
        end
        i = i + 1
    end
    return result
end


---@return nil
local function main()
    sdk.color_print({ colour = "cyan", message = "[BlenderRun] Parsing CLI arguments..." })
    -- Quick diagnostic: print raw argv as seen by this script
    do
        local buf = {}
        ---@cast buf table<integer, string>
        for idx = 1, #argv do
            table.insert(buf, tostring(argv[idx]))
        end
        log(Colours.CYAN, string.format("raw argv: %s", table.concat(buf, ", ")), "BlenderRun")
    end

    local cli = parse_arguments(argv)
    ---@cast cli BlenderCliOptions
    local path_fields = { "game_root", "base_dir", "operations_dir", "blender_dir", "preinstanced_dir", "blend_dir", "blank_blend_source", "symlink_path" }
    ---@cast path_fields table<integer, string>
    sdk.color_print({ colour = "cyan", message = "[BlenderRun] Normalizing CLI path arguments..." })
    for _, key in ipairs(path_fields) do
        ---@cast key string
        local value = cli[key]
        if type(value) == "string" and #value > 0 then
            cli[key] = normalize(value)
        end
    end
    log(Colours.BLUE, string.format("cli arg export: %s", tostring(cli.export)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg formats: %s", sdk.text.json.encode(cli.formats)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg verbose: %s", tostring(cli.verbose)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg debug_sleep: %s", tostring(cli.debug_sleep)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg operations_dir: %s", tostring(cli.operations_dir)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg blender_dir: %s", tostring(cli.blender_dir)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg preinstanced_dir: %s", tostring(cli.preinstanced_dir)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg blend_dir: %s", tostring(cli.blend_dir)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg blank_blend_source: %s", tostring(cli.blank_blend_source)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg symlink_path: %s", tostring(cli.symlink_path)), "BlenderRun")
    log(Colours.BLUE, string.format("cli arg asset_map_db: %s", tostring(cli.asset_map_db)), "BlenderRun")

    -- Establish working directory for resolving relative project paths
    --local working_dir = normalize(sdk.currentdir())
    --log(Colours.CYAN, string.format("Working directory: %s", working_dir), "BlenderRun")
    local working_dir = normalize(Game_Root)
    ---@cast working_dir string
    log(Colours.CYAN, string.format("Working directory: %s", working_dir), "BlenderRun")

    -- Project-relative paths for the game's operations
    -- If --game-root is provided, use it as the base directory; otherwise use repo-relative path
    local base_dir = Game_Root
    base_dir = normalize(base_dir)
    ---@cast base_dir string
    local operations_dir = cli.operations_dir
    operations_dir = normalize(operations_dir)
    ---@cast operations_dir string|nil
    local blender_dir = cli.blender_dir
    blender_dir = normalize(blender_dir)
    ---@cast blender_dir string|nil

    -- Input/output locations within the repo working tree
    -- preinstanced_dir: source GLBs and support assets
    -- blend_dir       : working folder for .blend files
    -- glb_dir         : location of GLB files
    local preinstanced_dir = cli.preinstanced_dir
    preinstanced_dir = preinstanced_dir and normalize(preinstanced_dir)
    ---@cast preinstanced_dir string|nil
    local blend_dir = cli.blend_dir
    blend_dir = blend_dir and normalize(blend_dir)
    ---@cast blend_dir string|nil
    local blank_blend_source = cli.blank_blend_source
    blank_blend_source = blank_blend_source and normalize(blank_blend_source)
    ---@cast blank_blend_source string|nil


    log(Colours.CYAN, string.format("Resolved base_dir: %s", tostring(base_dir)), "BlenderRun")
    log(Colours.CYAN, string.format("Resolved operations_dir: %s", tostring(operations_dir)), "BlenderRun")
    log(Colours.CYAN, string.format("Resolved blender_dir: %s", tostring(blender_dir)), "BlenderRun")
    log(Colours.CYAN, string.format("Resolved preinstanced_dir: %s", tostring(preinstanced_dir)), "BlenderRun")
    log(Colours.CYAN, string.format("Resolved blend_dir: %s", tostring(blend_dir)), "BlenderRun")
    log(Colours.CYAN, string.format("Resolved blank_blend_source: %s", tostring(blank_blend_source)), "BlenderRun")

    -- Compute a root for temporary symlinks
    local drive, _ = split_drive(working_dir)
    ---@cast drive string|nil
    local symlink_path
    if cli.symlink_path and #cli.symlink_path > 0 then
        if is_absolute(cli.symlink_path) then
            symlink_path = cli.symlink_path
        else
            symlink_path = normalize(join(working_dir, cli.symlink_path))
        end
    elseif drive then
        symlink_path = normalize(join(drive .. path_sep, "TMP_TSG_LNKS"))
    else
        symlink_path = normalize(join(Game_Root, "TMP_TSG_LNKS"))
    end
    ---@cast symlink_path string
    log(Colours.CYAN, string.format("Resolved symlink_path: %s", tostring(symlink_path)), "BlenderRun")

    local marker = preinstanced_dir and (preinstanced_dir .. path_sep)
    ---@cast marker string|nil
    log(Colours.CYAN, string.format("Marker for path stripping: '%s'", marker or "nil"), "BlenderRun")

    -- Load phase modules (must export a `main(opts)` function)
    local initpath = join(script_dir, join("init", "BlenderInit.lua"))
    log(Colours.CYAN, string.format("Importing BlenderInit from: %s", initpath), "BlenderRun")
    ---@type BlenderInit
    local BlenderInit = import(initpath)
    if not BlenderInit or type(BlenderInit.main) ~= "function" then
        error("BlenderInit module did not return a table with a main(opts) function")
        os.exit(1)
    else
        log(Colours.CYAN, "Successfully imported BlenderInit module.", "BlenderRun")
    end

    local corepath = join(script_dir, "BlenderCore.lua")
    log(Colours.CYAN, string.format("Importing BlenderCore from: %s", corepath), "BlenderRun")
    ---@type BlenderCore
    local BlenderCore = import(corepath)
    if not BlenderCore or type(BlenderCore.main) ~= "function" then
        error("BlenderCore module did not return a table with a main(opts) function")
        os.exit(1)
    else
        log(Colours.CYAN, "Successfully imported BlenderCore module.", "BlenderRun")
    end

    -- Options for initialization phase
    local init_opts = {
        game_root = cli.game_root,
        preinstanced_dir = preinstanced_dir,
        blend_dir = blend_dir,
        glb_dir = preinstanced_dir,
        output_dir = blender_dir,
        symlink_path = symlink_path,
        blank_blend_source = blank_blend_source,
        marker = marker,
        debug_sleep = cli.debug_sleep,
        verbose = cli.verbose,
        db_file_path = cli.asset_map_db,
        rename_map_file = cli.rename_map_file
    }
    ---@cast init_opts BlenderInitOptions

    -- Phase 1: setup, link creation, and environment preparation
    local ok, err = pcall(function()
        log(Colours.CYAN, "Running Blender initialization phase", "BlenderRun")
        BlenderInit.main(init_opts)
    end)
    ---@cast ok boolean
    ---@cast err string|nil

    if not ok then
        log(Colours.RED, string.format("Initialization failed: %s", err), "BlenderRun")
        error(string.format("run blend init error: %s", err))
    end



    -- Options for core processing phase (imports, conversions, exports)
    local core_opts = {
        verbose = cli.verbose,
        debug_sleep = cli.debug_sleep,
        export = cli.export,
        export_formats = cli.formats,
        db_file_path = cli.asset_map_db,
        game_root_path = Game_Root,
        preinstanced_dir = preinstanced_dir
    }
    ---@cast core_opts BlenderCoreOptions

    -- Phase 2: actual Blender processing and export
    local ok_core, err_core = pcall(function()
        log(Colours.CYAN, "Running Blender processing phase with opts: " .. sdk.text.json.encode(core_opts), "BlenderRun")
        BlenderCore.main(core_opts)
    end)
    ---@cast ok_core boolean
    ---@cast err_core string|nil

    if not ok_core then
        log(Colours.RED, string.format("Processing failed: %s", err_core), "BlenderRun")
        error(string.format("run blend core error: %s", err_core))
    end

    -- All done
    log(Colours.GREEN, "Blender pipeline finished successfully.", "BlenderRun")
end

local _ok, _err = pcall(main)
---@cast _ok boolean
---@cast _err string|nil
if not _ok then
    local msg = string.format("[BlenderRun] %s", tostring(_err))
    sdk.colour_print({ colour = "red", message = msg })
    error(string.format("run blend error %s", _err))
end
