--[[
The Simpsons Game NewGen .LH2 parser to CSV (Lua version)

Usage:
  Called via RemakeEngine operation system with:
  --input-dir "path/to/lh2/files"

Output:
  Generates .csv file alongside each .LH2 file

Converted from Python script by Edness (v1.1)
Lua conversion by samarixum for RemakeEngine
--]]

-- Small utilities -----------------------------------------------------------
---@type SharedUtils
local Utils = import("SharedUtils")

---@class Lh2ToCsvOptions
---@field input_dir string?
---@field input_file string?

-- Utility function to read big-endian uint32
---@param file FileHandle
---@return integer|nil
local function read_uint32_be(file)
    local b1, b2, b3, b4 = file:read(1), file:read(1), file:read(1), file:read(1)
    if not b1 or not b2 or not b3 or not b4 then
        return nil
    end
    -- Use bit operations compatible with Lua 5.1+
    local n1, n2, n3, n4 = b1:byte(), b2:byte(), b3:byte(), b4:byte()
    return n1 * 0x1000000 + n2 * 0x10000 + n3 * 0x100 + n4
end

-- Utility function to read null-terminated string (Windows-1252 encoded)
---@param file FileHandle
---@return string
local function read_string(file)
    ---@type string[]
    local chars = {}
    while true do
        local byte = file:read(1)
        if not byte or byte == "\x00" then
            break
        end
        table.insert(chars, byte)
    end
    return table.concat(chars)
end

-- Utility function to escape CSV field
---@param field any
---@return string
local function escape_csv_field(field)
    if not field then return "" end
    field = tostring(field)
    -- If field contains comma, quote, or newline, wrap in quotes and escape internal quotes
    if field:find('[,"\n]') then
        field = '"' .. field:gsub('"', '""') .. '"'
    end
    return field
end

-- Main LH2 decode function
---@param path string
---@return boolean
local function decode_lh2(path)
    --sdk.colour_print({ colour = 'cyan', message = 'Processing: ' .. path })

    -- Check if file exists
    if not sdk.path_exists(path) then
        Utils.colour_print({ colour = 'red', message = 'Error: File not found: ' .. path })
        return false
    end

    -- Open file for binary reading
    local file = io.open(path, "rb")
    if not file then
        Utils.colour_print({ colour = 'red', message = 'Error: Could not open file: ' .. path })
        return false
    end
    ---@cast file FileHandle

    -- Check Magic Number
    local magic = file:read(4)
    if not magic or #magic ~= 4 then
        Utils.colour_print({ colour = 'red', message = 'Error: Could not read magic number from file: ' .. path })
        file:close()
        return false
    end

    if magic ~= "2HCL" then
        -- Debug output to see what we actually got
        local hex = ""
        for i = 1, #magic do
            hex = hex .. string.format("%02X ", magic:byte(i))
        end
        Utils.colour_print({ colour = 'red', message = string.format('Error: Not a valid .LH2 file (bad magic): %s', path) })
        Utils.colour_print({ colour = 'yellow', message = string.format('  Expected: "2HCL" (32 48 43 4C), Got: "%s" (%s)', magic, hex) })
        file:close()
        return false
    end

    -- Check File Size integrity
    local file_size = read_uint32_be(file)
    local actual_size = file:seek("end")
    file:seek("set", 0)
    local _ = file:read(8) -- Skip magic and size we already read

    if file_size ~= actual_size then
        Utils.colour_print({ colour = 'yellow', message = 'Warning: File size mismatch (header=' .. file_size .. ', actual=' .. actual_size .. ')' })
    end

    -- Read Header Info
    file:seek("set", 0x10)
    local entries = read_uint32_be(file)
    local tables = read_uint32_be(file)

    if not entries or not tables then
        Utils.colour_print({ colour = 'red', message = 'Error: Failed to read header' })
        file:close()
        return false
    end

    --Utils.colour_print({ colour = 'white', message = string.format('  Entries: %d, Tables: %d', entries, tables) })

    -- Skip reserved/runtime pointers (8 bytes at 0x18)
    file:seek("set", 0x20)

    -- Read String IDs (Hashes)
    ---@type integer[]
    local ids = {}
    for i = 1, entries do
        local id = read_uint32_be(file)
        if not id then
            Utils.colour_print({ colour = 'red', message = 'Error: Failed to read string ID at index ' .. i })
            file:close()
            return false
        end
        table.insert(ids, id)
    end

    -- Read Offset Pointers
    -- The pointers are arranged sequentially by table (language/column)
    ---@type table<integer, integer[]>
    local ptr = {}
    for t = 1, tables do
        ptr[t] = {}
        for e = 1, entries do
            local offset = read_uint32_be(file)
            if not offset then
                Utils.colour_print({ colour = 'red', message = 'Error: Failed to read offset pointer' })
                file:close()
                return false
            end
            table.insert(ptr[t], offset)
        end
    end

    -- Read Strings based on offsets
    ---@type table<integer, string[]>
    local txt = {}
    for t = 1, tables do
        txt[t] = {}
        for e = 1, entries do
            local offset = ptr[t][e]
            file:seek("set", offset)
            local str = read_string(file)
            table.insert(txt[t], str)
        end
    end

    file:close()

    -- Prepare CSV Output
    local output_path = path .. ".csv"

    -- Determine column structure
    -- If there is more than 1 table, the last table is usually the internal String Label
    local columns_count = (tables > 1) and (tables - 1) or tables

    -- Open output file
    local out = io.open(output_path, "w")
    if not out then
        Utils.colour_print({ colour = 'red', message = 'Error: Could not create output file: ' .. output_path })
        return false
    end
    ---@cast out FileHandle

    -- Create Header Row
    ---@type string[]
    local header = {"String ID"}
    if tables > 1 then
        table.insert(header, "String Label")
    end

    for x = 1, columns_count do
        table.insert(header, "Language " .. (x - 1))
    end

    -- Write header
    out:write(table.concat(header, ",") .. "\n")

    -- Write Data Rows
    for i = 1, entries do
        ---@type string[]
        local row = {}

        -- Format ID as Hex string
        table.insert(row, escape_csv_field(string.format("%08X", ids[i])))

        if tables > 1 then
            -- If multiple tables, the last one is the label
            table.insert(row, escape_csv_field(txt[tables][i]))
        end

        -- Add the localized text columns
        for x = 1, columns_count do
            table.insert(row, escape_csv_field(txt[x][i]))
        end

        out:write(table.concat(row, ",") .. "\n")
    end

    out:close()

    --sdk.color_print('green', 'Success: Output written to ' .. output_path) too verbose, the progress bar and final summary will cover this
    return true
