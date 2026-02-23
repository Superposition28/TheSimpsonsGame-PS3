local M = {}

function M.setup(Utils)
    local lib = {}

    function lib.extract_map_subdirectory(full_path, marker, verbose)
        local normalized_path = Utils.normalize_separators(full_path or "")
        local normalized_marker = Utils.normalize_separators(marker or "")

        if normalized_marker == "" then
            Utils.log(Utils.Colours.YELLOW, string.format("Warning: Marker is not provided. Cannot extract map subdirectory from path: %s. Returning _UNKNOWN_MAP_NO_MARKER.", normalized_path))
            return "_UNKNOWN_MAP_NO_MARKER"
        end

        local lower_path = normalized_path:lower()
        local lower_marker = normalized_marker:lower()
        local idx = lower_path:find(lower_marker, 1, true)

        if not idx then
            Utils.log(Utils.Colours.YELLOW, string.format("Warning: Marker '%s' was not found in path: %s. Returning _UNKNOWN_MAP_NOT_FOUND.", normalized_marker, normalized_path))
            return "_UNKNOWN_MAP_NOT_FOUND"
        end

        local start_of_remainder = idx + #normalized_marker
        local remaining = normalized_path:sub(start_of_remainder)
        remaining = remaining:gsub("^[" .. Utils.path_sep .. "]+", "")

        if remaining == "" then
            Utils.log(Utils.Colours.CYAN, string.format("Info: Marker '%s' found in '%s', but path ends with marker or only separators follow. Returning _NO_SUBDIR_AFTER_MARKER.", normalized_marker, normalized_path))
            return "_NO_SUBDIR_AFTER_MARKER"
        end

        local parts = {}
        for component in remaining:gmatch("[^" .. Utils.path_sep .. "]+") do
            table.insert(parts, component)
        end

        if #parts == 0 then
            Utils.log(Utils.Colours.YELLOW, string.format("Warning: Marker '%s' found in '%s', but could not isolate a subdirectory. Returning _NO_SUBDIR_PARTS_FOUND.", normalized_marker, normalized_path))
            return "_NO_SUBDIR_PARTS_FOUND"
        end

        local subdir = parts[1]
        if verbose then
            Utils.log(Utils.Colours.GREEN, string.format("Success: Marker '%s', Path '%s', Subdir Part '%s'", normalized_marker, normalized_path, subdir))
        end
        return subdir
    end

    function lib.init_db(db_file_path)
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

    function lib.generate_asset_mapping(db, root_drive, preinstanced_root, blend_root, marker, glb_root, check_existence, verbose, game_root)
        check_existence = not not check_existence

        if not sdk.is_dir(preinstanced_root) then
            error(string.format("Preinstanced root directory not found: %s", preinstanced_root))
        end
        if not sdk.is_dir(blend_root) then
            error(string.format("Blend root directory not found: %s", blend_root))
        end
        if glb_root and not sdk.is_dir(glb_root) then
            Utils.log(Utils.Colours.CYAN, string.format("GLB root directory %s not found, creating it.", glb_root))
            sdk.ensure_dir(glb_root)
        end

        local assets_processed = 0
        local preinstanced_root_abs = Utils.absolute_path(preinstanced_root)
        local blend_root_abs = Utils.absolute_path(blend_root)
        local glb_root_abs = glb_root and Utils.absolute_path(glb_root) or nil

        -- If game_root is provided, we use it as the base for canonical IDs to match the Normalizer's view
        local canonical_base = game_root and Utils.absolute_path(game_root) or preinstanced_root_abs

        db.begin()

        local map_file_path = Utils.join(preinstanced_root_abs, "normalized_map.json")
        if sdk.is_file(map_file_path) then
            Utils.log(Utils.Colours.CYAN, string.format("Using normalized_map.json from %s", preinstanced_root_abs))
            local fh = io.open(map_file_path, "r")
            if fh then
                local map_content = fh:read("*a")
                fh:close()
                local map_data = sdk.text.json.decode(map_content)
                if map_data then
                    for _, entry in ipairs(map_data) do
                        local new_path = entry.new_path
                        if new_path and Utils.ends_with(new_path:lower(), ".preinstanced") then
                            local full_path = Utils.join(preinstanced_root_abs, new_path)

                            -- Extract filename from new_path
                            local filename = new_path
                            local last_sep = 0
                            for i = 1, #new_path do
                                local ch = new_path:sub(i,i)
                                if ch == '/' or ch == '\\' then last_sep = i end
                            end
                            if last_sep > 0 then
                                filename = new_path:sub(last_sep + 1)
                            end

                            local rel = Utils.normalize_separators(full_path):sub(#preinstanced_root_abs + 2)
                            local canonical_rel = Utils.normalize_separators(full_path):sub(#canonical_base + 2)

                            local blend_rel = rel:gsub("%.preinstanced$", ".blend")
                            local blend_full = Utils.join(blend_root_abs, blend_rel)

                            local glb_full = nil
                            if glb_root_abs then
                                local glb_rel = rel:gsub("%.preinstanced$", ".glb")
                                glb_full = Utils.join(glb_root_abs, glb_rel)
                            end

                            if check_existence and (not sdk.is_file(blend_full)) then
                                Utils.log(Utils.Colours.YELLOW, string.format("Warning: Corresponding blend file not found: %s", blend_full))
                            else
                                local map_subdir = lib.extract_map_subdirectory(full_path, marker, verbose)
                                if verbose then
                                    Utils.log(Utils.Colours.CYAN, string.format("Extracted Map Subdirectory: '%s' for %s", map_subdir, full_path))
                                end

                                local symlink_rel = ""
                                if rel:sub(1, #map_subdir) == map_subdir then
                                    symlink_rel = rel:sub(#map_subdir + 2)
                                end

                                local identifier = entry.uid or Utils.get_canonical_id(canonical_rel)
                                local base_filename = filename:gsub("%.preinstanced$", "")

                                local shared_symlink_root = Utils.join(root_drive, identifier)

                                local params = {
                                    identifier = identifier,
                                    map_subdirectory = map_subdir,
                                    filename = base_filename,
                                    preinstanced_full = full_path,
                                    blend_full = blend_full,
                                    glb_full = glb_full,
                                    preinstanced_symlink = shared_symlink_root,
                                    blend_symlink = shared_symlink_root,
                                    glb_symlink = glb_full and shared_symlink_root or nil
                                }

                                db.exec([[INSERT OR REPLACE INTO asset_map (
                                        identifier, map_subdirectory, filename, preinstanced_full, blend_full, glb_full,
                                        preinstanced_symlink, blend_symlink, glb_symlink)
                                        VALUES (:identifier, :map_subdirectory, :filename, :preinstanced_full, :blend_full, :glb_full,
                                        :preinstanced_symlink, :blend_symlink, :glb_symlink)
                                    ]], params)
                                assets_processed = assets_processed + 1
                            end
                        end
                    end
                end
            end
        else
            Utils.iterate_files(preinstanced_root_abs, function(full_path, filename)
                local lower_name = filename:lower()
                if not Utils.ends_with(lower_name, ".preinstanced") then
                    return
                end

                local rel = Utils.normalize_separators(full_path):sub(#preinstanced_root_abs + 2)
                local canonical_rel = Utils.normalize_separators(full_path):sub(#canonical_base + 2)

                local blend_rel = rel:gsub("%.preinstanced$", ".blend")
                local blend_full = Utils.join(blend_root_abs, blend_rel)

                local glb_full = nil
                if glb_root_abs then
                    local glb_rel = rel:gsub("%.preinstanced$", ".glb")
                    glb_full = Utils.join(glb_root_abs, glb_rel)
                end

                if check_existence and (not sdk.is_file(blend_full)) then
                    Utils.log(Utils.Colours.YELLOW, string.format("Warning: Corresponding blend file not found: %s", blend_full))
                    return
                end

                local map_subdir = lib.extract_map_subdirectory(full_path, marker, verbose)
                if verbose then
                    Utils.log(Utils.Colours.CYAN, string.format("Extracted Map Subdirectory: '%s' for %s", map_subdir, full_path))
                end

                -- The symlink relative path preserves the structure after the map_subdirectory
                -- rel is props\env\bin.preinstanced, map_subdir is props
                -- symlink_rel should be env\bin.preinstanced
                local symlink_rel = ""
                if rel:sub(1, #map_subdir) == map_subdir then
                    symlink_rel = rel:sub(#map_subdir + 2)
                end

                local identifier = Utils.get_canonical_id(canonical_rel)
                local base_filename = filename:gsub("%.preinstanced$", "")

                -- Use a single shared symlink folder per asset ID on the root drive
                local shared_symlink_root = Utils.join(root_drive, identifier)

                local params = {
                    identifier = identifier,
                    map_subdirectory = map_subdir,
                    filename = base_filename,
                    preinstanced_full = full_path,
                    blend_full = blend_full,
                    glb_full = glb_full,
                    preinstanced_symlink = shared_symlink_root,
                    blend_symlink = shared_symlink_root,
                    glb_symlink = glb_full and shared_symlink_root or nil
                }

                db.exec([[INSERT OR REPLACE INTO asset_map (
                        identifier, map_subdirectory, filename, preinstanced_full, blend_full, glb_full,
                        preinstanced_symlink, blend_symlink, glb_symlink)
                        VALUES (:identifier, :map_subdirectory, :filename, :preinstanced_full, :blend_full, :glb_full,
                        :preinstanced_symlink, :blend_symlink, :glb_symlink)
                    ]], params)
                assets_processed = assets_processed + 1
            end)
        end
        db.commit()

        return assets_processed
    end

    return lib
end

return M
