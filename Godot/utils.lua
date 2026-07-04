---@diagnostic disable: lowercase-global

---@class GodotRunCommandOptions
---@field cwd string|nil
---@field env table<string, string>|nil
---@field new_terminal boolean|nil
---@field keep_open boolean|nil
---@field wait boolean|nil

---@class GodotCopyTreeOptions
---@field use_hardlinks boolean|nil
---@field verify_hash_for_large boolean|nil
---@field large_bytes_threshold integer|nil
---@field exts table<integer, string>|nil
---@field progress_handle PanelProgress|nil
---@field case_insensitive boolean|nil
---@field log_sample_actions integer|nil

---@class GodotCopyItem
---@field src string
---@field rel string
---@field size integer

---@class GodotCopyStats
---@field total_seen integer
---@field total_bytes integer
---@field copied integer
---@field hardlinked integer
---@field skipped_identical integer
---@field bytes_copied integer
---@field bytes_skipped integer
---@field errors integer
---@field actions table<integer, string>

---@class GodotProgressModule
---@field new fun(total: integer, id: string|nil, label: string|nil): PanelProgress
---@field start fun(total: integer, label: string|nil): PanelProgress

path_sep = package.config:sub(1,1) or "/"

---@type table<string, string>
Colours = {
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

---@param p string|nil
---@return string
function dirname(p)
	if not p or p == "" then return "." end
	local d = p:match("(.+)[/\\][^/\\]+$") or p:match("(.+)[/\\]$") or ""
	if d == "" then return "." end
	return d
end

---@param msg string
---@return nil
function log_info(msg)
	sdk.colour_print{ colour = Colours.CYAN, message = msg }
	Diagnostics.Log("[godot-init] INFO: " .. msg)
end

---@param msg string
---@return nil
function log_warn(msg)
	sdk.colour_print{ colour = Colours.YELLOW, message = msg }
	Diagnostics.Log("[godot-init] WARN: " .. msg)
	warn(msg)
end

---@param msg string
---@return nil
function log_error(msg)
	sdk.colour_print{ colour = Colours.RED, message = msg }
	Diagnostics.Log("[godot-init] ERROR: " .. msg)
	error(msg)
end

---@param msg string
---@return nil
function fatal(msg)
	log_error(msg)
	assert(false, msg)
end

---@param p string|nil
---@return string|nil
function basename(p)
	return (p and p:match("([^/\\]+)$")) or p
end

---@param p string
---@return integer|nil
function get_file_size(p)
	local a = sdk.attributes(p)
	if a and a.mode == "file" then return a.size end
	return nil
end

---@param src string
---@param dst string
---@return boolean
function nearly_same_file(src, dst)
	local sa = sdk.attributes(src)
	local da = sdk.attributes(dst)
	if not sa or not da then return false end
	if (sa.size or -1) ~= (da.size or -2) then return false end
	if sa.modification and da.modification then
		return sa.modification == da.modification
	end
	return true
end

---@param src string
---@param dst string
---@return boolean
function files_equal(src, dst)
	local ss = get_file_size(src)
	local ds = get_file_size(dst)
	if not ss or not ds or ss ~= ds then return false end
	local h1, h2 = sdk.sha1_file(normalize(src)), sdk.sha1_file(normalize(dst))
	if h1 and h2 then return h1 == h2 end
	return true
end

---@param sec integer|number|string|nil
---@return nil
function countdown(sec)
	sec = tonumber(sec) or 0
	while sec > 0 do
		sdk.colour_print{ colour = Colours.CYAN, message = string.format("Waiting... %d seconds remaining.", sec) }
		sdk.sleep(1)
		sec = sec - 1
	end
end

---@param args table<integer, string>
---@return string
function build_cmdline(args)
	local parts = {}
	for i = 1, #args do
		local a = tostring(args[i])
		if path_sep == "\\" then
			if a:find('%s') or a:find('["&|<>^]') then
				a = '"' .. a:gsub('"', '""') .. '"'
			end
		else
			if a:find('%s') or a:find('["\'$]') then
				a = "'" .. a:gsub("'", "'\\''") .. "'"
			end
		end
		parts[#parts + 1] = a
	end
	return table.concat(parts, " ")
end

---@param args table<integer, string>
---@param opts GodotRunCommandOptions|nil
---@return boolean
function run_cmd(args, opts)
	opts = opts or {}
	local cmdline = build_cmdline(args)
	sdk.colour_print{ colour = Colours.CYAN, message = "Exec: " .. cmdline }
	local res = sdk.exec(args, {
		cwd = opts.cwd,
		env = opts.env,
		new_terminal = opts.new_terminal == true,
		keep_open = opts.keep_open == true,
		wait = opts.wait ~= false,
	})
	return res and res.success == true
end

---@param command table<integer, string>
---@param label string
---@return nil
function run_godot(command, label)
	log_info(string.format("\n--- %s ---", label))
	log_info("Command: " .. build_cmdline(command))
	local ok = run_cmd(command)
	if not ok then
		log_error(string.format("Godot command failed during '%s'", label))
	end
	log_info(string.format("--- %s finished ---", label))
end

---@param src string
---@param dst string
---@return nil
function copy_file(src, dst)
	src = normalize(src)
	dst = normalize(dst)
	sdk.ensure_dir(dirname(dst))
	local ok = sdk.copy_file(src, dst, true)
	if not ok then
		fatal(string.format("SDK copy failed: '%s' -> '%s'", src, dst))
	end
	if not files_equal(src, dst) then
		fatal(string.format("Copy validation failed: '%s' -> '%s'", src, dst))
	end
end

---@param src string
---@param dst string
---@return boolean
function try_hardlink(src, dst)
	sdk.remove_file(dst)
	sdk.ensure_dir(normalize(dirname(dst)))
	return sdk.create_hardlink(src, dst) == true
end

---@param root string
---@param cb fun(absPath: string, relPath: string, filename: string): nil
---@return nil
function walk_files(root, cb)
	root = normalize(root)
	local function walk_dir(dir, rel)
		local entries = sdk.list_dir(dir)
		if not entries then return end
		for i = 1, #entries do
			local name = entries[i]
			if name ~= "." and name ~= ".." then
				local ap = join(dir, name)
				local rp = rel and join(rel, name) or name
				local a = sdk.attributes(ap)
				if a and a.mode == "directory" then
					walk_dir(ap, rp)
				elseif a and a.mode == "file" then
					cb(ap, rp, name)
				end
			end
		end
	end
	walk_dir(root, nil)
end

---@param src_root string
---@param dst_root string
---@param opts GodotCopyTreeOptions|nil
---@return GodotCopyStats
function copy_tree_incremental(src_root, dst_root, opts)
	opts = opts or {}
	local use_hardlinks = (opts.use_hardlinks ~= false)
	local verify_hash_for_large = (opts.verify_hash_for_large ~= false)
	local large_bytes_threshold = opts.large_bytes_threshold or (50 * 1024 * 1024)
	local progress_handle = opts.progress_handle
	local case_insensitive = (opts.case_insensitive == true)
	local log_sample_actions = tonumber(opts.log_sample_actions or 50) or 50

	local extset = nil
	if opts.exts and #opts.exts > 0 then
		extset = {}
		for _, e in ipairs(opts.exts) do extset[e:lower()] = true end
	end

	---@type table<integer, GodotCopyItem>
	local files = {}
	local lower_map = {}
	local total_bytes = 0
	walk_files(src_root, function(src, rel, fn)
		if extset then
			local low = fn:lower()
			local match = false
			for e, _ in pairs(extset) do
				if low:sub(-#e) == e then match = true break end
			end
			if not match then return end
		end
		local a = sdk.attributes(src)
		local sz = (a and a.size) or 0
		table.insert(files, { src = src, rel = rel, size = sz })
		total_bytes = total_bytes + sz
		if case_insensitive then
			local low = rel:lower()
			if lower_map[low] then
				log_error(string.format("Case collision detected on destination: '%s' vs '%s'", lower_map[low], rel))
			else
				lower_map[low] = rel
			end
		end
	end)

	local stats = {
		total_seen = #files,
		total_bytes = total_bytes,
		copied = 0,
		hardlinked = 0,
		skipped_identical = 0,
		bytes_copied = 0,
		bytes_skipped = 0,
		errors = 0,
		actions = {},
	}
	---@cast stats GodotCopyStats

	if progress_handle then progress_handle:Update(0) end
	sdk.ensure_dir(normalize(dst_root))

	local start_clock = os.clock()
	local last_eta_print = start_clock
	local processed_bytes = 0

	---@param processed_count integer
	---@return nil
	local function maybe_print_eta(processed_count)
		local now = os.clock()
		if now - last_eta_print < 1.0 then return end
		last_eta_print = now
		local elapsed = now - start_clock
		if elapsed <= 0.0 then return end
		local rate = processed_bytes / elapsed
		if rate <= 1 then return end
		local remain = math.max(0, total_bytes - processed_bytes)
		local eta = remain / rate
		local mm = math.floor(eta / 60)
		local ss = math.floor(eta % 60)
		sdk.colour_print{ colour = Colours.GRAY, message = string.format("Progress: %d/%d, ETA ~ %02d:%02d", processed_count, stats.total_seen, mm, ss) }
	end

	local sample_emitted = 0
	for idx, item in ipairs(files) do
		---@cast item GodotCopyItem
		local src = item.src
		local rel = item.rel
		local sz = item.size or 0
		local dst = join(dst_root, rel)

		if sdk.path_exists(dst) and nearly_same_file(src, dst) then
			stats.skipped_identical = stats.skipped_identical + 1
			stats.bytes_skipped = stats.bytes_skipped + sz
		else
			local do_copy = true
			if sdk.path_exists(dst) and verify_hash_for_large then
				local ds = get_file_size(dst)
				if ds and ds == sz and sz >= large_bytes_threshold then
					local h1 = sdk.sha1_file(normalize(src))
					local h2 = sdk.sha1_file(normalize(dst))
					if h1 and h2 and h1 == h2 then
						do_copy = false
						stats.skipped_identical = stats.skipped_identical + 1
						stats.bytes_skipped = stats.bytes_skipped + sz
					end
				end
			end

			if do_copy then
				local action = use_hardlinks and "link" or "copy"
				local at = string.format("%s: %s -> %s", action, src, dst)
				table.insert(stats.actions, at)

				if sample_emitted < log_sample_actions then
					log_info(at)
					sample_emitted = sample_emitted + 1
				end

				local ok = false
				if use_hardlinks then
					ok = try_hardlink(src, dst)
					if ok then stats.hardlinked = stats.hardlinked + 1 end
				end
				if not ok then
					local ok2, err = pcall(copy_file, src, dst)
					if not ok2 then
						stats.errors = stats.errors + 1
						log_warn(string.format("Copy failed '%s' -> '%s': %s", src, dst, tostring(err)))
					else
						stats.copied = stats.copied + 1
						stats.bytes_copied = stats.bytes_copied + sz
					end
				else
					stats.bytes_copied = stats.bytes_copied + sz
				end
			end
		end

		processed_bytes = processed_bytes + sz
		if progress_handle then progress_handle:Update(1) end
		maybe_print_eta(idx)
	end

	if progress_handle and stats.total_seen > 0 then progress_handle:Update(0) end
	return stats
end

---@param t table
---@return string
function tableToString(t)
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

---@return string
function resolve_godot()
	local tool_fn = rawget(_G, "tool")
	local p = tool_fn("Godot")
	if p and p ~= "" then return p end
	fatal("Godot executable not found via tool('Godot'); ensure Godot is installed and configured in the engine.")
	return ""
end

---@param path string|nil
---@return string|nil
function get_parent_directory(path)
	if not path then return nil end
	path = path:gsub("\\", "/")
	if path:sub(-1) == "/" then
		path = path:sub(1, -2)
	end
	local parent = path:match("^(.*)/[^/]+$")
	return parent
end

---@param dir string|nil
---@return table<integer, string>
function discover_pngs_in_dir(dir)
	local list = {}
	if not dir or dir == "" then return list end
	dir = normalize(dir)
	log_info("Scanning for logo images in: " .. dir)

	local entries = sdk.list_dir(dir)
	if not entries then return list end

	for i = 1, #entries do
		local name = entries[i]
		if name ~= "." and name ~= ".." then
			local p = join(dir, name)
			local a = sdk.attributes(p)
			if a and a.mode == "file" then
				if name:lower():sub(-4) == ".png" then
					table.insert(list, p)
				end
			end
		end
	end
	return list
end

---@param iconPath string|nil
---@return table<integer, string>
function get_logos(iconPath)
	local logos = {}
	local ok, err = pcall(function()
		local logo_dir = iconPath

		if logo_dir and sdk.is_dir(logo_dir) then
			logos = discover_pngs_in_dir(logo_dir)
		elseif logo_dir then
			log_warn("Logo directory not found: " .. logo_dir)
		end

		if #logos == 0 and logo_dir then
			local parent_dir = get_parent_directory(logo_dir)
			if parent_dir and parent_dir ~= logo_dir and sdk.is_dir(parent_dir) then
				log_info("No PNGs found in icon path. Checking parent directory: " .. parent_dir)
				logos = discover_pngs_in_dir(parent_dir)
			end
		end

		if #logos > 0 then
			log_info("Found game logo images: " .. table.concat(logos, ", "))
		end
	end)

	if not ok then
		log_warn("Logo scan warning: " .. tostring(err))
	end
	return logos
end

