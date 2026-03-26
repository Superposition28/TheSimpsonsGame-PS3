--[[
SetupAudioDir.lua

Purpose:
- Prepare the audio source directory by grouping subfolders into 'EN' and 'Global'.
- Skips language-specific folders in a blacklist.

Runtime guarantees: sdk, argv are provided by engine
]]

local Utils = import("SharedUtils")

-- Hardcoded Language Blacklist and Global Dirs (mirrors Python script)
local language_blacklist = { it=true, es=true, fr=true }
local language_dirs_to_process = { "en", "es", "fr", "it" }
local global_dirs = {
	["80b_crow"]=true, ["amb_airc"]=true, ["amb_chao"]=true, ["amb_cour"]=true, ["amb_dung"]=true, ["amb_ext_"]=true,
	["amb_fore"]=true, ["amb_fren"]=true, ["amb_gara"]=true, ["amb_int_"]=true, ["amb_mans"]=true, ["amb_nort"]=true,
	["amb_riot"]=true, ["amb_shir"]=true, ["amb_vent"]=true, ["bin_rev0"]=true, ["brt_dino"]=true, ["brt_dior"]=true,
	["brt_myst"]=true, ["brt_plan"]=true, ["brt_temp"]=true, ["bsh_air_"]=true, ["bsh_beac"]=true, ["bsh_figh"]=true,
	["bsh_fire"]=true, ["bsh_ice_"]=true, ["bsh_vill"]=true, ["bsh__air"]=true, ["che_cart"]=true, ["che_cent"]=true,
	["che_mark"]=true, ["che_mo_b"]=true, ["che_q_an"]=true, ["dod_aqua"]=true, ["dod_dock"]=true, ["gamehub_"]=true,
	["gts_full"]=true, ["gts_seas"]=true, ["gts_stat"]=true, ["gts_subu"]=true, ["gts_vent"]=true, ["gts_viol"]=true,
	["mtp_heav"]=true, ["mus_simp"]=true, ["sss_cont"]=true, ["sss_lab_"]=true, ["sss_mall"]=true
}

local function lower(s)
	return s and string.lower(s) or s
end

local function trim(s)
	return Utils.trim(s or "") or ""
end

