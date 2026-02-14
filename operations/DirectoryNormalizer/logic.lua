local logic = {}
local utils = {}

-- Constants -----------------------------------------------------------------

logic.segments_to_remove = {
    { "build", "ps3", "pal_en" },
    { "build", "ps3", "ntsc_en" }
}

logic.LevelAliasMap = {
    ["l01_landofchocolate"] = { "loc" },
    ["l02_bartmanbegins"] = { "brt" },
    ["l03_hungryhungryhomer"] = { "eighty_bites" },
    ["l04_treehugger"] = { "tree_hugger" },
    ["l05_mobrules"] = { "mob_rules" },
    ["l06_enterthecheatrix"] = { "cheater" },
    ["l07_dayofthedolphin"] = { "dayofthedolphins" },
    ["l08_thecolossaldonut"] = { "colossaldonut" },
    ["l09_invasion"] = { "dayspringfieldstoodstill" },
    ["l10_bargainbin"] = { "bargainbin" },
    ["l11_neverquest"] = { "neverquest" },
    ["l12_grandtheftscratchy"] = { "grand_theft_scratchy" },
    ["l13_medalofhomer"] = { "medal_of_homer" },
    ["l14_bigsuperhappy"] = { "bigsuperhappy" },
    ["l15_rhymes"] = { "rhymes" },
    ["l16_meetthyplayer"] = { "meetthyplayer" },
    ["lhub-00_gamehub"] = { "gamehub" },
    ["lhub-00_sprhub"] = { "spr_hub" },
    ["a2_frontend"] = { "frontend" },
    ["a2_characters"] = { "simpsons_chars" }
}

logic.IgnoredExtensions = {
    [".blend"] = true,
    [".blend1"] = true,
    [".preinstanced"] = true,
    [".dds"] = true,
    [".txd"] = true
}

-- Functions -----------------------------------------------------------------

function logic.init(util)
    utils = util
end

function logic.SplitTokens(segment)
    local tokens = {}
    for token in segment:gmatch("[^_]+") do
        table.insert(tokens, token)
    end
    return tokens
end

