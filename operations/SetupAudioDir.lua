--[[
SetupAudioDir.lua

Purpose:
- Prepare the audio source directory by grouping subfolders into 'EN' and 'Global'.
- Skips language-specific folders in a blacklist.
- Applies AudioMap-based rename phases when parser/data is available, otherwise logs and skips safely.

Runtime guarantees: sdk, argv are provided by engine
]]

---@type SharedUtils
import("SharedUtils")

---@class AudioMapFilePatterns
---@field file_pattern string?

---@class AudioMapFilePatternEntry
---@field file_pattern string?

---@class AudioMapFileEntry
---@field CharacterName string?
---@field file_patterns AudioMapFilePatterns|AudioMapFilePatternEntry[]?

---@class AudioMapSectionEntry
---@field OLD_DIR_NAME string?
---@field NEW_DIR_NAME string?
---@field files AudioMapFileEntry[]?

---@class AudioMapRenameFileRule
---@field CharacterPrefix string
---@field MatchPattern string

---@class AudioMapRenameRule
---@field OldDirName string
---@field NewDirName string
---@field FileRules AudioMapRenameFileRule[]

---@class AudioMapRenameStats
---@field FolderRenamed integer
---@field FolderSkipped integer
---@field FolderConflicts integer
---@field FolderErrors integer
---@field FileRenamed integer
---@field FileSkipped integer
---@field FileConflicts integer
---@field FileErrors integer

---@class AudioMapSectionCounts
---@field Dialogue integer
---@field Cutscene integer
---@field GlobalSound integer

---@class ParsedAudioMapRules
---@field DialogueRules table<string, AudioMapRenameRule>
---@field CutsceneRules table<string, AudioMapRenameRule>
---@field GlobalSoundRules table<string, AudioMapRenameRule>
---@field SkippedCharacters integer
---@field SectionCounts AudioMapSectionCounts

---@class ApplyRulesOptions
---@field UseCharacterSubfolders boolean?

-- Hardcoded Language Blacklist and Global Dirs (mirrors Python script)
---@type table<string, boolean>
local language_blacklist = { it=true, es=true, fr=true }
---@type string[]
local language_dirs_to_process = { "en", "es", "fr", "it" }
---@type table<string, boolean>
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

---@param s any
---@return any
local function lower(s)
	if type(s) ~= "string" then
		return s
	end
	return string.lower(s)
end

---@param path string?
---@param label string?
---@return string[]
local function safe_list_dir(path, label)
	if not path or path == "" then
		return {}
	end

	local entries = sdk.list_dir(path)
	if type(entries) ~= "table" then
		Utils.colour_print({ colour = "yellow", message = string.format("Unable to list directory, skipping %s: %s", label or "phase", tostring(path)) })
		return {}
	end

	return entries
end

