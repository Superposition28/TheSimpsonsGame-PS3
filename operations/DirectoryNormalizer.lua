--[[
DirectoryNormalizer.lua (Simple Mode + Collapse + Rules v2)

This script normalizes a directory by performing transformations:
1. Removes the nested path segments '/build/PS3/pal_en' or '/build/PS3/ntsc_en'.
2. Renames any folder named 'texture_dictionary' to 'txd'.
3. NEW: Removes redundant "level name" folders from sub-paths.
   e.g., 'Map_X/level/a/b/level/c' -> 'Map_X/level/a/b/c'
4. Finds any folder that contains only one other folder, and merges their names.
5. Appends a 6-character hex UID to each filename.
   - UID is based on the original relative path stem (no extension).
   - NEW: UID is inserted before the *first* extension (e.g., file_UID.rws.PS3).

Runtime: lfs, dkjson, sdk, argv provided by engine
]]

local dkjson = require("dkjson")
local lfs = require("lfs")

-- Small utilities -----------------------------------------------------------
local path_sep = package.config:sub(1,1) or "/"

local function join(a, b)
    if not a or a == "" then return b end
    if not b or b == "" then return a end
    local last = a:sub(-1)
    if last == "/" or last == "\\" then return a .. b end
    return a .. path_sep .. b
end

local function norm_slashes(p)
    if not p then return p end
    if path_sep == "\\" then
        p = p:gsub("/", "\\")
    else
        p = p:gsub("\\", "/")
    end
    p = p:gsub("[/\\]+", path_sep)
    return p
end

local function split_path(p)
    local parts = {}
    for part in p:gmatch("[^/\\]+") do table.insert(parts, part) end
    return parts
end

local function ensure_dir(p)
    return sdk.ensure_dir(p)
end

local function path_exists(p)
    return sdk.path_exists(p)
end

local function write_all_text(path, data)
    local parent = path:match("^(.*)[/\\][^/\\]+$")
    if parent and parent ~= "" then ensure_dir(parent) end
    local f = io.open(path, "wb"); if not f then return false end
    f:write(data); f:close(); return true
end

local function dirname(p)
    local s = norm_slashes(p)
    local last = 0
    for i=1,#s do
        local ch = s:sub(i,i)
        if ch == '/' or ch == '\\' then last = i end
    end
    if last == 0 then return "" end
    return s:sub(1, last-1)
end

local function basename(p)
    local s = norm_slashes(p)
    local last = 0
    for i=1,#s do
        local ch = s:sub(i,i)
        if ch == '/' or ch == '\\' then last = i end
    end
    if last == 0 then return s end
    return s:sub(last+1)
end

-- JSON helpers --------------------------------------------------------------
local function json_decode(str)
    local obj = dkjson.decode(str)
    return obj
end

local function json_encode(obj, indent)
    return dkjson.encode(obj, { indent = indent ~= false })
end

-- Rename Map Loader --------------------------------------------------------
local function load_rename_map(db_path)
    -- Returns a table: { [new_name_lowercase] = old_name }
    local map = {}
    
    if not sdk.path_exists(db_path) then
        warn(string.format("RenameMap.db not found at: %s", db_path))
        return map
    end
    
    local db = sqlite.open(db_path)
    if not db then
        warn(string.format("Failed to open RenameMap.db: %s", db_path))
        return map
    end
    
    local ok, rows = pcall(function()
        return db:query("SELECT old_name, new_name FROM rename_mappings")
    end)
    
    if ok and rows then
        for _, row in ipairs(rows) do
            local old_name = row.old_name
            local new_name = row.new_name
            if old_name and new_name then
                map[string.lower(new_name)] = old_name
            end
        end
    else
        warn("Failed to query RenameMap.db")
    end
    
    db:close()
    return map
end

-- Canonical Path Normalizer ------------------------------------------------
local function normalize_to_canonical(rel_path, rename_map)
    -- Converts renamed folder names back to their original canonical names
    -- This ensures consistent UID generation regardless of folder renaming
    -- Example: "L10_BargainBin/file.dat" -> "bargainbin/file.dat"
    
    if not rename_map or not rel_path then
        return rel_path
    end
    
    local parts = split_path(rel_path)
    if #parts == 0 then
        return rel_path
    end
    
    -- Normalize the first folder (base folder) if it's in the rename map
    local base_folder = parts[1]
    local base_folder_lower = string.lower(base_folder)
    
    if rename_map[base_folder_lower] then
        -- Replace with canonical (original) name
        parts[1] = rename_map[base_folder_lower]
    end
    
    -- Reconstruct path with canonical base folder
    return table.concat(parts, "/")