function logic.BuildAliasTokenSequences(level_folder_lower)
    local sequences = {}
    local aliases = logic.LevelAliasMap[level_folder_lower] or {}
    for _, alias in ipairs(aliases) do
        local alias_tokens = logic.SplitTokens(string.lower(alias))
        if #alias_tokens > 0 then
            table.insert(sequences, alias_tokens)
        end
    end
    table.sort(sequences, function(a, b) return #a > #b end)
    return sequences
end

function logic.MatchesSequence(tokens, index, sequence)
    if index + #sequence - 1 > #tokens then
        return false
    end
    for j = 1, #sequence do
        if string.lower(tokens[index + j - 1]) ~= sequence[j] then
            return false
        end
    end
    return true
end

function logic.GetZonePrefix(segment)
    if not segment then
        return nil
    end
    local lower = string.lower(segment)
    local zone_number = lower:match("^zone(%d+)_")
    if not zone_number then
        return nil
    end
    return "zone" .. zone_number
end

function logic.IsMatchingZoneAssets(parent_segment, child_segment)
    if not parent_segment or not child_segment then
        return false
    end
    local parent_zone = logic.GetZonePrefix(parent_segment)
    if not parent_zone then
        return false
    end
    local child_lower = string.lower(child_segment)
    return child_lower == ("assets_environs_" .. parent_zone)
end

function logic.IsMatchingZoneAssets2(parent_segment, child_segment)
    if not parent_segment or not child_segment then
        return false
    end
    local parent_zone = logic.GetZonePrefix(parent_segment)
    if not parent_zone then
        return false
    end
    local child_lower = string.lower(child_segment)
    return child_lower == ("environs_" .. parent_zone)
end

function logic.NormalizeFolderSegment(segment, alias_sequences)
    if not segment or segment == "" then
        return segment
    end

    local tokens = logic.SplitTokens(segment)
    if #tokens == 0 then
        return segment
    end

    local filtered = {}
    local i = 1
    while i <= #tokens do
        local matched_alias = false
        for _, sequence in ipairs(alias_sequences) do
            if logic.MatchesSequence(tokens, i, sequence) then
                i = i + #sequence
                matched_alias = true
                break
            end
        end
        if not matched_alias then
            table.insert(filtered, tokens[i])
            i = i + 1
        end
    end

    local collapsed = {}
    for j = 1, #filtered do
        local token = filtered[j]
        if #collapsed == 0 or string.lower(collapsed[#collapsed]) ~= string.lower(token) then
            table.insert(collapsed, token)
        end
    end

    if #collapsed == 0 then
        return ""
    end
    return table.concat(collapsed, "_")
end

function logic.NormalizeCollapsedDir(dir_path, level_folder_lower, level_name_lower)
    if not dir_path or dir_path == "" then
        return dir_path
    end

    local parts = utils.split_path(dir_path)
    if #parts == 0 then
        return dir_path
    end

    local alias_sequences = logic.BuildAliasTokenSequences(level_folder_lower)
    local new_parts = {}
    local i = 1
    while i <= #parts do
        local part = parts[i]
        local part_lower = string.lower(part)

        if i > 2 and part_lower == level_name_lower then
            -- Skip redundant level name
        else
            local skip_part = false
            if i > 2 and i < #parts then
                if part_lower == "challenge_mode" or part_lower == "story_mode" then
                    local next_part = parts[i + 1]
                    if next_part and string.lower(next_part):find("^" .. part_lower .. "_") then
                        skip_part = true
                    end
                end
            end

            if not skip_part then
                if i > 2 and #new_parts > 0 then
                    local parent_part = new_parts[#new_parts]
                    if logic.IsMatchingZoneAssets(parent_part, part) then
                        part = "assets_environs"
                    end
                    if logic.IsMatchingZoneAssets2(parent_part, part) then
                        part = "environs"
                    end
                end

                if i > 2 then
                    local normalized = logic.NormalizeFolderSegment(part, alias_sequences)
                    if normalized ~= "" then
                        part = normalized
                    else
                        part = nil
                    end
                end

                if part and part ~= "" then
                    table.insert(new_parts, part)
                end
            end
        end
        i = i + 1
    end

    if #new_parts == 0 then
        return ""
    end
    return table.concat(new_parts, utils.path_sep)
end

function logic.apply_file_rules(original_rel, uid_generator_func, rename_map)
    local parts = utils.split_path(original_rel)
    if #parts == 0 then return original_rel, "000000" end

    local level_name_lower = ""
    if #parts >= 2 then
        level_name_lower = string.lower(parts[2])
    end

    local level_folder_lower = ""
    if #parts >= 1 then
        level_folder_lower = string.lower(parts[1])
    end

    local alias_sequences = logic.BuildAliasTokenSequences(level_folder_lower)

    local new_parts = {}
    local i = 1
    while i <= #parts do
        local part = parts[i]
        local part_lower = string.lower(part)
        local matched_segment = false

        for _, segment in ipairs(logic.segments_to_remove) do
            if part_lower == segment[1] and i + #segment - 1 <= #parts then
                local match = true
                for j = 1, #segment do
                    if string.lower(parts[i + j - 1]) ~= segment[j] then
                        match = false
                        break
                    end
                end

                if match then
                    i = i + #segment
                    matched_segment = true
                    break
                end
            end
        end

        if not matched_segment then
            if i > 2 and part_lower == level_name_lower then
            else
                local skip_part = false
                if i > 2 and i < #parts then
                    if part_lower == "challenge_mode" or part_lower == "story_mode" then
                        local next_part = parts[i + 1]
                        if next_part and string.lower(next_part):find("^" .. part_lower .. "_") then
                            skip_part = true
                        end
                    end
                end

                if not skip_part then
                    if part_lower == "texture_dictionary" then
                        part = "txd"
                    end
                    if i > 2 and #new_parts > 0 then
                        local parent_part = new_parts[#new_parts]
                        if logic.IsMatchingZoneAssets(parent_part, part) then
                            part = "assets_environs"
                        end
                    end
                    if i > 2 and i < #parts then
                        local normalized = logic.NormalizeFolderSegment(part, alias_sequences)
                        if normalized ~= "" then
                            part = normalized
                        else
                            part = nil
                        end
                    end
                    if part and part ~= "" then
                        table.insert(new_parts, part)
                    end
                end
            end
            i = i + 1
        end
    end

    if #new_parts == 0 then return original_rel, "000000" end

    local filename = table.remove(new_parts)
    local new_dir = table.concat(new_parts, utils.path_sep)

    local canonical_rel = logic.normalize_to_canonical(original_rel, rename_map)
    local canonical_rel_stem, _ = utils.multi_ext(canonical_rel)
    local uid = uid_generator_func(canonical_rel_stem, 6)

    local base, rest = filename:match("^(.-)%.(.*)$")
    local new_filename
    if base then
        new_filename = string.format("%s_%s.%s", base, uid, rest)
    else
        new_filename = string.format("%s_%s", filename, uid)
    end

    local new_rel_path = utils.join(new_dir, new_filename)
    return new_rel_path, uid
end

function logic.add_to_tree(tree, path_str)
    local parts = utils.split_path(path_str)
    local filename = table.remove(parts)
    local current_path = ""
    local t = tree[""]

    for i=1, #parts do
        local part = parts[i]
        t.dirs[part] = true

        local child_path = utils.join(current_path, part)
        if not tree[child_path] then
            tree[child_path] = { dirs={}, files={} }
        end
        t = tree[child_path]
        current_path = child_path
    end

    if filename and filename ~= "" then
        t.files[filename] = true
    end
end

function logic.build_collapse_map(tree, map, current_orig_path, current_new_path)
    local node = tree[current_orig_path]
    if not node then return end

    local dir_names = {}
    for k,_ in pairs(node.dirs) do table.insert(dir_names, k) end
    local file_names = {}
    for k,_ in pairs(node.files) do table.insert(file_names, k) end

    if #dir_names == 1 and #file_names == 0 then
        local child_name = dir_names[1]
        local child_orig_path = utils.join(current_orig_path, child_name)

        local new_basename = utils.basename(current_new_path)
        if current_orig_path == "" then
            new_basename = child_name
        elseif new_basename == "" then
            new_basename = utils.basename(current_orig_path)
        end

        local new_collapsed_name = new_basename .. "_" .. child_name
        local new_collapsed_path = utils.join(utils.dirname(current_new_path), new_collapsed_name)

        logic.build_collapse_map(tree, map, child_orig_path, new_collapsed_path)
    else
        map[current_orig_path] = current_new_path
        for _, name in ipairs(dir_names) do
            local child_orig = utils.join(current_orig_path, name)
            local child_new = utils.join(current_new_path, name)
            logic.build_collapse_map(tree, map, child_orig, child_new)
        end
    end
end

function logic.load_rename_map(db_path)
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

function logic.normalize_to_canonical(rel_path, rename_map)
    if not rename_map or not rel_path then
        return rel_path
    end
    local parts = utils.split_path(rel_path)
    if #parts == 0 then
        return rel_path
    end
    local base_folder = parts[1]
    local base_folder_lower = string.lower(base_folder)
    if rename_map[base_folder_lower] then
        parts[1] = rename_map[base_folder_lower]
    end
    return table.concat(parts, "/")
end

function logic.walk_files(root, ignore_list)
    local stack = { root }
    local files = {}
    while #stack > 0 do
        local dir = table.remove(stack)
        local entries = sdk.list_dir(dir)
        for i = 1, #entries do
            local entry = entries[i]
            local p = utils.join(dir, entry)
            local attr = sdk.attributes(p)
            if attr and attr.mode == "directory" then
                if not utils.should_ignore_dir(entry, ignore_list) then
                    table.insert(stack, p)
                end
            else
                local ext = utils.ext_lower(entry)
                if not logic.IgnoredExtensions[ext] then
                    table.insert(files, p)
                end
            end
        end
    end
    return files
end

function logic.BuildCopyOnlySet(copyonly_list)
    local Set = {}
    for _, entry in ipairs(copyonly_list or {}) do
        local Name = entry or ""
        if Name ~= "" then
            Set[string.lower(Name)] = true
        end
    end
    return Set
end

function logic.IsCopyOnlyPath(rel_path, copyonly_set)
    if not rel_path or not copyonly_set then
        return false
    end
    local parts = utils.split_path(rel_path)
    if #parts == 0 then
        return false
    end
    return copyonly_set[string.lower(parts[1])] == true
end

return logic