end

-- Argument parsing
---@param list string[]
---@return Lh2ToCsvOptions
local function parse_args(list)
    ---@type Lh2ToCsvOptions
    local opts = {}
    local i = 1
    while i <= #list do
        local arg = list[i]
        if arg == "--input-dir" then
            i = i + 1
            opts.input_dir = list[i]
        elseif arg == "--input-file" then
            i = i + 1
            opts.input_file = list[i]
        else
            Utils.colour_print({ colour = 'yellow', message = 'Unknown argument: ' .. arg })
        end
        i = i + 1
    end
    return opts
end

-- Main execution
---@return nil
local function main()
    Utils.colour_print({ colour = 'white', message = '=== LH2 to CSV Converter ===' })

    -- Parse command line arguments
    local opts = parse_args(argv or {})

    if opts.input_file then
        -- Single file mode
        local success = decode_lh2(opts.input_file)
        if not success then
            error("Failed to process file: " .. opts.input_file)
        end
    elseif opts.input_dir then
        -- Directory mode - find all .lh2 files
        opts.input_dir = Utils.normalize(opts.input_dir)
        Utils.colour_print({ colour = 'cyan', message = 'Scanning directory: ' .. opts.input_dir })
        Diagnostics.Trace('[lh2_to_csv] Scanning directory: ' .. opts.input_dir)

        if not sdk.path_exists(opts.input_dir) then
            error("Input directory does not exist: " .. opts.input_dir)
        end

        ---@type string[]
        local lh2_files = {}
        Utils.iterate_files(opts.input_dir, function(full_path, entry)
            if entry:lower():match("%.lh2$") then
                table.insert(lh2_files, full_path)
            end
        end)

        local files_found = #lh2_files
        local files_processed = 0

        if files_found == 0 then
            Utils.colour_print({ colour = 'yellow', message = 'No .LH2 files found in directory' })
            return
        end

        Utils.colour_print({ colour = 'white', message = string.format('Found %d .LH2 files. Starting conversion...', files_found) })

        local prog = progress.new(files_found, "lh2-csv", "Converting LH2 to CSV")

        for _, path in ipairs(lh2_files) do
            if decode_lh2(path) then
                files_processed = files_processed + 1
            end
            if prog then prog:Update(1) end
        end

        if prog then prog:Complete() end

        Utils.colour_print({ colour = 'white', message = '=== Processing Complete ===' })
        Utils.colour_print({ colour = 'cyan', message = string.format('Files found: %d', files_found) })
        Utils.colour_print({ colour = 'green', message = string.format('Files processed: %d', files_processed) })
        Diagnostics.Trace(string.format('[lh2_to_csv] Processed %d/%d files', files_processed, files_found))

        if files_processed < files_found then
            error(string.format("Some files failed to process (%d/%d)", files_processed, files_found))
        end
    else
        error("Usage: --input-dir <directory> or --input-file <file.lh2>")
    end
end

-- Execute main function
main()
