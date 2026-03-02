-- RemakeEngine config manager for [[placeholders]] in config.toml
-- Single, safe implementation: updates only the targeted key and preserves everything else.
-- Runtime guarantees: sdk (with TOML helpers) and argv are provided by engine


local function usage(msg)
    if msg then print(msg .. "\n") end
    print([[Usage:
    lua config.lua [--list] [--config <path>] [--group <name>] [--index <n>] [--key <k>] [--value <v>] [--type <hint>] [--set "key=value[:type]"]...

Options:
    -g, --group        Target section (default: placeholders)
    -k, --key          Key to set within the section
    -v, --value        Value to assign to the key
    -t, --type         Optional type hint: string|boolean|integer|float|auto (default: auto)
    -i, --index        Optional array index (default: 1)
    -c, --config       Override config.toml path (default: <this dir>/config.toml)
    -s, --set          Repeatable multi-set entry in the form key=value[:type].
                        Example: --group placeholders --set STROUT=STROUT_Normalized:string --set Type=normalized:string
    -l, --list         List current sections and keys without modifying the file
    -h, --help         Show this message
]])
end

local function parse_args(list)
    local opts = { group = 'placeholders', index = 1, type_hint = 'auto', sets = {} }
    local i = 1
    while i <= #list do
        local a = list[i]
        if a == '-h' or a == '--help' then opts.help = true
        elseif a == '-l' or a == '--list' then opts.list = true
        elseif a == '-g' or a == '--group' then i = i + 1; opts.group = list[i]
        elseif a == '-k' or a == '--key' then i = i + 1; opts.key = list[i]
        elseif a == '-v' or a == '--value' then i = i + 1; opts.value = list[i]
        elseif a == '-t' or a == '--type' then i = i + 1; opts.type_hint = (list[i] or 'auto'):lower()
        elseif a == '-i' or a == '--index' then i = i + 1; opts.index = tonumber(list[i]) or 1
        elseif a == '-c' or a == '--config' then i = i + 1; opts.config_path = list[i]
        elseif a == '-s' or a == '--set' then i = i + 1; table.insert(opts.sets, list[i])
        end
        i = i + 1
    end
    return opts
end

local function as_string(v)
    local t = type(v)
    if t == 'string' then return v
    elseif t == 'boolean' then return v and 'true' or 'false'
    elseif t == 'number' then return tostring(v)
    elseif v == nil then return 'nil' end
    return '<' .. t .. '>'
end

local function convert_value(raw, hint)
    hint = (hint or 'auto'):lower()
    if hint == 'string' then return raw
    elseif hint == 'boolean' or hint == 'bool' then
        local s = tostring(raw or ''):lower()
        if s == 'true' or s == '1' or s == 'yes' or s == 'y' then return true end
        if s == 'false' or s == '0' or s == 'no' or s == 'n' then return false end
        error("Value '" .. tostring(raw) .. "' cannot be parsed as boolean")
    elseif hint == 'integer' or hint == 'int' then
        local n = tonumber(raw)
        if not n or n % 1 ~= 0 then error("Value '" .. tostring(raw) .. "' is not an integer") end
        return n
    elseif hint == 'float' or hint == 'number' or hint == 'double' then
        local n = tonumber(raw)
        if not n then error("Value '" .. tostring(raw) .. "' is not a number") end
        return n
    elseif hint ~= 'auto' then
        error("Unknown type hint '" .. tostring(hint) .. "'")
    end
    -- auto
    local s = tostring(raw or '')
    local sl = s:lower()
    if sl == 'true' or sl == 'false' then return sl == 'true' end
    local n = tonumber(s)
    if n then return n end
    return s
end


local function list_doc(cfg_path, doc)
    print('Config file: ' .. cfg_path)
    local printed = false
    for k, v in pairs(doc) do
        if type(v) == 'table' then
            if v[1] and type(v[1]) == 'table' then
                for idx, entry in ipairs(v) do
                    print(string.format('[[%s]] (entry %d)', k, idx))
                    for ek, ev in pairs(entry) do
                        print(string.format('    %s = %s', tostring(ek), as_string(ev)))
                    end
                end
                printed = true
            else
                print('[' .. tostring(k) .. ']')
                for ek, ev in pairs(v) do
                    print(string.format('    %s = %s', tostring(ek), as_string(ev)))
                end
                printed = true
            end
        end
    end
    if not printed then print('No sections found yet.') end
end