---@param name any
---@return string
local function strip_xxx_suffix(name)
	local value = Utils.trim(name)
	if type(value) ~= "string" then
		return ""
	end
	if value == "" then
		return value
	end
	if lower(value):match("_xxx_0$") then
		return value:sub(1, #value - 6)
	end
	return value
end

---@param name any
---@return boolean
local function is_placeholder_character_name(name)
	local raw_value = Utils.trim(name)
	if type(raw_value) ~= "string" then
		return true
	end

	local value = lower(raw_value)
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

---@param name any
---@return string
local function sanitize_character_prefix(name)
	local value = Utils.trim(name)
	if type(value) ~= "string" then
		return ""
	end
	if value == "" then
		return value
	end
	-- Keep readable names but remove filesystem-invalid characters.
	value = value:gsub("[\\/:%*%?\"<>|]", "_")
	value = value:gsub("%s+", " ")
	value = Utils.trim(value)
	return value
end

---@param file_pattern any
---@return string?
local function build_file_match_pattern(file_pattern)
	local raw = Utils.trim(file_pattern)
	if type(raw) ~= "string" then
		return nil
	end
	if raw == "" then
		return nil
	end

	local placeholder = "__HEX7__"
	local escaped = raw:gsub("#######", placeholder)
	escaped = escaped:gsub("([%^%$%(%)%%%.%[%]%*%+%-%?])", "%%%1")
	escaped = escaped:gsub(placeholder, "[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]")
	return "^" .. escaped .. "$"
end

---@param file_entry AudioMapFileEntry|table|nil
---@return string[]
local function extract_file_patterns(file_entry)
	---@type string[]
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

---@param node table|nil
---@param section_name string
---@param collector AudioMapSectionEntry[]
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

---@param entries AudioMapSectionEntry[]|table|nil
---@return table<string, AudioMapRenameRule>
---@return integer
local function build_rules_from_entries(entries)
	---@type table<string, AudioMapRenameRule>
	local rules_by_old_name = {}
	local skipped_characters = 0
	if type(entries) ~= "table" then
		return rules_by_old_name, skipped_characters
	end

	for _, entry in ipairs(entries) do
		local old_name = type(entry.OLD_DIR_NAME) == "string" and Utils.trim(entry.OLD_DIR_NAME) or ""
		if old_name ~= "" then
			local new_name = type(entry.NEW_DIR_NAME) == "string" and Utils.trim(entry.NEW_DIR_NAME) or ""
			if new_name == "" or lower(new_name) == "tbd" then
				new_name = strip_xxx_suffix(old_name)
			end

			---@type AudioMapRenameRule
			local rule = {
				OldDirName = old_name,
				NewDirName = new_name,
				FileRules = {}
			}

			if type(entry.files) == "table" then
				for _, file_entry in ipairs(entry.files) do
					if type(file_entry) == "table" then
						local character_name = Utils.trim(file_entry.CharacterName)
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

---@param audio_map_path string
---@return ParsedAudioMapRules|nil
---@return string|nil
local function load_audio_map_rules(audio_map_path)
	local yaml_reader = nil
	if sdk.text and sdk.text.yaml and type(sdk.text.yaml.read_file) == "function" then
		yaml_reader = sdk.text.yaml.read_file
	elseif type(sdk.yaml_read_file) == "function" then
		yaml_reader = sdk.yaml_read_file
	end

	if not yaml_reader then
		return nil, "YAML parser is unavailable (sdk.text.yaml.read_file and sdk.yaml_read_file not found)"
	end

	local ok, parsed = pcall(yaml_reader, audio_map_path)
	if not ok then
		return nil, string.format("AudioMap parser threw an exception: %s", tostring(parsed))
	end

	if type(parsed) ~= "table" then
		return nil, string.format("AudioMap parser returned invalid root type: %s", type(parsed))
	end

	if next(parsed) == nil then
		return nil, "AudioMap parser returned an empty table"
	end

	---@type table<string, AudioMapSectionEntry[]>
	local section_entries = {
		["Dialogue"] = {},
		["CUTSCENE"] = {},
		["Global-Sound"] = {}
	}

	for section_name, entries in pairs(section_entries) do
		find_section_entries(parsed, section_name, entries)
	end

	local dialogue_rules, dialogue_skipped = build_rules_from_entries(section_entries["Dialogue"])
	local cutscene_rules, cutscene_skipped = build_rules_from_entries(section_entries["CUTSCENE"])
	local global_sound_rules, global_sound_skipped = build_rules_from_entries(section_entries["Global-Sound"])

	if next(dialogue_rules) == nil then
		return nil, "No Dialogue entries found in AudioMap.yaml"
	end

	return {
		DialogueRules = dialogue_rules,
		CutsceneRules = cutscene_rules,
		GlobalSoundRules = global_sound_rules,
		SkippedCharacters = dialogue_skipped + cutscene_skipped + global_sound_skipped,
		SectionCounts = {
			Dialogue = #section_entries["Dialogue"],
			Cutscene = #section_entries["CUTSCENE"],
			GlobalSound = #section_entries["Global-Sound"]
		}
	}, nil
end

---@param root_dir string
---@return table<string, string>
local function resolve_language_dirs(root_dir)
	---@type table<string, string>
	local resolved = {}
	for _, name in ipairs(safe_list_dir(root_dir, "language directory discovery")) do
		local candidate = normalize(join(root_dir, name))
		if sdk.is_dir(candidate) then
			local lname = lower(name)
			if lname == "en" or lname == "es" or lname == "fr" or lname == "it" then
				resolved[lname] = candidate
			end
		end
	end
	return resolved
end

---@param path_a string?
---@param path_b string?
---@return boolean
local function same_path(path_a, path_b)
	if not path_a or not path_b then
		return false
	end
	return lower(Utils.normalize(path_a)) == lower(Utils.normalize(path_b))
end

---@param file_name string
---@param file_rules AudioMapRenameFileRule[]|nil
---@return string|nil
---@return boolean
local function resolve_character_subfolder(file_name, file_rules)
	if type(file_rules) ~= "table" or #file_rules == 0 then
		return nil, false
	end

	local matched_prefix = nil
	local ambiguous = false

	for _, file_rule in ipairs(file_rules) do
		if string.match(file_name, file_rule.MatchPattern) then
			if not matched_prefix then
				matched_prefix = file_rule.CharacterPrefix
			elseif matched_prefix ~= file_rule.CharacterPrefix then
				ambiguous = true
				break
			end
		end
	end

	return matched_prefix, ambiguous
end

---@param source_file_path string
---@param target_file_path string
---@param stats AudioMapRenameStats
local function move_file_with_conflict_checks(source_file_path, target_file_path, stats)
	if same_path(source_file_path, target_file_path) then
		stats.FileSkipped = stats.FileSkipped + 1
		return
	end

	if sdk.path_exists(target_file_path) then
		stats.FileConflicts = stats.FileConflicts + 1
		Utils.colour_print({ colour = "yellow", message = string.format("Skipping file move because target exists: %s", target_file_path) })
		return
	end

	local ok = sdk.rename_file(source_file_path, target_file_path)
	if ok then
		stats.FileRenamed = stats.FileRenamed + 1
	else
		stats.FileErrors = stats.FileErrors + 1
		Utils.colour_print({ colour = "red", message = string.format("Failed to move file: %s", source_file_path) })
	end
end

---@return AudioMapRenameStats
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

---@param base_dir string?
---@param rules_by_old_name table<string, AudioMapRenameRule>|nil
---@param stats AudioMapRenameStats
---@param options ApplyRulesOptions?
local function apply_rules_in_base_dir(base_dir, rules_by_old_name, stats, options)
	if not base_dir or not sdk.is_dir(base_dir) then
		return
	end
	if type(rules_by_old_name) ~= "table" or next(rules_by_old_name) == nil then
		return
	end

	local use_character_subfolders = true
	if type(options) == "table" and options.UseCharacterSubfolders == false then
		use_character_subfolders = false
	end

	for _, rule in pairs(rules_by_old_name) do
		local source_path = normalize(join(base_dir, rule.OldDirName))
		local target_path = normalize(join(base_dir, rule.NewDirName))

		if not sdk.is_dir(source_path) then
			stats.FolderSkipped = stats.FolderSkipped + 1
		else
			local target_ready = sdk.ensure_dir(target_path)
			if not target_ready or not sdk.is_dir(target_path) then
				stats.FolderErrors = stats.FolderErrors + 1
				Utils.colour_print({ colour = "red", message = string.format("Failed to create/resolve target folder: %s", target_path) })
			else
				local entries = safe_list_dir(source_path, "rule source folder")
				for _, name in ipairs(entries) do
					local source_item_path = normalize(join(source_path, name))
					if sdk.is_file(source_item_path) then
						local character_folder_name, ambiguous = nil, false
						if use_character_subfolders then
							character_folder_name, ambiguous = resolve_character_subfolder(name, rule.FileRules)
						end
						local destination_dir = target_path
						if ambiguous then
							stats.FileConflicts = stats.FileConflicts + 1
							Utils.colour_print({ colour = "yellow", message = string.format("Ambiguous character mapping, moving to target root: %s", source_item_path) })
						elseif character_folder_name and character_folder_name ~= "" then
							destination_dir = normalize(join(target_path, character_folder_name))
							if not sdk.ensure_dir(destination_dir) or not sdk.is_dir(destination_dir) then
								stats.FileErrors = stats.FileErrors + 1
								Utils.colour_print({ colour = "red", message = string.format("Failed to create character folder: %s", destination_dir) })
								destination_dir = target_path
							end
						end

						local target_file_path = normalize(join(destination_dir, name))
						move_file_with_conflict_checks(source_item_path, target_file_path, stats)
					elseif sdk.is_dir(source_item_path) then
						local target_item_path = normalize(join(target_path, name))
						if not same_path(source_item_path, target_item_path) then
							if sdk.path_exists(target_item_path) and not sdk.is_dir(target_item_path) then
								stats.FolderConflicts = stats.FolderConflicts + 1
								Utils.colour_print({ colour = "yellow", message = string.format("Skipping directory move because file exists at target path: %s", target_item_path) })
							else
								local moved_ok = sdk.rename_file(source_item_path, target_item_path)
								if moved_ok then
									stats.FolderRenamed = stats.FolderRenamed + 1
								else
									stats.FolderErrors = stats.FolderErrors + 1
									Utils.colour_print({ colour = "red", message = string.format("Failed to move directory: %s", source_item_path) })
								end
							end
						end
					end
				end

				if not same_path(source_path, target_path) and sdk.is_dir(source_path) then
					local remaining = safe_list_dir(source_path, "remaining source entries")
					if #remaining == 0 then
						if sdk.remove_dir(source_path) then
							stats.FolderRenamed = stats.FolderRenamed + 1
						else
							stats.FolderErrors = stats.FolderErrors + 1
							Utils.colour_print({ colour = "red", message = string.format("Failed to remove emptied source folder: %s", source_path) })
						end
					else
						stats.FolderSkipped = stats.FolderSkipped + 1
						Utils.colour_print({ colour = "darkgray", message = string.format("Source folder retained with remaining entries: %s", source_path) })
					end
				end
			end
		end
	end
end

---@param label string
---@param stats AudioMapRenameStats
local function print_stats(label, stats)
	print(string.format("%s Folders Renamed: %d, Skipped: %d, Conflicts: %d, Errors: %d", label, stats.FolderRenamed, stats.FolderSkipped, stats.FolderConflicts, stats.FolderErrors))
	print(string.format("%s Files Renamed: %d, Skipped: %d, Conflicts: %d, Errors: %d", label, stats.FileRenamed, stats.FileSkipped, stats.FileConflicts, stats.FileErrors))
end

---@param audio_root string
---@param global_dir_path string?
local function apply_audio_map_renames(audio_root, global_dir_path)
	if type(Game_Root) ~= "string" or Utils.trim(Game_Root) == "" then
		Utils.colour_print({ colour = "yellow", message = "Game_Root is unavailable, skipping AudioMap rename phases." })
		return
	end

	local audio_map_path = normalize(join(Game_Root, "reversing", "docs", "PS3_GAME", "USRDIR", "A1_Audio", "AudioMap.yaml"))
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
			Utils.colour_print({ colour = "cyan", message = string.format("Applying AudioMap Dialogue rules in language folder: %s", language_path) })
			apply_rules_in_base_dir(language_path, parsed_rules.DialogueRules, dialogue_stats)
			Utils.colour_print({ colour = "cyan", message = string.format("Applying AudioMap CUTSCENE rules in language folder: %s", language_path) })
			apply_rules_in_base_dir(language_path, parsed_rules.CutsceneRules, cutscene_stats)
		else
			Utils.colour_print({ colour = "darkgray", message = string.format("Language folder not found, skipping: %s", language_code) })
		end
	end

	if global_dir_path and sdk.is_dir(global_dir_path) then
		Utils.colour_print({ colour = "cyan", message = string.format("Applying AudioMap Global-Sound rules in global folder: %s", global_dir_path) })
		apply_rules_in_base_dir(global_dir_path, parsed_rules.GlobalSoundRules, global_sound_stats, { UseCharacterSubfolders = false })
	else
		Utils.colour_print({ colour = "darkgray", message = "Global folder not found, skipping Global-Sound rename phase." })
	end

	print("AudioMap rename phases complete.")
	print(string.format("AudioMap sections loaded - Dialogue: %d, CUTSCENE: %d, Global-Sound: %d", parsed_rules.SectionCounts.Dialogue, parsed_rules.SectionCounts.Cutscene, parsed_rules.SectionCounts.GlobalSound))
	print(string.format("Languages Processed: %d", language_dirs_processed))
	print_stats("Dialogue", dialogue_stats)
	print_stats("CUTSCENE", cutscene_stats)
	print_stats("Global-Sound", global_sound_stats)
	print(string.format("AudioMap placeholder character entries skipped: %d", parsed_rules.SkippedCharacters or 0))
end

---@return string?
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

---@return nil
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
	if sdk.path_exists(normalize(join(input, "audiostreams"))) then
		input = normalize(join(input, "audiostreams"))
	elseif sdk.path_exists(normalize(join(input, "A1_Audio"))) then
		input = normalize(join(input, "A1_Audio"))
	end

	local en_dir_name = "EN"
	local global_dir_name = "Global"
	local en_dir_path = normalize(join(input, en_dir_name))
	local global_dir_path = normalize(join(input, global_dir_name))

	sdk.ensure_dir(en_dir_path)
	sdk.ensure_dir(global_dir_path)

	Utils.colour_print({ colour = "cyan", message = string.format("Organizing directories in '%s' into '%s' and '%s'...", input, en_dir_path, global_dir_path) })

	local moved, skipped, errors = 0, 0, 0

	local entries = safe_list_dir(input, "top-level audio source")
	for _, name in ipairs(entries) do
		local item = normalize(join(input, name))
		if sdk.is_dir(item) then
			local lname = lower(name)
			if name == en_dir_name or name == global_dir_name or language_blacklist[lname] then
				Utils.colour_print({ colour = "darkgray", message = string.format("Skipping directory: '%s'", name) })
				skipped = skipped + 1
			else
				local parent = global_dirs[name] and global_dir_path or en_dir_path
				local target = normalize(join(parent, name))
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

