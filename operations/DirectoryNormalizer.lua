--[[
DirectoryNormalizer.lua

Reimplementation of reversing/Format-Analysis/preinstanced/DirectoryNormalizer.py
for the RemakeEngine Lua runtime (MoonSharp) with the provided SDK.

Goals
- Preserve base folders (Assets_* / Map_*) and zone folders when present.
- Normalize character folders to a single root per character, variants as subfolders.
- Build a readable filename and deterministic short key from the original relative path.
- Emit JSON mapping files (flatten_map.json, flatten_map_<BASE>.json, summary).
- Copy files (default) or dry-run preview; configurable via args.
- Broaden supported file types (default: all files); allow filtering with --ext.

Runtime guarantees: lfs, dkjson, sdk, argv are provided by engine
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

local function to_lower_list(parts)
    local out = {}
    for i=1,#parts do out[i] = string.lower(parts[i]) end
    return out
end

local function isdigit_byte(b)
    return b and b >= 48 and b <= 57
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

local function read_all_text(path)
    local f = io.open(path, "rb"); if not f then return nil end
    local d = f:read("*a"); f:close(); return d
end

local function write_all_text(path, data)
    local parent = path:match("^(.*)[/\\][^/\\]+$")
    if parent and parent ~= "" then ensure_dir(parent) end
    local f = io.open(path, "wb"); if not f then return false end
    f:write(data); f:close(); return true
end

local function colour_print(colour, message)
    sdk.colour_print({ colour = colour or "default", message = message or "", newline = true })
end

-- JSON helpers --------------------------------------------------------------
local function json_decode(str)
    local obj = dkjson.decode(str)
    return obj
end

local function json_encode(obj, indent)
    return dkjson.encode(obj, { indent = indent ~= false })
end

-- Base32 encode from hex string (uppercase alphabet), trim '='; lowercases final
local function hex_to_bytes(hex)
    local bytes = {}
    for i = 1, #hex, 2 do
        local byte = tonumber(hex:sub(i, i+1), 16)
        bytes[#bytes+1] = string.char(byte)
    end
    return table.concat(bytes)
end

local function base32_encode(bin)
    local alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    local output = {}
    local bitbuf, bitcount = 0, 0
    for i = 1, #bin do
        bitbuf = bitbuf * 256 + bin:byte(i)
        bitcount = bitcount + 8
        while bitcount >= 5 do
            local idx = math.floor(bitbuf / (2 ^ (bitcount - 5))) % 32
            bitcount = bitcount - 5
            output[#output+1] = alphabet:sub(idx + 1, idx + 1)
        end
    end
    if bitcount > 0 then
        local idx = (bitbuf * (2 ^ (5 - bitcount))) % 32
        output[#output+1] = alphabet:sub(idx + 1, idx + 1)
    end
    return table.concat(output)
end

-- Short key: Base32(SHA1(original_rel_path))[:length], lowercase
local function short_key_from_string(s, length, tmp_dir)
    length = length or 10
    local tmp = join(tmp_dir, "key.tmp")
    write_all_text(tmp, s)
    local hex = sdk.sha1_file(tmp)
    if not hex or hex == "" then
        -- Fallback to MD5 if SHA1 fails (should never happen with engine SDK)
        hex = sdk.md5(s) or ""
    end
    if hex == "" then return "0000000000" end
    local bin = hex_to_bytes(hex)
    local b32 = base32_encode(bin):gsub("=+", "")
    return string.lower(b32:sub(1, length))
end

-- Name/path helpers mirroring Python script --------------------------------
local function multi_ext(name)
    local idx = name:find(".")
    if not idx then return name, "" end
    return name:sub(1, idx-1), name:sub(idx)
end

local function sanitize_filename(name)
    -- Replace Windows-unsafe characters and control codes without complex Lua patterns
    local out = {}
    for i = 1, #name do
        local ch = name:sub(i, i)
        local b = string.byte(ch)
        if b and b < 32 then
            out[#out+1] = '_'
        elseif ch == '<' or ch == '>' or ch == ':' or ch == '"' or ch == '/' or ch == '\\' or ch == '|' or ch == '?' or ch == '*' then
            out[#out+1] = '_'
        else
            out[#out+1] = ch
        end
    end
    local s = table.concat(out)
    -- trim outer whitespace using simple patterns
    s = (s:gsub('^%s+', ''):gsub('%s+$', ''))
    return s
end

local function strip_str_suffix(token, enable)
    if not token or token == "" then return token end
    if enable == false then return token end
    return (token:gsub("_str$", ""))
end

local function normalize_piece(s)
    if not s or s == "" then return "unk" end
    s = s:gsub("[^A-Za-z0-9_]+", "_")
    s = s:gsub("^_+", ""):gsub("_+$", "")
    return s
end

-- Character folder parsing
local function char_root_and_variant(parts)
    -- Expects parts after base, not including filename
    for i=1,#parts-0 do
        if string.lower(parts[i]) == "chars" and i+1 <= #parts then
            local folder = parts[i+1]
            local lowerf = string.lower(folder)
            if #lowerf >= 4 and lowerf:sub(#lowerf-3) == "_str" then
                local body = folder:sub(1, #folder-4) -- keep original casing for variant
                local us = body:find("_", 1, true)
                if us then
                    local char_name = string.lower(body:sub(1, us-1))
                    -- validate char_name letters only
                    local ok = #char_name > 0
                    for c in char_name:gmatch(".") do
                        local b = string.byte(c)
                        if not (b and b >= 97 and b <= 122) then ok=false; break end
                    end
                    if ok then
                        local variant = body:sub(us+1)
                        return char_name .. "_str", variant, i
                    end
                else
                    -- already canonical <name>_str
                    return folder, "", i
                end
            end
            return nil, "", nil
        end
    end
    return nil, "", nil
end

local function find_base_folder(rel_parts, base_prefixes)
    for i=1,#rel_parts do
        for j=1,#base_prefixes do
            local pref = base_prefixes[j]
            if rel_parts[i]:sub(1, #pref) == pref then
                return i, rel_parts[i]
            end
        end
    end
    return nil, nil
end

local function find_zone(parts)
    for i=1,#parts do
        local p = parts[i]
        if string.match(string.lower(p), "^zone%d+") then
            return p
        end
    end
    return nil
end

local function find_category(parts, categories)
    local lower = to_lower_list(parts)
    for i=1,#lower do
        if lower[i] == "assets" and i+1 <= #lower then
            local cat = lower[i+1]
            for _,c in ipairs(categories) do
                if c == cat then
                    return (cat == "characters") and "chars" or cat
                end
            end
        end
    end
    for i=#lower,1,-1 do
        for _,c in ipairs(categories) do
            if lower[i] == c then
                return (c == "characters") and "chars" or c
            end
        end
    end
    return "misc"
end

local function find_purpose(parts, stem, purpose_tokens, filename_patterns)
    -- Prefer purpose from path tokens
    for _,p in ipairs(parts) do
        local pl = string.lower(p)
        for _,pt in ipairs(purpose_tokens) do
            if pl == pt then
                if pl:sub(1,3) == "lod" then return "lod" end
                return pt
            end
        end
    end
    local s = string.lower(stem or "")
    -- lodN or lodN_model
    if s:sub(1,3) == "lod" then
        local i = 4
        local ch = s:sub(i,i)
        if ch == '_' or ch == '-' or ch == ' ' then i = i + 1 end
        local j = i
        while j <= #s and isdigit_byte(s:byte(j)) do j = j + 1 end
        if j > i then
            if j > #s then return "lod" end
            local k = j
            ch = s:sub(k,k)
            if ch == '_' or ch == '-' or ch == ' ' then k = k + 1 end
            if s:sub(k) == "model" then return "lod" end
            return "lod"
        end
    end
    -- opt_modelN
    if s:sub(1,3) == "opt" then
        local i = 4
        local ch = s:sub(i,i)
        if ch == '_' or ch == '-' or ch == ' ' then i = i + 1 end
        if s:sub(i, i+4) == "model" then
            local j = i + 5
            local k = j
            while k <= #s and isdigit_byte(s:byte(k)) do k = k + 1 end
            if k > j then return "opt" end
        end
    end
    -- *_geo / geo
    if s == "geo" or (#s >= 4 and s:sub(#s-3) == "_geo") then return "geo" end
    -- terrain*
    if s:sub(1,7) == "terrain" then return "terrain" end
    return "misc"
end

local function extract_index(stem, purpose)
    local s = string.lower(stem or "")
    local p = s:find("lod", 1, true)
    if p then
        local i = p + 3
        local ch = s:sub(i,i)
        if ch == '_' or ch == '-' or ch == ' ' then i = i + 1 end
        local j = i
        while j <= #s and isdigit_byte(s:byte(j)) do j = j + 1 end
        if j > i then return s:sub(i, j-1) end
    end
    if purpose == "opt" then
        local po = s:find("opt", 1, true)
        if po then
            local i = po + 3
            local ch = s:sub(i,i)
            if ch == '_' or ch == '-' or ch == ' ' then i = i + 1 end
            if s:sub(i, i+4) == "model" then
                local j = i + 5
                local k = j
                while k <= #s and isdigit_byte(s:byte(k)) do k = k + 1 end
                if k > j then return s:sub(j, k-1) end
            end
        end
    end
    return nil
end

local function pick_owner(parts, generic_tokens)
    local cand = {}
    for _,p in ipairs(parts) do
        local pl = string.lower(p)
        if pl:sub(1,8) == "costume_" then
            table.insert(cand, p)
        elseif pl:sub(-4) == "_str" then
            table.insert(cand, p)
        elseif pl:sub(-4) == "_hub" then
            table.insert(cand, p)
        elseif not pl:find("zone", 1, true) and not generic_tokens[pl] then
            local us = pl:find("_", 1, true)
            if us and us > 1 then
                local left = pl:sub(1, us-1)
                local right = pl:sub(us+1)
                local ok_left = #left > 0
                for c in left:gmatch(".") do
                    local b = string.byte(c)
                    if not (b and b >= 97 and b <= 122) then ok_left=false; break end
                end
                local ok_right = #right > 0
                for c in right:gmatch(".") do
                    local b = string.byte(c)
                    if not ((b and b >= 97 and b <= 122) or (b and b >= 48 and b <= 57) or c == "_") then ok_right=false; break end
                end
                if ok_left and ok_right then
                    table.insert(cand, p)
                end
            end
        end
    end
    return cand[#cand]
end

local function pick_asset_leaf(parts, categories, purpose_tokens, generic_tokens)
    local lower = to_lower_list(parts)
    local purpose_set = {}
    for _,p in ipairs(purpose_tokens) do purpose_set[p] = true end

    for i,p in ipairs(lower) do
        if p == "assets" and i+2 <= #lower then
            local cat = lower[i+1]
            local is_cat = false
            for _,c in ipairs(categories) do if c == cat then is_cat = true; break end end
            if is_cat then
                local cand = parts[i+2]
                local pl = string.lower(cand)
                if not generic_tokens[pl] and not purpose_set[pl] then
                    return cand
                end
            end
        end
    end

    local export_idx
    for i,p in ipairs(lower) do if p == "export" then export_idx = i end end
    if export_idx then
        for _,k in ipairs({export_idx-1, export_idx+1}) do
            if k >= 1 and k <= #parts then
                local cand = parts[k]
                local pl = string.lower(cand)
                if not generic_tokens[pl] and not purpose_set[pl] then
                    return cand
                end
            end
        end
    end

    for i=#parts,1,-1 do
        local pl = string.lower(parts[i])
        if not generic_tokens[pl] and not purpose_set[pl] then
            return parts[i]
        end
    end
    return nil
end

-- Renderer -----------------------------------------------------------------
local function render_filename(meta, ext, mode, template)
    local owner = meta.owner or ""
    local asset = meta.asset or ""
    local purpose = meta.purpose or ""
    local index = meta.index or ""
    local key = meta.key or ""

    if owner ~= "" and asset ~= "" and string.lower(owner) == string.lower(asset) then
        asset = ""
    end

    local m = string.lower(mode or "flattened")
    if m == "key_only" then
        return string.format("%s%s", key, ext)
    elseif m == "template" and template and template ~= "" then
        local _index = (index ~= nil and index ~= "") and ("_"..tostring(index)) or ""
        local out = template
        out = out:gsub("{owner}", owner)
        out = out:gsub("{asset}", asset)
        out = out:gsub("{purpose}", purpose)
        out = out:gsub("{index}", tostring(index or ""))
        out = out:gsub("{_index}", _index)
        out = out:gsub("{key}", key)
        out = out:gsub("{ext}", ext)
        return out
    else
        local pieces = {}
        if owner and owner ~= "" then table.insert(pieces, owner) end
        if asset and asset ~= "" then table.insert(pieces, asset) end
        if purpose and purpose ~= "" then table.insert(pieces, purpose) end
        if index and index ~= "" then table.insert(pieces, tostring(index)) end
        local base = table.concat(pieces, "_")
        return string.format("%s__K%s%s", base, key, ext)
    end
end

-- Core transformation -------------------------------------------------------
local function build_new_path(rel, rules, tmp_key_dir)
    local rel_parts = split_path(rel)
    local base_idx, base_name = find_base_folder(rel_parts, rules.base_folder_prefixes)
    if not base_name then return nil end

    local after_base = {}
    for i=base_idx+1, #rel_parts-1 do table.insert(after_base, rel_parts[i]) end
    local filename = rel_parts[#rel_parts]
    local stem, ext = multi_ext(filename)

    local zone = find_zone(after_base)
    local category = find_category(after_base, rules.categories)
    local purpose = find_purpose(after_base, stem, rules.purpose_tokens, rules.filename_patterns)
    local index = extract_index(stem, purpose)
    local owner = pick_owner(after_base, rules.generic_tokens_set)
    local asset = pick_asset_leaf(after_base, rules.categories, rules.purpose_tokens, rules.generic_tokens_set)

    local char_main, variant_slug, _ = char_root_and_variant(after_base)

    local zone_out = strip_str_suffix(zone, rules.strip_str_suffix)
    asset = strip_str_suffix(asset, rules.strip_str_suffix)

    local owner_for_name = (char_main and char_main or owner)
    owner_for_name = strip_str_suffix(owner_for_name, rules.strip_str_suffix)
    local owner_n = normalize_piece(owner_for_name)
    local asset_n = normalize_piece(asset)

    -- Short key from original relative path
    local key = short_key_from_string(rel, 10, tmp_key_dir)

    local meta = {
        base = base_name,
        zone = zone_out or "",
        category = category,
        purpose = purpose,
        owner = owner_n,
        asset = asset_n,
        index = index or "",
        key = key,
        ext = ext
    }

    local new_name = render_filename(meta, ext, rules.file_name_mode, rules.file_name_template)

    local new_dir_parts = { base_name }
    if zone_out and zone_out ~= "" then table.insert(new_dir_parts, zone_out) end
    if char_main then
        local char_root_folder = normalize_piece(strip_str_suffix(char_main, rules.strip_str_suffix))
        table.insert(new_dir_parts, "chars")
        table.insert(new_dir_parts, char_root_folder)
        if variant_slug and variant_slug ~= "" then table.insert(new_dir_parts, variant_slug) end
        if string.lower(category) ~= "chars" then table.insert(new_dir_parts, category) end
    else
        table.insert(new_dir_parts, category)
    end
    table.insert(new_dir_parts, purpose)

    local new_rel = table.concat(new_dir_parts, path_sep) .. path_sep .. new_name
    return new_rel, meta
end

-- Arg parsing ---------------------------------------------------------------
local function parse_args(argv)
    local function gets(i) local v = argv[i]; return type(v) == "string" and v or nil end
    local out = { ignores = {}, dry_run = false, action = "copy", exts = nil }
    out.src = gets(1)
    out.dst = gets(2)
    local i = 3
    while true do
        local a = gets(i); if not a then break end
        if a == "--rules" then out.rules = gets(i+1); i = i + 2
        elseif a == "--action" then out.action = (gets(i+1) or out.action); i = i + 2
        elseif a == "--ignore" then table.insert(out.ignores, gets(i+1) or ""); i = i + 2
        elseif a == "--dry-run" then out.dry_run = true; i = i + 1
        elseif a == "--ext" or a == "--exts" then
            local v = gets(i+1) or ""; i = i + 2
            local list = {}
            for token in v:gmatch("[^,]+") do
                local t = token:gsub("^%s+", ""):gsub("%s+$", "")
                if t ~= "" then table.insert(list, string.lower(t)) end
            end
            if #list > 0 then out.exts = list end
        else
            i = i + 1
        end
    end
    return out
end

local function load_rules(path)
    local defaults = {
        categories = { "environs", "props", "chars", "weapons", "characters", "fx", "ui", "audio" },
        purpose_tokens = { "geo", "opt", "lod", "bound", "rig", "tex", "mat", "proxy", "anim", "terrain" },
        filename_patterns = {
            { pattern = "^lod[_\\- ]?(\\d+)", purpose = "lod" },
            { pattern = "^lod(\\d+)[_\\- ]?model$", purpose = "lod" },
            { pattern = "^opt[_\\- ]?model(\\d+)$", purpose = "opt" },
            { pattern = "^(.*)_geo$", purpose = "geo" },
            { pattern = "^terrain", purpose = "terrain" },
        },
        base_folder_prefixes = { "Assets_", "Map_" },
        generic_tokens = { "export", "assets", "build", "ntsc_en", "ps3", "rws" },
        strip_str_suffix = true,
        file_name_mode = "flattened",
        file_name_template = "{owner}_{asset}_{purpose}{_index}__K{key}{ext}",
    }
    if not path or path == "" then
        -- Build sets from defaults
        local set = {}
        for _,g in ipairs(defaults.generic_tokens) do set[g] = true end
        defaults.generic_tokens_set = set
        return defaults
    end
    local txt = read_all_text(path)
    if not txt then
        local set = {}
        for _,g in ipairs(defaults.generic_tokens) do set[g] = true end
        defaults.generic_tokens_set = set
        return defaults
    end
    local obj = json_decode(txt) or {}
    local rules = {
        categories = obj.categories or defaults.categories,
        purpose_tokens = obj.purpose_tokens or defaults.purpose_tokens,
        filename_patterns = obj.filename_patterns or defaults.filename_patterns,
        base_folder_prefixes = obj.base_folder_prefixes or defaults.base_folder_prefixes,
        generic_tokens = obj.generic_tokens or defaults.generic_tokens,
        strip_str_suffix = obj.strip_str_suffix ~= false,
        file_name_mode = obj.file_name_mode or defaults.file_name_mode,
        file_name_template = obj.file_name_template or defaults.file_name_template,
    }
    local set = {}
    for _,g in ipairs(rules.generic_tokens) do set[string.lower(g)] = true end
    rules.generic_tokens_set = set
    return rules
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

local function should_include_file(file, exts)
    if not exts or #exts == 0 then return true end
    local e = ext_lower(file)
    for _,x in ipairs(exts) do
        if e == x then return true end
    end
    return false
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

local function main()
    local args = parse_args(argv)
    if not args.src or args.src == "" then error("source dir missing") end
    if not args.dst or args.dst == "" then error("output dir missing") end
    args.src = norm_slashes(args.src)
    args.dst = norm_slashes(args.dst)

    local rules = load_rules(args.rules)

    ensure_dir(args.dst)
    local tmp_key_dir = join(args.dst, ".tmp_keys")
    ensure_dir(tmp_key_dir)

    local all_files = walk_files(args.src, args.ignores)
    -- Filter by extension list if provided
    local files = {}
    for _,f in ipairs(all_files) do
        if should_include_file(f, args.exts) then table.insert(files, f) end
    end

    local prog = progress(#files, "normalize", "Normalizing directory")
    local ok, err = pcall(function()
        local mapping_rows = {}
        local per_base = {}
        local total = 0

        for i=1,#files do
            local full = files[i]
            local rel = rel_path(full, args.src)
            local new_rel, meta = build_new_path(rel, rules, tmp_key_dir)
            if new_rel then
                total = total + 1
                local new_path = join(args.dst, new_rel)

                local row = {
                    key = meta.key,
                    original_path = rel,
                    new_path = new_rel,
                    base = meta.base,
                    zone = meta.zone,
                    category = meta.category,
                    purpose = meta.purpose,
                    owner = meta.owner,
                    asset = meta.asset,
                    index = meta.index,
                    ext = meta.ext,
                }
                table.insert(mapping_rows, row)
                per_base[meta.base] = per_base[meta.base] or {}
                table.insert(per_base[meta.base], row)

                if args.dry_run then
                    colour_print("darkgray", string.format("[DRY COPY] %s -> %s", rel, new_rel))
                else
                    copy_with_collision_handling(full, new_path)
                end
            end
            if prog then prog:Update(1) end
        end

        -- Sort rows
        table.sort(mapping_rows, function(a,b)
            if a.base == b.base then return a.original_path < b.original_path end
            return a.base < b.base
        end)
        for _,rows in pairs(per_base) do
            table.sort(rows, function(a,b) return a.original_path < b.original_path end)
        end

        -- Write JSON outputs into args.dst
        local map_json = join(args.dst, "flatten_map.json")
        write_all_text(map_json, json_encode(mapping_rows, true))

        local created = {}
    for base, rows in pairs(per_base) do
        local safe = sanitize_filename(base)
        local per_path = join(args.dst, string.format("flatten_map_%s.json", safe))
        write_all_text(per_path, json_encode(rows, true))
        table.insert(created, basename(per_path))
    end

        local summary = { total_assets = total, bases = {}, files_written = {} }
        for base, rows in pairs(per_base) do summary.bases[base] = #rows end
        summary.files_written = { basename(map_json) }
        for _,n in ipairs(created) do table.insert(summary.files_written, n) end
        write_all_text(join(args.dst, "flatten_map_summary.json"), json_encode(summary, true))

        print("")
        print(string.format("Found %d assets.", total))
        print(string.format("JSON mapping written to: %s", map_json))
        if #created > 0 then
            print("Per-base maps:")
            for _,name in ipairs(created) do print("  - " .. name) end
            print(string.format("Summary: %s", join(args.dst, "flatten_map_summary.json")))
        end
    end)

    -- finalize progress panel (stop background spinner) regardless of success
    if prog then prog:Complete() end
    if not ok then error(err) end
end

-- run
main()