local function parse_set_token(token)
    -- token form: key=value[:type]
    if not token or token == '' then return nil end
    local eq = token:find('=')
    if not eq then return nil end
    local key = token:sub(1, eq - 1)
    local rest = token:sub(eq + 1)
    -- Detect optional trailing :type only if it matches a known type word
    local type_hint
    local colon = rest:match(':(%a+)$')
    if colon then
        local t = colon:lower()
        if t == 'string' or t == 'boolean' or t == 'bool' or t == 'integer' or t == 'int' or t == 'float' or t == 'number' or t == 'double' or t == 'auto' then
            type_hint = t
            rest = rest:sub(1, #rest - (#colon + 1))
        end
    end
    return { key = key, value = rest, type_hint = type_hint }
end


local function ensure_group_entry(doc, group, index)
    local g = doc[group]
    if g == nil then
        -- create an array-of-tables up to requested index
        g = {}
        doc[group] = g
    end

    if g[1] ~= nil then
        -- already an array-of-tables
        while #g < (index or 1) do table.insert(g, {}) end
        return g[index or 1]
    end

    -- single table
    if (index or 1) == 1 then
        return g
    end
    -- wrap existing single table into array and extend
    local arr = { g }
    doc[group] = arr
    while #arr < index do table.insert(arr, {}) end
    return arr[index]
end


local function main()
    if not sdk or not sdk.toml_read_file or not sdk.toml_write_file then
        error('SDK TOML helpers unavailable - engine integrity issue')
        Diagnostics.Trace('SDK TOML helpers unavailable - engine integrity issue')
    end

    local opts = parse_args(argv)
    -- Handle help request
    if opts.help then usage(); return 0 end

    local base = script_dir
    local cfg_path = opts.config_path or (base .. '/config.toml')

    -- Read existing document; if it fails, abort rather than creating a new one implicitly
    local doc = sdk.toml_read_file(cfg_path)
    if not doc or type(doc) ~= 'table' then
        error('Failed to read existing config.toml at ' .. cfg_path .. '; refusing to overwrite.')
    end

    if opts.list or (not opts.group and not opts.key and not opts.value) then
        Diagnostics.Trace('Listing config.toml contents at ' .. cfg_path)
        list_doc(cfg_path, doc)
        return 0
    end

    -- Multi-set mode if any --set tokens are provided
    if opts.sets and #opts.sets > 0 then
        local target = ensure_group_entry(doc, opts.group, opts.index)
        for _,tok in ipairs(opts.sets) do
            local parsed = parse_set_token(tok)
            if parsed and parsed.key and parsed.value ~= nil then
                local ok, conv = pcall(convert_value, parsed.value, parsed.type_hint or opts.type_hint)
                if not ok then
                    error('Value conversion failed: ' .. tostring(conv))
                end
                target[parsed.key] = conv
                local msg = string.format('Updated %s[%d].%s = %s', opts.group, opts.index or 1, parsed.key, as_string(conv))
                sdk.colour_print({ colour = 'green', message = msg })
            end
        end
        sdk.toml_write_file(cfg_path, doc)
        Diagnostics.Trace('Performed multi-set updates to config.toml at ' .. cfg_path)
        return 0
    end

    -- Single-set mode
    if not opts.group or not opts.key then
        usage('Missing --group/--key for set operation')
        Diagnostics.Trace('Missing --group/--key for set operation')
        return 1
    end
    if opts.value == nil then
        usage('Missing --value for set operation')
        Diagnostics.Trace('Missing --value for set operation')
        return 1
    end

    local ok, newValue = pcall(convert_value, opts.value, opts.type_hint)
    if not ok then
        error('Value conversion failed: ' .. tostring(newValue))
        Diagnostics.Trace('Value conversion failed: ' .. tostring(newValue))
    end

    local target = ensure_group_entry(doc, opts.group, opts.index)
    target[opts.key] = newValue

    -- Persist entire document as-is, only the targeted key changed
    sdk.toml_write_file(cfg_path, doc)

    Diagnostics.Trace(string.format('Updated %s[%d].%s = %s in config.toml at %s', opts.group, opts.index or 1, opts.key, as_string(newValue), cfg_path))
    sdk.colour_print({ colour = 'green', message = string.format('Updated %s[%d].%s = %s', opts.group, opts.index or 1, opts.key, as_string(newValue)) })
    return 0
end

-- execute main and exit with its return code
os.exit(main())