local function strip_xxx_suffix(name)
	local value = trim(name)
	if value == "" then
		return value
	end
	if lower(value):match("_xxx_0$") then
		return value:sub(1, #value - 6)
	end
	return value
end

local function is_placeholder_character_name(name)
	local value = lower(trim(name))
	if value == "" then
		return true
	end
	if value == "unknown" then
		return true
	end
	if value == "tbd" then
		return true
	end
	if value == "tba" then
		return true
	end
	return false
end

local function sanitize_character_prefix(name)
	local value = trim(name)
	if value == "" then
		return value
	end
	-- Keep readable names but remove filesystem-invalid characters.
	value = value:gsub("[\\/:%*%?\"<>|]", "_")
	value = value:gsub("%s+", " ")
	value = trim(value)
	return value
end

local function build_file_match_pattern(file_pattern)
	local raw = trim(file_pattern)
	if raw == "" then
		return nil
	end

	local placeholder = "__HEX7__"
	local escaped = raw:gsub("#######", placeholder)
	escaped = escaped:gsub("([%^%$%(%)%%%.%[%]%*%+%-%?])", "%%%1")
	escaped = escaped:gsub(placeholder, "[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]")
	return "^" .. escaped .. "$"
end

local function extract_file_patterns(file_entry)
	local results = {}
	local file_patterns = file_entry and file_entry.file_patterns
	if type(file_patterns) ~= "table" then
		return results
	end

	if type(file_patterns.file_pattern) == "string" then
		table.insert(results, file_patterns.file_pattern)
	end

	for _, pattern_entry in ipairs(file_patterns) do
		if type(pattern_entry) == "table" and type(pattern_entry.file_pattern) == "string" then
			table.insert(results, pattern_entry.file_pattern)
		end
	end

	return results
end

local function find_section_entries(node, section_name, collector)
	if type(node) ~= "table" then
		return
	end

	local section = node[section_name]
	if type(section) == "table" then
		for _, entry in ipairs(section) do
			if type(entry) == "table" and type(entry.OLD_DIR_NAME) == "string" then
				table.insert(collector, entry)
			end
		end
	end

	for _, value in pairs(node) do
		if type(value) == "table" then
			find_section_entries(value, section_name, collector)
		end
	end
end

local function build_rules_from_entries(entries)
	local rules_by_old_name = {}
	local skipped_characters = 0

	for _, entry in ipairs(entries) do
		local old_name = trim(entry.OLD_DIR_NAME)
		if old_name ~= "" then
			local new_name = trim(entry.NEW_DIR_NAME)
			if new_name == "" or lower(new_name) == "tbd" then
				new_name = strip_xxx_suffix(old_name)
			end

			local rule = {
				OldDirName = old_name,
				NewDirName = new_name,
				FileRules = {}
			}

			if type(entry.files) == "table" then
				for _, file_entry in ipairs(entry.files) do
					if type(file_entry) == "table" then
						local character_name = trim(file_entry.CharacterName)
						if is_placeholder_character_name(character_name) then
							skipped_characters = skipped_characters + 1
						else
							local safe_prefix = sanitize_character_prefix(character_name)
							if safe_prefix ~= "" then
								local patterns = extract_file_patterns(file_entry)
								for _, file_pattern in ipairs(patterns) do
									local match_pattern = build_file_match_pattern(file_pattern)
									if match_pattern then
										table.insert(rule.FileRules, {
											CharacterPrefix = safe_prefix,
											MatchPattern = match_pattern
										})
									end
								end
							end
						end
					end
				end
			end

			rules_by_old_name[lower(old_name)] = rule
		end
	end

	return rules_by_old_name, skipped_characters
end

local function load_audio_map_rules(audio_map_path)
	local parsed = nil
	if sdk.text and sdk.text.yaml and sdk.text.yaml.read_file then
		parsed = sdk.text.yaml.read_file(audio_map_path)
	elseif sdk.yaml_read_file then
		parsed = sdk.yaml_read_file(audio_map_path)
	end

	if not parsed then
		return nil, "Unable to parse AudioMap.yaml"
	end

	local section_entries = {
		["EN-Dialogue"] = {},
		["EN-CUTSCENE"] = {},
		["Global-Sound"] = {}
	}

	for section_name, entries in pairs(section_entries) do
		find_section_entries(parsed, section_name, entries)
	end

	local en_dialogue_rules, en_dialogue_skipped = build_rules_from_entries(section_entries["EN-Dialogue"])
	local en_cutscene_rules, en_cutscene_skipped = build_rules_from_entries(section_entries["EN-CUTSCENE"])
	local global_sound_rules, global_sound_skipped = build_rules_from_entries(section_entries["Global-Sound"])

	if next(en_dialogue_rules) == nil and next(en_cutscene_rules) == nil and next(global_sound_rules) == nil then
		return nil, "No EN-Dialogue/EN-CUTSCENE/Global-Sound entries found in AudioMap.yaml"
	end

	return {
		ENDialogueRules = en_dialogue_rules,
		ENCutsceneRules = en_cutscene_rules,
		GlobalSoundRules = global_sound_rules,
		SkippedCharacters = en_dialogue_skipped + en_cutscene_skipped + global_sound_skipped,
		SectionCounts = {
			ENDialogue = #section_entries["EN-Dialogue"],
			ENCutscene = #section_entries["EN-CUTSCENE"],
			GlobalSound = #section_entries["Global-Sound"]
		}
	}, nil
end

local function resolve_language_dirs(root_dir)
	local resolved = {}
	for _, name in ipairs(sdk.list_dir(root_dir)) do
		local candidate = Utils.join(root_dir, name)
		if sdk.is_dir(candidate) then
			local lname = lower(name)
			if lname == "en" or lname == "es" or lname == "fr" or lname == "it" then
				resolved[lname] = candidate
			end
		end
	end
	return resolved
end

local function apply_file_rename_rules(rule, folder_path, stats)
	if type(rule.FileRules) ~= "table" or #rule.FileRules == 0 then
		return
	end

	for _, file_name in ipairs(sdk.list_dir(folder_path)) do
		local file_path = Utils.join(folder_path, file_name)
		if sdk.is_file(file_path) then
			local matched_prefix = nil
			local ambiguous = false

			for _, file_rule in ipairs(rule.FileRules) do
				if string.match(file_name, file_rule.MatchPattern) then
					if not matched_prefix then
						matched_prefix = file_rule.CharacterPrefix
					elseif matched_prefix ~= file_rule.CharacterPrefix then
						ambiguous = true
						break
					end
				end
			end

			if ambiguous then
				stats.FileConflicts = stats.FileConflicts + 1
				Utils.colour_print({ colour = "yellow", message = string.format("Skipping ambiguous file mapping in '%s': %s", folder_path, file_name) })
			elseif matched_prefix then
				local prefixed_name = matched_prefix .. "_"
				if string.sub(file_name, 1, #prefixed_name) == prefixed_name then
					stats.FileSkipped = stats.FileSkipped + 1
				else
					local new_name = prefixed_name .. file_name
					local new_path = Utils.join(folder_path, new_name)
					if sdk.path_exists(new_path) then
						stats.FileConflicts = stats.FileConflicts + 1
						Utils.colour_print({ colour = "yellow", message = string.format("Skipping file rename because target exists: %s", new_path) })
					else
						local ok = sdk.rename_file(file_path, new_path)
						if ok then
							stats.FileRenamed = stats.FileRenamed + 1
						else
							stats.FileErrors = stats.FileErrors + 1
							Utils.colour_print({ colour = "red", message = string.format("Failed to rename file: %s", file_path) })
						end
					end
				end
			end
		end
	end
end

local function create_rename_stats()
	return {
		FolderRenamed = 0,
		FolderSkipped = 0,
		FolderConflicts = 0,
		FolderErrors = 0,
		FileRenamed = 0,
		FileSkipped = 0,
		FileConflicts = 0,
		FileErrors = 0
	}
end

local function apply_rules_in_base_dir(base_dir, rules_by_old_name, stats)
	if not base_dir or not sdk.is_dir(base_dir) then
		return
	end
	if type(rules_by_old_name) ~= "table" or next(rules_by_old_name) == nil then
		return
	end

	for _, rule in pairs(rules_by_old_name) do
		local source_path = Utils.join(base_dir, rule.OldDirName)
		local target_path = Utils.join(base_dir, rule.NewDirName)
		local active_path = nil

		if lower(rule.OldDirName) == lower(rule.NewDirName) then
			if sdk.is_dir(source_path) then
				active_path = source_path
			end
		else
			if sdk.is_dir(target_path) then
				active_path = target_path
			elseif sdk.is_dir(source_path) then
				if sdk.path_exists(target_path) then
					stats.FolderConflicts = stats.FolderConflicts + 1
					Utils.colour_print({ colour = "yellow", message = string.format("Skipping folder rename because target exists: %s", target_path) })
					active_path = source_path
				else
					local ok = sdk.rename_file(source_path, target_path)
					if ok then
						stats.FolderRenamed = stats.FolderRenamed + 1
						active_path = target_path
					else
						stats.FolderErrors = stats.FolderErrors + 1
						Utils.colour_print({ colour = "red", message = string.format("Failed to rename folder: %s", source_path) })
						active_path = source_path
					end
				end
			end
		end

		if not active_path and sdk.is_dir(source_path) then
			active_path = source_path
		end

		if active_path and sdk.is_dir(active_path) then
			apply_file_rename_rules(rule, active_path, stats)
		else
			stats.FolderSkipped = stats.FolderSkipped + 1
		end
	end
end

local function print_stats(label, stats)
	print(string.format("%s Folders Renamed: %d, Skipped: %d, Conflicts: %d, Errors: %d", label, stats.FolderRenamed, stats.FolderSkipped, stats.FolderConflicts, stats.FolderErrors))
	print(string.format("%s Files Renamed: %d, Skipped: %d, Conflicts: %d, Errors: %d", label, stats.FileRenamed, stats.FileSkipped, stats.FileConflicts, stats.FileErrors))
end

local function apply_audio_map_renames(audio_root, global_dir_path)
	local audio_map_path = Utils.join(Game_Root, "reversing", "docs", "PS3_GAME", "USRDIR", "A1_Audio", "AudioMap.yaml")
	if not sdk.path_exists(audio_map_path) then
		Utils.colour_print({ colour = "yellow", message = string.format("AudioMap not found, skipping map rename phases: %s", audio_map_path) })
		return
	end

	local parsed_rules, parse_error = load_audio_map_rules(audio_map_path)
	if not parsed_rules then
		Utils.colour_print({ colour = "yellow", message = string.format("AudioMap parse failed, skipping map rename phases: %s", parse_error or "unknown error") })
		return
	end

	local language_dirs = resolve_language_dirs(audio_root)
	local language_dirs_processed = 0
	local dialogue_stats = create_rename_stats()
	local cutscene_stats = create_rename_stats()
	local global_sound_stats = create_rename_stats()

	for _, language_code in ipairs(language_dirs_to_process) do
		local language_path = language_dirs[language_code]
		if language_path and sdk.is_dir(language_path) then
			language_dirs_processed = language_dirs_processed + 1
			Utils.colour_print({ colour = "cyan", message = string.format("Applying AudioMap EN-Dialogue rules in language folder: %s", language_path) })
			apply_rules_in_base_dir(language_path, parsed_rules.ENDialogueRules, dialogue_stats)
			Utils.colour_print({ colour = "cyan", message = string.format("Applying AudioMap EN-CUTSCENE rules in language folder: %s", language_path) })
			apply_rules_in_base_dir(language_path, parsed_rules.ENCutsceneRules, cutscene_stats)
		else
			Utils.colour_print({ colour = "darkgray", message = string.format("Language folder not found, skipping: %s", language_code) })
		end
	end

	if global_dir_path and sdk.is_dir(global_dir_path) then
		Utils.colour_print({ colour = "cyan", message = string.format("Applying AudioMap Global-Sound rules in global folder: %s", global_dir_path) })
		apply_rules_in_base_dir(global_dir_path, parsed_rules.GlobalSoundRules, global_sound_stats)
	else
		Utils.colour_print({ colour = "darkgray", message = "Global folder not found, skipping Global-Sound rename phase." })
	end

	print("AudioMap rename phases complete.")
	print(string.format("AudioMap sections loaded - EN-Dialogue: %d, EN-CUTSCENE: %d, Global-Sound: %d", parsed_rules.SectionCounts.ENDialogue, parsed_rules.SectionCounts.ENCutscene, parsed_rules.SectionCounts.GlobalSound))
	print(string.format("Languages Processed: %d", language_dirs_processed))
	print_stats("EN-Dialogue", dialogue_stats)
	print_stats("EN-CUTSCENE", cutscene_stats)
	print_stats("Global-Sound", global_sound_stats)
	print(string.format("AudioMap placeholder character entries skipped: %d", parsed_rules.SkippedCharacters or 0))
end

local function parse_argv()
	-- Engine guarantees argv global; try index 1 first, then 0 for compatibility
	if argv and argv[1] and type(argv[1]) == "string" and argv[1] ~= "" then
		return argv[1]
	end
	if argv and argv[0] and type(argv[0]) == "string" and argv[0] ~= "" then
		return argv[0]
	end
	return nil
end

local function main()
	local input = parse_argv()
	if not input or input == "" then
		input = prompt("Enter Audio Source Directory path:", "audio_dir_prompt", false) or ""
	end

	input = Utils.normalize(input)

	if not input or input == "" then
		sdk.colour_print{ colour = "Red", message = "Error: AUDIO_SOURCE_DIR not provided or empty." }
		return
	end
	if not sdk.is_dir(input) then
		sdk.colour_print{ colour = "Red", message = string.format("Error: Audio source directory does not exist: %s", input) }
		return
	end

	-- check if input dir contains audiostreams/ folder or the A1_Audio/ folder
	if sdk.path_exists(Utils.join(input, "audiostreams")) then
		input = Utils.join(input, "audiostreams")
	elseif sdk.path_exists(Utils.join(input, "A1_Audio")) then
		input = Utils.join(input, "A1_Audio")
	end

	local en_dir_name = "EN"
	local global_dir_name = "Global"
	local en_dir_path = Utils.join(input, en_dir_name)
	local global_dir_path = Utils.join(input, global_dir_name)

	sdk.ensure_dir(en_dir_path)
	sdk.ensure_dir(global_dir_path)

	Utils.colour_print({ colour = "cyan", message = string.format("Organizing directories in '%s' into '%s' and '%s'...", input, en_dir_path, global_dir_path) })

	local moved, skipped, errors = 0, 0, 0

	local entries = sdk.list_dir(input)
	for _, name in ipairs(entries) do
		local item = Utils.join(input, name)
		if sdk.is_dir(item) then
			local lname = lower(name)
			if name == en_dir_name or name == global_dir_name or language_blacklist[lname] then
				Utils.colour_print({ colour = "darkgray", message = string.format("Skipping directory: '%s'", name) })
				skipped = skipped + 1
			else
				local parent = global_dirs[name] and global_dir_path or en_dir_path
				local target = Utils.join(parent, name)
				Utils.colour_print({ colour = "gray", message = string.format("Moving '%s' to '%s'...", name, target) })
				if sdk.path_exists(target) then
					Utils.colour_print({ colour = "yellow", message = string.format("Warning: Target directory '%s' already exists. Skipping move for '%s'.", target, name) })
					skipped = skipped + 1
				else
					local ok = sdk.move_dir(item, target, true) -- true = overwrite existing target
					if ok then
						moved = moved + 1
					else
						Utils.colour_print({ colour = "red", message = string.format("Error moving directory %s to %s", name, (global_dirs[name] and global_dir_name or en_dir_name)) })
						errors = errors + 1
					end
				end
			end
		end
	end

	print("Directory organization complete.")
	print(string.format("Moved: %d, Skipped: %d, Errors: %d", moved, skipped, errors))
	apply_audio_map_renames(input, global_dir_path)
	print(string.format("Setup operated on Audio Source Dir: %s", input))
end

-- run
main()

