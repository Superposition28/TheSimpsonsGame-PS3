--[[
DirectoryNormalizer.lua (Simple Mode + Collapse + Rules v2)

This script normalizes a directory by performing transformations:
1. Removes the nested path segments '/build/PS3/pal_en' or '/build/PS3/ntsc_en'.
2. Renames any folder named 'texture_dictionary' to 'txd'.
3. NEW: Removes redundant "level name" folders from sub-paths.
   e.g., 'Map_X/level/a/b/level/c' -> 'Map_X/level/a/b/c'
4. Finds any folder that contains only one other folder, and merges their names.
5. Appends a 6-character hex UID to each filename.
6. NEW: When --copyonly is used, those directories are excluded from normalization and copied as-is after normalization.
    - Copy-only assets are still included in mapping outputs with uid/new_path/original_path fields.
    - Audio UIDs are extracted from *.exa.wav filenames (last 6 chars before .exa.wav).
    - Video UIDs are auto-assigned from the canonical relative path stem (no extension).
    - UID is inserted before the *first* extension (e.g., file_UID.rws.PS3).
7. NEW: Removes redundant level shortform tokens from folder names after the level folder
    and collapses repeated tokens within a segment.
    e.g., 'assets_rws_loc_loc' -> 'assets_rws', 'assets_rws_simpsons_chars_simpsons_chars' -> 'assets_rws'.
8. NEW: Normalizes redundant mode folders and zone asset folders.
    e.g., 'challenge_mode/challenge_mode_design_str' -> 'challenge_mode_design_str',
    and when parent matches 'zoneNN_*', 'assets_environs_zoneNN' -> 'assets_environs'.

]]

-- Load a Lua module from file expecting it to return a table API
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

-- Arg parsing ---------------------------------------------------------------
local function parse_args(argv)
    local function gets(i) local v = argv[i]; return type(v) == "string" and v or nil end
    local out = { ignores = {}, copyonly = {}, dry_run = false, map_db_file = nil, camel_only = false }
    out.src = gets(1)
    out.dst = gets(2)
    local i = 3
    while true do
        local a = gets(i); if not a then break end
        if a == "--ignore" then
            table.insert(out.ignores, gets(i+1) or "")
            i = i + 2
        elseif a == "--copyonly" then
            table.insert(out.copyonly, gets(i+1) or "")
            i = i + 2
        elseif a == "--dry-run" then
            out.dry_run = true
            i = i + 1
        elseif a == "--camel-only" then
            out.camel_only = true
            i = i + 1
        elseif a == "--map-db-file" then
            out.map_db_file = gets(i+1)
            i = i + 2
        else
            i = i + 1
        end
    end
    return out
end


-- Standard Module Loading ---------------------------

