
---@class DirectoryNormalizerLogic
---@field segments_to_remove string[][]
---@field LevelAliasMap table<string, string[]>
---@field EpisodeMap table<string, string[][]>
---@field IgnoredExtensions table<string, boolean>
---@field init fun(util: table)
---@field to_camel_case fun(str: string): string
---@field simplify_episode_names fun(rel_path: string): string
---@field apply_camel_case_to_path fun(rel_path: string): string
---@field SplitTokens fun(segment: string): string[]
---@field BuildAliasTokenSequences fun(level_folder_lower: string): string[][]
---@field MatchesSequence fun(tokens: string[], index: integer, sequence: string[]): boolean
---@field GetZonePrefix fun(segment: string): string|nil
---@field IsMatchingZoneAssets fun(parent_segment: string, child_segment: string): boolean
---@field IsMatchingZoneAssets2 fun(parent_segment: string, child_segment: string): boolean
---@field NormalizeFolderSegment fun(segment: string, alias_sequences: string[][]): string
---@field NormalizeCollapsedDir fun(dir_path: string, level_folder_lower: string, level_name_lower: string): string
---@field apply_file_rules fun(original_rel: string, process_rel: string, uid_generator_func: function, rename_map: table<string, string>): string, string
---@field ExtractAudioUidFromFilename fun(filename: string): string|nil
---@field GetCopyOnlyUid fun(rel_path: string, uid_generator_func: function, rename_map: table<string, string>): string
---@field add_to_tree fun(tree: table, path_str: string)
---@field build_collapse_map fun(tree: table, map: table<string, string>, current_orig_path: string, current_new_path: string)
---@field load_rename_map fun(db_path: string): table<string, string>
---@field normalize_to_canonical fun(rel_path: string, rename_map: table<string, string>): string
---@field walk_files fun(root: string, ignore_list: table): string[]
---@field BuildCopyOnlySet fun(copyonly_list: string[]): table<string, boolean>
---@field IsCopyOnlyPath fun(rel_path: string, copyonly_set: table<string, boolean>): boolean



local logic = {}
local utils = {}

-- Constants -----------------------------------------------------------------

