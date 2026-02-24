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

local function main()
    -- Path separator for current platform ("/" on Unix, "\\" on Windows)
    local path_sep = package.config:sub(1, 1)
    -- Log prefix so messages are easy to filter downstream
    local PREFIX = "BlenderRun"
    -- Console colour names (used only if host SDK supports coloured printing)
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

    -- Convenience logger that prepends a prefix and colourizes output
    local function log(colour, message)
        sdk.colour_print({ colour = colour or Colours.DEFAULT, message = string.format("[%s] %s", PREFIX, message or "") })
    end

    -- Normalize path separators in a single string to the current platform
    local function normalize_separators(path)
        if not path then
            return path
        end
        if path_sep == "\\" then
            return path:gsub("/", "\\")
        end
        return path:gsub("\\", "/")
    end

    -- Join an arbitrary number of path segments with exactly one separator between them
    -- Trims duplicate leading/trailing separators from middle parts
    local function join(...)
        local parts = { ... }
        local buffer = {}
        for index = 1, #parts do
            local part = parts[index]
            if part and part ~= "" then
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

    -- Parse argv-style table into a structured options table
    -- Returns:
    -- {
    --   verbose: boolean | nil,
    --   debug_sleep: boolean | nil,
    --   export: boolean,
    --   formats: { string, ... }
    -- }
    local function parse_arguments(args)
        local result = {
            game_root = nil,
            formats = {},
            export = false,
            verbose = false,
            debug_sleep = false,
            base_dir = nil,
            operations_dir = nil,
            blender_dir = nil,
            preinstanced_dir = nil,
            blend_dir = nil,
            blank_blend_source = nil,
            symlink_path = nil,
            asset_map_db = nil,
            rename_map_file = nil
        }
        -- Byte-wise helpers to avoid Lua pattern engine entirely
        local function is_space_byte(b)
            return b == 9 or b == 10 or b == 11 or b == 12 or b == 13 or b == 32
        end
        local function trim_ascii(s)
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
        local function strip_surrounding_quotes(s)
            if not s or #s < 2 then return s end
            local first = string.sub(s, 1, 1)
            local last = string.sub(s, -1)
            if (first == '"' and last == '"') or (first == "'" and last == "'") then
                return string.sub(s, 2, -2)
            end
            return s
        end
        local function trim_trailing_punct_ws(s)
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
        local function clean_value(v)
            if v == nil then return v end
            local s = trim_ascii(tostring(v))
            s = strip_surrounding_quotes(s)
            s = trim_trailing_punct_ws(s)
            return trim_ascii(s)
        end
        local function match_assignment(token)
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
        local i = 1
        while args and i <= #args do
            local argument = tostring(args[i])
            -- Normalize token by trimming whitespace and trailing punctuation
            local arg_token = trim_trailing_punct_ws(trim_ascii(argument))
            local option_name, inline_value = match_assignment(arg_token)
            if option_name == "--verbose" then
                result.verbose = true
            elseif option_name == "--debug-sleep" then
                result.debug_sleep = true
            elseif option_name == "--export" then
                result.export = true
                if inline_value and #inline_value > 0 then
                    table.insert(result.formats, clean_value(inline_value))
                end
                -- Collect all non-flag values following --export as formats
                i = i + 1
                while i <= #args do
                    local next_tok = tostring(args[i])
                    -- Stop if next token looks like a flag
                    if string.sub(next_tok, 1, 2) == "--" then
                        i = i - 1
                        break
                    end
                    table.insert(result.formats, clean_value(args[i]))
                    i = i + 1
                end
            elseif option_name == "--game-root" or option_name == "--game_root" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --game-root")
                    end
                end
                result.game_root = clean_value(value)
            elseif option_name == "-g" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after -g")
                    end
                end
                result.game_root = clean_value(value)
            elseif option_name == "--blank-blend" or option_name == "--blank_blend" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --blank-blend")
                    end
                end
                result.blank_blend_source = clean_value(value)
            elseif option_name == "--base-dir" or option_name == "--base_dir" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --base-dir")
                    end
                end
                result.base_dir = clean_value(value)
            elseif option_name == "--operations-dir" or option_name == "--operations_dir" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --operations-dir")
                    end
                end
                result.operations_dir = clean_value(value)
            elseif option_name == "--blender-dir" or option_name == "--blender_dir" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --blender-dir")
                    end
                end
                result.blender_dir = clean_value(value)
            elseif option_name == "--GameFiles" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --GameFiles")
                    end
                end
                result.preinstanced_dir = clean_value(value)
                result.blend_dir = clean_value(value) -- use the same dir
            elseif option_name == "--symlink-path" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --symlink-path")
                    end
                end
                result.symlink_path = clean_value(value)
            elseif option_name == "--asset-map-db" or option_name == "--asset_map_db" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --asset-map-db")
                    end
                end
                result.asset_map_db = clean_value(value)
            elseif option_name == "--rename-map" or option_name == "--rename_map" then
                local value = inline_value
                if value == nil or #value == 0 then
                    i = i + 1
                    if i <= #args then
                        value = args[i]
                    else
                        error("Expected value after --rename-map")
                    end
                end
                result.rename_map_file = clean_value(value)
            end
            i = i + 1
        end
        return result
    end

    -- Load a Lua module from file expecting it to return a table API
    -- Note: loadfile/dofile are disabled in the engine sandbox; use io + load instead.
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

    -- Split a Windows drive prefix (e.g., "C:") from a path; returns drive, remainder
    local function split_drive(path)
        if not path then
            return nil, path
        end
        local drive = path:match("^(%a:)")
        if drive then
            local remainder = path:sub(#drive + 1)
            return drive, remainder
        end
        return nil, path
    end

    local function tableToString(t)
        if next(t) == nil then
            return "none"
        end
        local result = {}
        for k, v in pairs(t) do
            if type(v) == "table" then
                table.insert(result, tostring(k) .. "=" .. tableToString(v))
            else
                table.insert(result, tostring(k) .. "=" .. tostring(v))
            end
        end
        return "{" .. table.concat(result, ", ") .. "}"
    end


    -- Quick diagnostic: print raw argv as seen by this script
    do
        local buf = {}
        for idx = 1, #argv do
            table.insert(buf, tostring(argv[idx]))
        end
        sdk.colour_print({ colour = Colours.GRAY, message = string.format("[" .. PREFIX .. "] raw argv: %s", table.concat(buf, ", ")) })
    end

    local cli = parse_arguments(argv)
    local path_fields = { "game_root", "base_dir", "operations_dir", "blender_dir", "preinstanced_dir", "blend_dir", "blank_blend_source", "symlink_path" }
    for _, key in ipairs(path_fields) do
        local value = cli[key]
        if type(value) == "string" and #value > 0 then
            cli[key] = normalize_separators(value)
        end
    end
    log(Colours.BLUE, string.format("cli arg export: %s", tostring(cli.export)))
    log(Colours.BLUE, string.format("cli arg formats: %s", tableToString(cli.formats)))
    log(Colours.BLUE, string.format("cli arg verbose: %s", tostring(cli.verbose)))
    log(Colours.BLUE, string.format("cli arg debug_sleep: %s", tostring(cli.debug_sleep)))
    log(Colours.BLUE, string.format("cli arg game_root: %s", tostring(cli.game_root)))
    log(Colours.BLUE, string.format("cli arg base_dir: %s", tostring(cli.base_dir)))
    log(Colours.BLUE, string.format("cli arg operations_dir: %s", tostring(cli.operations_dir)))
    log(Colours.BLUE, string.format("cli arg blender_dir: %s", tostring(cli.blender_dir)))
    log(Colours.BLUE, string.format("cli arg preinstanced_dir: %s", tostring(cli.preinstanced_dir)))
    log(Colours.BLUE, string.format("cli arg blend_dir: %s", tostring(cli.blend_dir)))
    log(Colours.BLUE, string.format("cli arg blank_blend_source: %s", tostring(cli.blank_blend_source)))
    log(Colours.BLUE, string.format("cli arg symlink_path: %s", tostring(cli.symlink_path)))
    log(Colours.BLUE, string.format("cli arg asset_map_db: %s", tostring(cli.asset_map_db)))

    -- Establish working directory for resolving relative project paths
    local working_dir = normalize_separators(sdk.currentdir())
    log(Colours.CYAN, string.format("Working directory: %s", working_dir))

    -- Project-relative paths for the game's operations
    -- If --game-root is provided, use it as the base directory; otherwise use repo-relative path
    local base_dir = cli.base_dir or cli.game_root or join("EngineApps", "Games", "TheSimpsonsGame-PS3")
    base_dir = normalize_separators(base_dir)
    local operations_dir = cli.operations_dir or join(base_dir, "operations")
    operations_dir = normalize_separators(operations_dir)
    local blender_dir = cli.blender_dir or join(operations_dir, "Blender")
    blender_dir = normalize_separators(blender_dir)

    -- Input/output locations within the repo working tree
    -- preinstanced_dir: source GLBs and support assets
    -- blend_dir       : working folder for .blend files
    -- glb_dir         : location of GLB files
    -- output_dir      : database output location
    local preinstanced_dir = cli.preinstanced_dir --or join(cli.game_root, "GameFiles", "STROUT")
    preinstanced_dir = preinstanced_dir and normalize_separators(preinstanced_dir) or preinstanced_dir
    local blend_dir = cli.blend_dir --or join(cli.game_root, "GameFiles", "TEMP_BLEND")
    blend_dir = blend_dir and normalize_separators(blend_dir) or blend_dir
    local blank_blend_source = cli.blank_blend_source or join(cli.game_root, "blank.blend")
    blank_blend_source = blank_blend_source and normalize_separators(blank_blend_source) or blank_blend_source
    -- Use the resolved blender_dir as output_dir to stay consistent with base_dir choice
    local output_dir = blender_dir

    log(Colours.CYAN, string.format("Resolved base_dir: %s", tostring(base_dir)))
    log(Colours.CYAN, string.format("Resolved operations_dir: %s", tostring(operations_dir)))
    log(Colours.CYAN, string.format("Resolved blender_dir: %s", tostring(blender_dir)))
    log(Colours.CYAN, string.format("Resolved preinstanced_dir: %s", tostring(preinstanced_dir)))
    log(Colours.CYAN, string.format("Resolved blend_dir: %s", tostring(blend_dir)))
    log(Colours.CYAN, string.format("Resolved blank_blend_source: %s", tostring(blank_blend_source)))

    -- Template/marker artifacts for Blender scene creation
    local function is_absolute(path)
        if not path then return false end
        if path:match("^%a:[/\\]") then return true end
        if path:sub(1, 2) == "\\\\" then return true end
        if path:sub(1, 1) == "/" then return true end
        return false
    end

    -- Compute a root for temporary symlinks
    local drive, _ = split_drive(working_dir)
    local symlink_path
    if cli.symlink_path and #cli.symlink_path > 0 then
        if is_absolute(cli.symlink_path) then
            symlink_path = cli.symlink_path
        else
            symlink_path = normalize_separators(join(working_dir, cli.symlink_path))
        end
    elseif drive then
        symlink_path = normalize_separators(join(drive .. path_sep, "TMP_TSG_LNKS"))
    else
        symlink_path = normalize_separators(join(cli.game_root, "TMP_TSG_LNKS"))
    end
    log(Colours.CYAN, string.format("Resolved symlink_path: %s", tostring(symlink_path)))

    local marker = preinstanced_dir and (preinstanced_dir .. path_sep) or ""

    -- Ensure output folder exists before any writes
    sdk.ensure_dir(output_dir)

    -- Load phase modules (must export a `main(opts)` function)
    local BlenderInit = load_module(join(output_dir, join("init", "BlenderInit.lua")))
    if not BlenderInit or type(BlenderInit.main) ~= "function" then
        error("BlenderInit module did not return a table with a main(opts) function")
        os.exit(1)
    end
    local BlenderCore = load_module(join(output_dir, "BlenderCore.lua"))
    if not BlenderCore or type(BlenderCore.main) ~= "function" then
        error("BlenderCore module did not return a table with a main(opts) function")
        os.exit(1)
    end

    -- Options for initialization phase
    local init_opts = {
        game_root = cli.game_root,
        preinstanced_dir = preinstanced_dir,
        blend_dir = blend_dir,
        glb_dir = preinstanced_dir,
        output_dir = output_dir,
        symlink_path = symlink_path,
        blank_blend_source = blank_blend_source,
        marker = marker,
        debug_sleep = cli.debug_sleep,
        verbose = cli.verbose,
        db_file_path = join(cli.asset_map_db),
        rename_map_file = cli.rename_map_file
    }

    -- Phase 1: setup, link creation, and environment preparation
    local ok, err = pcall(function()
        log(Colours.CYAN, "Running Blender initialization phase")
        BlenderInit.main(init_opts)
    end)

    if not ok then
        log(Colours.RED, string.format("Initialization failed: %s", err))
    error(string.format("run blend init error: %s", err))
    end

    -- use engine tool resolver to get blender
    local blender_exe = nil
    local blender_exe_path = nil
    local tool_fn = rawget(_G, "tool")
    if type(tool_fn) == "function" then
        blender_exe = tool_fn("Blender")
        if blender_exe and blender_exe ~= "" then
            blender_exe_path = normalize_separators(blender_exe)
            log(Colours.CYAN, string.format("Resolved Blender executable via engine tool resolver: %s", tostring(blender_exe_path)))
        end
    end

    -- Options for core processing phase (imports, conversions, exports)
    local core_opts = {
        verbose = cli.verbose,
        debug_sleep = cli.debug_sleep,
        export = cli.export,
        export_formats = cli.formats,
        db_file_path = join(cli.asset_map_db),
        blender_exe_path = blender_exe_path,
        game_root = cli.game_root,
        preinstanced_dir = preinstanced_dir
    }

    -- Phase 2: actual Blender processing and export
    local ok_core, err_core = pcall(function()
        log(Colours.CYAN, "Running Blender processing phase with opts: " .. tableToString(core_opts))
        BlenderCore.main(core_opts)
    end)

    if not ok_core then
        log(Colours.RED, string.format("Processing failed: %s", err_core))
    error(string.format("run blend core error: %s", err_core))
    end

    -- All done
    log(Colours.GREEN, "Blender pipeline finished successfully.")
end

-- Execute main wrapped in pcall to avoid leaking errors outside
local _ok, _err = pcall(main)
if not _ok then
    local _sdk = rawget(_G, "sdk") or nil
    local msg = string.format("[BlenderRun] %s", tostring(_err))
    if _sdk and _sdk.colour_print then
        _sdk.colour_print({ colour = "red", message = msg })
    else
        print(msg)
    end
    error(string.format("run blend error %s", _err))
end