-- Main function -------------------------------------------------------------
local function main()
    local args = parse_args(argv)

    local path_sep = package.config:sub(1,1) or "/"
    local function join(a, b)
        if not a or a == "" then return b end
        if not b or b == "" then return a end
        local last = a:sub(-1)
        if last == "/" or last == "\\" then return a .. b end
        return a .. path_sep .. b
    end

    local utils = load_module(join(Game_Root, join("operations", join("DirectoryNormalizer", "utils.lua"))))
    local logic = load_module(join(Game_Root, join("operations", join("DirectoryNormalizer", "logic.lua"))))
    logic.init(utils)

    if not args.src or args.src == "" then error("source dir missing") end
    if not args.dst or args.dst == "" then error("output dir missing") end
    args.src = utils.norm_slashes(args.src)
    args.dst = utils.norm_slashes(args.dst)

    -- Load rename map for canonical UID generation
    local rename_map = {}
    if args.map_db_file and args.map_db_file ~= "" then
        local db_path = utils.norm_slashes(args.map_db_file)
        sdk.color_print("cyan", string.format("Loading rename mappings from: %s", db_path))
        Diagnostics.Trace(string.format("[DirectoryNormalizer] Loading rename mappings from: %s", db_path))
        rename_map = logic.load_rename_map(db_path)
        local count = (function() local c=0; for _ in pairs(rename_map) do c=c+1 end; return c end)()
        sdk.color_print("green", string.format("Loaded %d rename mappings", count))
        Diagnostics.Trace(string.format("[DirectoryNormalizer] Loaded %d rename mappings", count))
    end

    sdk.ensure_dir(args.dst)

    local files = logic.walk_files(args.src, args.ignores)
    local copyonly_set = logic.BuildCopyOnlySet(args.copyonly)
    local copyonly_files = {}

    local prog = progress.new(#files, "normalize", "Normalizing directory")
    local ok, err = pcall(function()
        Diagnostics.Trace(string.format("Starting normalization: %d files found", #files))

        -- NEW: Optional exit for isolated camelCase testing
        if args.camel_only then
            sdk.color_print("cyan", "Running in camel-only mode...")
            local total = 0
            for i=1, #files do
                local full = files[i]
                local rel = utils.rel_path(full, args.src)
                local new_rel = rel
                
                -- Skip conversion for copy-only sets
                if not logic.IsCopyOnlyPath(rel, copyonly_set) then
                    new_rel = logic.apply_camel_case_to_path(rel)
                end
                
                local new_path = utils.join(args.dst, new_rel)
                if not args.dry_run then
                    utils.copy_with_collision_handling(full, new_path)
                end
                total = total + 1
                if prog then prog:Update(1) end
            end
            sdk.color_print("green", string.format("Camel-only pass complete. Copied %d files.", total))
            return -- Exit early, completely bypassing full normalization
        end

        local file_targets = {}
        local target_tree = { [""] = { dirs={}, files={} } } -- Init root node
        local mapping_rows = {}
        local total = 0
        local per_folder_maps = {} -- NEW: To store per-folder mappings

        -- PASS 1: Pre-scan all files
        -- Build the list of target files (after build-path removal)
        -- Build the in-memory tree of the target structure
        for i=1,#files do
            local full = files[i]
            local rel = utils.rel_path(full, args.src)

            if logic.IsCopyOnlyPath(rel, copyonly_set) then
                table.insert(copyonly_files, full)
            else
                -- Apply CamelCase conversion strictly before hitting the rules engine
                local camel_rel = logic.apply_camel_case_to_path(rel)
                
                -- Note: apply_file_rules now takes BOTH rel and camel_rel
                local rel_no_build, uid = logic.apply_file_rules(rel, camel_rel, utils.get_hex_uid, rename_map)

                -- Store for Pass 3
                table.insert(file_targets, {
                    full = full,
                    rel = rel,
                    rel_no_build = rel_no_build,
                    uid = uid
                })

                -- Add this conceptual path to the tree for Pass 2
                logic.add_to_tree(target_tree, rel_no_build)
            end
        end

        -- PASS 2: Build the collapse map
        -- This map will store { [old_dir] = new_collapsed_dir }
        local path_map = {}
        logic.build_collapse_map(target_tree, path_map, "", "")

        -- PASS 3: Process and copy normalized files
        for i=1, #file_targets do
            local target = file_targets[i]

            local pre_collapse_dir = utils.dirname(target.rel_no_build)
            local filename = utils.basename(target.rel_no_build)

            -- Look up the collapsed path. Fallback to original if not in map (e.g., root files)
            local new_collapsed_dir = path_map[pre_collapse_dir]
            if not new_collapsed_dir then
                new_collapsed_dir = pre_collapse_dir
            end

            local rel_parts = utils.split_path(target.rel)
            local level_folder_lower = rel_parts[1] and string.lower(rel_parts[1]) or ""
            local level_name_lower = rel_parts[2] and string.lower(rel_parts[2]) or ""
            if new_collapsed_dir and new_collapsed_dir ~= "" then
                new_collapsed_dir = logic.NormalizeCollapsedDir(new_collapsed_dir, level_folder_lower, level_name_lower)
            end

            -- This is the final, normalized, collapsed path
            local new_rel = utils.join(new_collapsed_dir, filename)
            local new_path = utils.join(args.dst, new_rel)

            local row_data = {
                uid = target.uid,
                original_path = utils.to_posix(target.rel),
                new_path = utils.to_posix(new_rel),
            }
            table.insert(mapping_rows, row_data)

            -- NEW: Group by top-level folder
            local parts = utils.split_path(target.rel)
            if #parts > 0 then
                local top_folder = parts[1]
                if not per_folder_maps[top_folder] then
                    per_folder_maps[top_folder] = {}
                end
                -- Insert the same row data
                table.insert(per_folder_maps[top_folder], row_data)
            end
            -- END NEW

            if not args.dry_run then
                utils.copy_with_collision_handling(target.full, new_path)
            end

            total = total + 1
            if prog then prog:Update(1) end
        end

        -- PASS 4: Copy copy-only directories as-is (no normalization)
        for i=1, #copyonly_files do
            local full = copyonly_files[i]
            local rel = utils.rel_path(full, args.src)
            local new_path = utils.join(args.dst, rel)

            local uid = logic.GetCopyOnlyUid(rel, utils.get_hex_uid, rename_map)
            local row_data = {
                uid = uid,
                original_path = utils.to_posix(rel),
                new_path = utils.to_posix(rel),
            }
            table.insert(mapping_rows, row_data)

            local parts = utils.split_path(rel)
            if #parts > 0 then
                local top_folder = parts[1]
                if not per_folder_maps[top_folder] then
                    per_folder_maps[top_folder] = {}
                end
                table.insert(per_folder_maps[top_folder], row_data)
            end

            if not args.dry_run then
                utils.copy_with_collision_handling(full, new_path)
            end
            total = total + 1
            if prog then prog:Update(1) end
        end

        -- Sort rows
        table.sort(mapping_rows, function(a,b)
            return a.original_path < b.original_path
        end)

        -- Write JSON outputs
        local map_json = utils.join(args.dst, "normalized_map.json")
        utils.write_all_text(map_json, utils.json_encode(mapping_rows, true))

        -- NEW: Write per-folder JSON maps
        sdk.color_print("cyan", "Writing per-folder JSON maps...")
        Diagnostics.Trace("[DirectoryNormalizer] Writing per-folder JSON maps...")
        local per_folder_files = {}
        for top_folder, rows in pairs(per_folder_maps) do
            -- Ensure these are also sorted just like the main map
            table.sort(rows, function(a,b)
                return a.original_path < b.original_path
            end)

            -- Sanitize folder name for use in a filename (basic sanitization)
            local safe_name = top_folder:gsub("[^a-zA-Z0-9_%-]", "_")
            local map_filename = string.format("map_%s.json", safe_name)
            local map_json_path = utils.join(args.dst, map_filename)

            utils.write_all_text(map_json_path, utils.json_encode(rows, true))
            table.insert(per_folder_files, map_filename)
        end
        sdk.color_print("green", string.format("Wrote %d per-folder maps.", #per_folder_files))
        Diagnostics.Trace(string.format("[DirectoryNormalizer] Wrote %d per-folder maps.", #per_folder_files))
        -- END NEW

        local summary = {
            total_assets = total,
            files_written = { utils.basename(map_json) }
        }

        -- NEW: Add per-folder maps to summary
        for _, f in ipairs(per_folder_files) do
            table.insert(summary.files_written, f)
        end

        utils.write_all_text(utils.join(args.dst, "normalized_map_summary.json"), utils.json_encode(summary, true))

        sdk.color_print("green", "-------------------------------------------")
        sdk.color_print("green", string.format("Normalized %d assets.", total))
        sdk.color_print("green", string.format("JSON mapping written to: %s", map_json))
        sdk.color_print("green", string.format("Summary: %s", utils.join(args.dst, "normalized_map_summary.json")))
        Diagnostics.Trace(string.format("[DirectoryNormalizer] Normalized %d assets.", total))
    end)

    if prog then prog:Complete() end
    if not ok then error(err) end
end

-- run
main()