end

-- UID Generator (6-char hex from MD5) --------------------------------
local function get_hex_uid(s, length)
    length = length or 6
    local hex = sdk.md5(s) or ""
    if hex == "" then return string.rep("0", length) end -- Fallback
    return string.lower(hex:sub(1, length))
end

-- Filename helper ------------------------------------------------------
local function multi_ext(name)
    local idx = nil
    for i = 1, #name do
        if name:sub(i, i) == '.' then
            idx = i
        end
    end
    if not idx then return name, "" end
    return name:sub(1, idx-1), name:sub(idx)
end


-- Core transformation -------------------------------------------------------

-- Define the segments to remove, as lowercase
local segments_to_remove = {
    { "build", "ps3", "pal_en" },
    { "build", "ps3", "ntsc_en" }
}

-- PASS 1: Apply build path removal, folder rename, and UID
local function apply_file_rules(original_rel, uid_generator_func, rename_map)
    local parts = split_path(original_rel)
    if #parts == 0 then return original_rel, "000000" end

    -- NEW: Identify level name to filter redundancy
    local level_name_lower = ""
    if #parts >= 2 then
        level_name_lower = string.lower(parts[2])
    end

    local new_parts = {}
    local i = 1
    while i <= #parts do
        local part = parts[i]
        local part_lower = string.lower(part)
        local matched_segment = false

        for _, segment in ipairs(segments_to_remove) do
            -- Check if the current part matches the start of a segment to be removed
            if part_lower == segment[1] and i + #segment - 1 <= #parts then
                local match = true
                for j = 1, #segment do
                    if string.lower(parts[i + j - 1]) ~= segment[j] then
                        match = false
                        break
                    end
                end

                if match then
                    -- It's a match, skip these parts
                    i = i + #segment
                    matched_segment = true
                    break
                end
            end
        end

        if not matched_segment then
            -- NEW: REQUIREMENT 3: Filter redundant level names
            -- (Only apply this check *after* the map and level folders themselves)
            if i > 2 and part_lower == level_name_lower then
                -- Skip this part
            else
                -- REQUIREMENT 2: Rename 'texture_dictionary' to 'txd'
                if part_lower == "texture_dictionary" then
                    part = "txd"
                end
                table.insert(new_parts, part)
            end
            i = i + 1
        end
    end

    if #new_parts == 0 then return original_rel, "000000" end

    local filename = table.remove(new_parts)
    local new_dir = table.concat(new_parts, path_sep)

    -- CRITICAL FIX: Normalize the ORIGINAL path to canonical form BEFORE UID generation
    -- This ensures "L10_BargainBin/file.dat" and "bargainbin/file.dat" produce the same UID
    local canonical_rel = normalize_to_canonical(original_rel, rename_map)
    local canonical_rel_stem, _ = multi_ext(canonical_rel)
    local uid = uid_generator_func(canonical_rel_stem, 6)

    -- NEW: REQUIREMENT 1 (UID Insertion): Place UID before any file extensions (before first '.')
    local base, rest = filename:match("^(.-)%.(.*)$")
    local new_filename
    if base then
        -- Has at least one dot: keep everything after the first dot intact
        -- e.g. "lodmodel1.rws.PS3.blend" -> "lodmodel1_<uid>.rws.PS3.blend"
        new_filename = string.format("%s_%s.%s", base, uid, rest)
    else
        -- No extension at all
        new_filename = string.format("%s_%s", filename, uid)
    end

    local new_rel_path = join(new_dir, new_filename)
    return new_rel_path, uid
end

-- PASS 1.5: Helper to build in-memory tree
local function add_to_tree(tree, path_str)
    local parts = split_path(path_str)
    local filename = table.remove(parts)
    local current_path = ""
    local t = tree[""] -- Start at root node

    for i=1, #parts do
        local part = parts[i]
        t.dirs[part] = true -- Mark dir as a child of parent

        local child_path = join(current_path, part)
        if not tree[child_path] then
            tree[child_path] = { dirs={}, files={} } -- Ensure node exists
        end
        t = tree[child_path] -- Descend
        current_path = child_path
    end

    if filename and filename ~= "" then
        t.files[filename] = true
    end