logic.segments_to_remove = {
    { "build", "ps3", "palen" },
    { "build", "ps3", "ntscen" }
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
    ["l09_invasion"] = { "dayspringfieldstoodstill", "springfield_stood_still", "sss", "sssinvasion" },
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

logic.EpisodeMap = {
    ["loc"] = { {"land", "of", "chocolate"}, {"landofchocolate"}, {"loc"} },
    ["brt"] = { {"bartman", "begins"}, {"bartmanbegins"}, {"brt"} },
    ["80b"] = { {"around", "the", "world", "in", "80", "bites"}, {"eighty", "bites"}, {"80b"}, {"80bites"} },
    ["hug"] = { {"lisa", "the", "tree", "hugger"}, {"tree", "hugger"}, {"treehugger"}, {"hug"} },
    ["mob"] = { {"mob", "rules"}, {"mobrules"}, {"mob"} },
    ["che"] = { {"enter", "the", "cheatrix"}, {"cheatrix"}, {"cheater"}, {"che"} },
    ["dod"] = { {"day", "of", "the", "dolphin"}, {"day", "of", "dolphin"}, {"dayofthedolphins"}, {"dod"} },
    ["scd"] = { {"shadow", "of", "the", "colossal", "donut"}, {"colossal", "donut"}, {"colossaldonut"}, {"scd"} },
    ["sss"] = { {"invasion", "of", "the", "yokel", "snatchers"}, {"day", "springfield", "stood", "still"}, {"dayspringfieldstoodstill"}, {"sss"} },
    ["gamehub"] = { {"bargain", "bin"}, {"bargainbin"}, {"gamehub"} },
    ["nvq"] = { {"neverquest"}, {"nvq"} },
    ["gts"] = { {"grand", "theft", "scratchy"}, {"grandtheftscratchy"}, {"gts"} },
    ["moh"] = { {"medal", "of", "homer"}, {"medalofhomer"}, {"moh"} },
    ["bsh"] = { {"big", "super", "happy", "fun", "fun", "game"}, {"big", "super", "happy"}, {"bigsuperhappy"}, {"bsh"} },
    ["rwc"] = { {"five", "characters", "in", "search", "of", "an", "author"}, {"rhymes"}, {"rwc"} },
    ["mtp"] = { {"game", "over"}, {"meet", "thy", "player"}, {"meetthyplayer"}, {"mtp"} }
}

logic.IgnoredExtensions = {
    [".blend"] = true,
    [".blend1"] = true
}

-- Functions -----------------------------------------------------------------

function logic.init(util)
    utils = util
end

function logic.to_camel_case(str)
    if not str or not string.find(str, "_") then return str end
    local parts = {}
    for token in string.gmatch(str, "[^_]+") do
        table.insert(parts, token)
    end
    if #parts == 0 then return str end
    local res = string.lower(parts[1])
    for i = 2, #parts do
        local t = string.lower(parts[i])
        res = res .. string.upper(string.sub(t, 1, 1)) .. string.sub(t, 2)
    end
    return res
end

function logic.simplify_episode_names(rel_path)
    local parts = utils.split_path(rel_path)
    if #parts <= 1 then return rel_path end

    local root_lower = string.lower(parts[1])
    if not (root_lower:match("^a2_") or root_lower:match("^lhub%-")) then
        return rel_path
    end

    local seen_episodes = {}

    for i = 2, #parts - 1 do
        local part = parts[i]
        local tokens = logic.SplitTokens(part)

        local new_tokens = {}
        local t_idx = 1
        while t_idx <= #tokens do
            local matched_shortcode = nil
            local matched_len = 0

            for shortcode, sequences in pairs(logic.EpisodeMap) do
                for _, seq in ipairs(sequences) do
                    if logic.MatchesSequence(tokens, t_idx, seq) then
                        if #seq > matched_len then
                            matched_len = #seq
                            matched_shortcode = shortcode
                        end
                    end
                end
            end

            if matched_shortcode then
                if not seen_episodes[matched_shortcode] then
                    table.insert(new_tokens, matched_shortcode)
                    seen_episodes[matched_shortcode] = true
                end
                t_idx = t_idx + matched_len
            else
                table.insert(new_tokens, tokens[t_idx])
                t_idx = t_idx + 1
            end
        end

        if #new_tokens == 0 and #tokens > 0 then
            local fallback_tokens = {}
            local f_idx = 1
            while f_idx <= #tokens do
                local matched_shortcode = nil
                local matched_len = 0
                for shortcode, sequences in pairs(logic.EpisodeMap) do
                    for _, seq in ipairs(sequences) do
                        if logic.MatchesSequence(tokens, f_idx, seq) then
                            if #seq > matched_len then
                                matched_len = #seq
                                matched_shortcode = shortcode
                            end
                        end
                    end
                end
                if matched_shortcode then
                    table.insert(fallback_tokens, matched_shortcode)
                    f_idx = f_idx + matched_len
                else
                    table.insert(fallback_tokens, tokens[f_idx])
                    f_idx = f_idx + 1
                end
            end
            new_tokens = fallback_tokens
        end

        parts[i] = table.concat(new_tokens, "_")
    end

    return table.concat(parts, utils.path_sep)
end

function logic.apply_camel_case_to_path(rel_path)
    rel_path = logic.simplify_episode_names(rel_path)

    local parts = utils.split_path(rel_path)
    -- Don't process paths that are just root or root/file
    if #parts <= 1 then return rel_path end

    -- Explicit override: rename L09_Invasion primary level folder before camelCase
    if #parts >= 2 and string.lower(parts[1]) == "l09_invasion" and string.lower(parts[2]) == "dayspringfieldstoodstill" then
        parts[2] = "sss_invasion"
    end

    -- Exclude parts[1] (root folder) and parts[#parts] (file name)
    for i = 2, #parts - 1 do
        parts[i] = logic.to_camel_case(parts[i])
    end

    return table.concat(parts, utils.path_sep)
end

function logic.SplitTokens(segment)
    local tokens = {}
    -- Convert camelCase boundaries to underscores temporarily so gmatch still works
    local s = segment:gsub("([a-z])([A-Z])", "%1_%2")
    for token in s:gmatch("[^_]+") do
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
    local zone_number = lower:match("^zone(%d+)")
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
    return child_lower == ("assetsenvirons" .. parent_zone)
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
    return child_lower == ("environs" .. parent_zone)
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

    -- Recombine the tokens using camelCase instead of underscores
    local res = string.lower(collapsed[1])
    for j = 2, #collapsed do
        local t = string.lower(collapsed[j])
        res = res .. string.upper(string.sub(t, 1, 1)) .. string.sub(t, 2)
    end
    return res
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
                if part_lower == "challengemode" or part_lower == "storymode" then
                    local next_part = parts[i + 1]
                    if next_part and string.lower(next_part):find("^" .. part_lower) then
                        skip_part = true
                    end
                end
            end

            if not skip_part then
                if i > 2 and #new_parts > 0 then
                    local parent_part = new_parts[#new_parts]
                    if logic.IsMatchingZoneAssets(parent_part, part) then
                        part = "assetsEnvirons"
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

function logic.apply_file_rules(original_rel, process_rel, uid_generator_func, rename_map)
    local parts = utils.split_path(process_rel)
    if #parts == 0 then return process_rel, "000000" end

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
                    if part_lower == "challengemode" or part_lower == "storymode" then
                        local next_part = parts[i + 1]
                        if next_part and string.lower(next_part):find("^" .. part_lower) then
                            skip_part = true
                        end
                    end
                end

                if not skip_part then
                    if part_lower == "texturedictionary" then
                        part = "txd"
                    end
                    if i > 2 and #new_parts > 0 then
                        local parent_part = new_parts[#new_parts]
                        if logic.IsMatchingZoneAssets(parent_part, part) then
                            part = "assetsEnvirons"
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

    if #new_parts == 0 then return process_rel, "000000" end

    local filename = table.remove(new_parts)
    local new_dir = table.concat(new_parts, utils.path_sep)

    -- Use original_rel for stable UID generation regardless of camelCase
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

    local new_rel_path = join(new_dir, new_filename)
    return new_rel_path, uid
end

function logic.ExtractAudioUidFromFilename(filename)
    if not filename or filename == "" then
        return nil
    end
    local lower = string.lower(filename)
    if not lower:match("%.exa%.wav$") then
        return nil
    end
    local stem = filename:sub(1, #filename - #".exa.wav")
    if #stem < 6 then
        return nil
    end
    local uid = stem:sub(#stem - 5)
    if uid:match("^[%x]+$") then
        return string.lower(uid)
    end
    return nil
end

function logic.GetCopyOnlyUid(rel_path, uid_generator_func, rename_map)
    local filename = utils.basename(rel_path or "")
    local audio_uid = logic.ExtractAudioUidFromFilename(filename)
    if audio_uid then
        return audio_uid
    end

    local canonical_rel = logic.normalize_to_canonical(rel_path, rename_map)
    local canonical_rel_stem, _ = utils.multi_ext(canonical_rel)
    return uid_generator_func(canonical_rel_stem, 6)
end

function logic.add_to_tree(tree, path_str)
    local parts = utils.split_path(path_str)
    local filename = table.remove(parts)
    local current_path = ""
    local t = tree[""]

    for i=1, #parts do
        local part = parts[i]
        t.dirs[part] = true

        local child_path = join(current_path, part)
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
        local child_orig_path = join(current_orig_path, child_name)

        local new_basename = utils.basename(current_new_path)
        if current_orig_path == "" then
            new_basename = child_name
        elseif new_basename == "" then
            new_basename = utils.basename(current_orig_path)
        end

        -- Capitalize the first letter of the child folder to merge in camelCase
        local capitalized_child = string.upper(string.sub(child_name, 1, 1)) .. string.sub(child_name, 2)
        local new_collapsed_name = new_basename .. capitalized_child

        local new_collapsed_path = join(utils.dirname(current_new_path), new_collapsed_name)

        logic.build_collapse_map(tree, map, child_orig_path, new_collapsed_path)
    else
        map[current_orig_path] = current_new_path
        for _, name in ipairs(dir_names) do
            local child_orig = join(current_orig_path, name)
            local child_new = join(current_new_path, name)
            logic.build_collapse_map(tree, map, child_orig, child_new)
        end
    end
end

function logic.load_rename_map(db_path)
    local map = {}
    if not sdk.path_exists(db_path) then
        return map
    end
    local db = sqlite.open(db_path)
    if not db then
        return map
    end
    local prog = progress.console.new(0, "RenameMap", "Loading rename mappings...")
    local ok, rows = pcall(function()
        return db:query("SELECT old_name, new_name FROM rename_mappings")
    end)
    if ok and rows then
        prog:SetTotal(#rows)
        for i, row in ipairs(rows) do
            local old_name = row.old_name
            local new_name = row.new_name
            if old_name and new_name then
                map[string.lower(new_name)] = old_name
            end
            prog:SetLabel("Loaded " .. i .. " mappings")
            prog:Update(1, 1, 0, 0)
        end
    end
    db:close()
    prog:Complete()
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

    -- Start with 1 total directory (the root)
    local total_dirs = 1

    -- Passing an ID and a Label to the progress bar
    local prog = progress.console.new(total_dirs, "WalkFiles", "Scanning directory...")

    while #stack > 0 do
        local dir = table.remove(stack)

        -- Update the progress bar label instead of spamming the console
        prog:SetLabel("Scanning: " .. dir)
        -- Increment the progress for each directory we process
        prog:Update(1, 1, 0, 0)

        local entries = sdk.list_dir(dir)
        for i = 1, #entries do
            local entry = entries[i]
            local p = join(dir, entry)
            local attr = sdk.attributes(p)

            if attr and attr.mode == "directory" then
                if not utils.should_ignore_dir(entry, ignore_list) then
                    table.insert(stack, p)

                    -- We discovered a new directory: expand the progress bar's Total
                    total_dirs = total_dirs + 1
                    prog:SetTotal(total_dirs)
                end
            else
                local ext = utils.ext_lower(entry)
                if not logic.IgnoredExtensions[ext] then
                    table.insert(files, p)
                end
            end
        end
    end

    prog:SetLabel("Finished Scanning.")
    prog:Complete()

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