end

-- PASS 2: Build the path-collapsing map
-- Recursively walks the 'tree' and fills 'map'
-- map[original_path] = new_collapsed_path
local function build_collapse_map(tree, map, current_orig_path, current_new_path)
    local node = tree[current_orig_path]
    if not node then return end

    local dir_names = {}
    for k,_ in pairs(node.dirs) do table.insert(dir_names, k) end
    local file_names = {}
    for k,_ in pairs(node.files) do table.insert(file_names, k) end

    if #dir_names == 1 and #file_names == 0 then
        -- This is a collapsible folder. Don't add to map yet. Recurse.
        local child_name = dir_names[1]
        local child_orig_path = join(current_orig_path, child_name)

        -- Get the name of this folder (or use new_path if it's already a chain)
        local new_basename = basename(current_new_path)
        -- Handle root edge case where current_new_path is ""
        if current_orig_path == "" then
            new_basename = child_name
        elseif new_basename == "" then
             -- This happens if current_new_path was just "/"
            new_basename = basename(current_orig_path)
        end

        local new_collapsed_name = new_basename .. "_" .. child_name
        local new_collapsed_path = join(dirname(current_new_path), new_collapsed_name)

        -- Recurse into the child, passing the *new collapsed path*
        build_collapse_map(tree, map, child_orig_path, new_collapsed_path)
    else
        -- This is a "real" folder (0 or 2+ children, or has files).
        -- This is the end of a chain. Map the *original* path to the *final new* path.
        map[current_orig_path] = current_new_path

        -- Now recurse for all children, starting a *new* chain for each.
        for _, name in ipairs(dir_names) do
            local child_orig = join(current_orig_path, name)
            local child_new = join(current_new_path, name)
            build_collapse_map(tree, map, child_orig, child_new)
        end
    end
end


-- Arg parsing ---------------------------------------------------------------
local function parse_args(argv)
    local function gets(i) local v = argv[i]; return type(v) == "string" and v or nil end
    local out = { ignores = {}, dry_run = false, map_db_file = nil }
    out.src = gets(1)
    out.dst = gets(2)
    local i = 3
    while true do
        local a = gets(i); if not a then break end
        if a == "--ignore" then
            table.insert(out.ignores, gets(i+1) or "")
            i = i + 2
        elseif a == "--dry-run" then
            out.dry_run = true
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

-- Walk directory recursively with ignore filters
local function should_ignore_dir(name, ignore_list)
    local lname = string.lower(name)
    for _,ig in ipairs(ignore_list) do
        local v = string.lower(ig or "")
        if v ~= "" and lname == v then return true end
    end
    return false
end

local function walk_files(root, ignore_list)
    local stack = { root }
    local files = {}
    while #stack > 0 do
        local dir = table.remove(stack)
        for entry in lfs.dir(dir) do
            if entry ~= "." and entry ~= ".." then
                local p = join(dir, entry)
                local attr = lfs.attributes(p)
                if attr and attr.mode == "directory" then
                    if not should_ignore_dir(entry, ignore_list) then
                        table.insert(stack, p)
                    end
                else
                    table.insert(files, p)
                end
            end
        end
    end
    return files
end

local function rel_path(full, root)
    local f = norm_slashes(full)
    local r = norm_slashes(root)
    if f:sub(1, #r) == r then
        local rest = f:sub(#r+1)
        if rest:sub(1,1) == path_sep then rest = rest:sub(2) end
        return rest
    end
    return full
end

local function ext_lower(name)
    local last = nil
    for i=1,#name do
        if name:sub(i,i) == '.' then last = i end
    end
    if not last then return "" end
    return string.lower(name:sub(last))
end

local function copy_with_collision_handling(src, dst)
    local parent = dirname(dst)
    if parent and parent ~= "" then ensure_dir(parent) end
    local target = dst
    if path_exists(target) then
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
        until not path_exists(target)
    end
    return sdk.copy_file(src, target, false)
end

-- Main function -------------------------------------------------------------
local function main()
    local args = parse_args(argv)
    if not args.src or args.src == "" then error("source dir missing") end
    if not args.dst or args.dst == "" then error("output dir missing") end
    args.src = norm_slashes(args.src)
    args.dst = norm_slashes(args.dst)

    -- Load rename map for canonical UID generation
    local rename_map = {}
    if args.map_db_file and args.map_db_file ~= "" then
        local db_path = norm_slashes(args.map_db_file)
        print(string.format("Loading rename mappings from: %s", db_path))
        rename_map = load_rename_map(db_path)
        print(string.format("Loaded %d rename mappings", 
            (function() local c=0; for _ in pairs(rename_map) do c=c+1 end; return c end)()))
    else
        print("No rename map provided, UIDs will be based on actual folder names")
    end

    ensure_dir(args.dst)

    local files = walk_files(args.src, args.ignores)

    local prog = progress(#files, "normalize", "Normalizing directory")
    local ok, err = pcall(function()

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
            local rel = rel_path(full, args.src)

            -- Get the target path *before* collapse, and the UID
            -- CRITICAL: Pass rename_map for canonical UID generation
            local rel_no_build, uid = apply_file_rules(rel, get_hex_uid, rename_map)

            -- Store for Pass 3
            table.insert(file_targets, {
                full = full,
                rel = rel,
                rel_no_build = rel_no_build,
                uid = uid
            })

            -- Add this conceptual path to the tree for Pass 2
            add_to_tree(target_tree, rel_no_build)
        end

        -- PASS 2: Build the collapse map
        -- This map will store { [old_dir] = new_collapsed_dir }
        local path_map = {}
        build_collapse_map(target_tree, path_map, "", "")

        -- PASS 3: Process and copy files
        for i=1, #file_targets do
            local target = file_targets[i]

            local pre_collapse_dir = dirname(target.rel_no_build)
            local filename = basename(target.rel_no_build)

            -- Look up the collapsed path. Fallback to original if not in map (e.g., root files)
            local new_collapsed_dir = path_map[pre_collapse_dir]
            if not new_collapsed_dir then
                new_collapsed_dir = pre_collapse_dir
            end

            -- This is the final, normalized, collapsed path
            local new_rel = join(new_collapsed_dir, filename)
            local new_path = join(args.dst, new_rel)

            local row_data = {
                uid = target.uid,
                original_path = target.rel,
                new_path = new_rel,
            }
            table.insert(mapping_rows, row_data)

            -- NEW: Group by top-level folder
            local parts = split_path(target.rel)
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
                copy_with_collision_handling(target.full, new_path)
            end

            total = total + 1
            if prog then prog:Update(1) end
        end

        -- Sort rows
        table.sort(mapping_rows, function(a,b)
            return a.original_path < b.original_path
        end)

        -- Write JSON outputs
        local map_json = join(args.dst, "normalized_map.json")
        write_all_text(map_json, json_encode(mapping_rows, true))

        -- NEW: Write per-folder JSON maps
        print("Writing per-folder JSON maps...")
        local per_folder_files = {}
        for top_folder, rows in pairs(per_folder_maps) do
            -- Ensure these are also sorted just like the main map
            table.sort(rows, function(a,b)
                return a.original_path < b.original_path
            end)

            -- Sanitize folder name for use in a filename (basic sanitization)
            local safe_name = top_folder:gsub("[^a-zA-Z0-9_%-]", "_")
            local map_filename = string.format("map_%s.json", safe_name)
            local map_json_path = join(args.dst, map_filename)

            write_all_text(map_json_path, json_encode(rows, true))
            table.insert(per_folder_files, map_filename)
        end
        print(string.format("Wrote %d per-folder maps.", #per_folder_files))
        -- END NEW

        local summary = {
            total_assets = total,
            files_written = { basename(map_json) }
        }
        
        -- NEW: Add per-folder maps to summary
        for _, f in ipairs(per_folder_files) do
            table.insert(summary.files_written, f)
        end
        
        write_all_text(join(args.dst, "normalized_map_summary.json"), json_encode(summary, true))

        print("")
        print(string.format("Normalized %d assets.", total))
        print(string.format("JSON mapping written to: %s", map_json))
        print(string.format("Summary: %s", join(args.dst, "normalized_map_summary.json")))
    end)

    if prog then prog:Complete() end
    if not ok then error(err) end
end

-- run
main()