local M = {}

---@return BlenderProcessorModule
function M.setup()
    ---@class PreinstancedFileProcessorOptions
    ---@field input_dir string
    ---@field blend_dir string
    ---@field glb_dir string
    ---@field blank_blend_source string
    ---@field debug_mode_enabled boolean
    ---@field verbose boolean

    ---@class PreinstancedFileProcessor
    ---@field input_dir string
    ---@field blend_dir string
    ---@field glb_dir string
    ---@field blank_blend_source string
    ---@field debug_mode_enabled boolean
    ---@field verbose boolean
    ---@field process_files fun(self: PreinstancedFileProcessor): nil

    ---@class PreinstancedFileProcessorClass
    ---@field new fun(opts: PreinstancedFileProcessorOptions): PreinstancedFileProcessor

    ---@class BlenderProcessorModule
    ---@field PreinstancedFileProcessor PreinstancedFileProcessorClass

    local PreinstancedFileProcessor = {}
    PreinstancedFileProcessor.__index = PreinstancedFileProcessor

    ---@param opts PreinstancedFileProcessorOptions
    ---@return PreinstancedFileProcessor
    function PreinstancedFileProcessor.new(opts)
        local self = setmetatable({}, PreinstancedFileProcessor)
        self.input_dir = absolute_path(opts.input_dir)
        self.blend_dir = absolute_path(opts.blend_dir)
        self.glb_dir = absolute_path(opts.glb_dir)
        self.blank_blend_source = absolute_path(opts.blank_blend_source)
        self.debug_mode_enabled = not not opts.debug_mode_enabled
        self.verbose = not not opts.verbose
        ---@cast self PreinstancedFileProcessor
        return self
    end

    ---@return nil
    function PreinstancedFileProcessor:process_files()
        if not sdk.is_dir(self.input_dir) then
            log(Colours.RED, string.format("InputDirectory '%s' is not set or does not exist.", self.input_dir))
            error(string.format("InputDirectory '%s' is not set or does not exist.", self.input_dir))
        end
        if not self.blend_dir then
            log(Colours.RED, "BlendDirectory is not set.")
            error("BlendDirectory is not set.")
        end
        sdk.ensure_dir(self.blend_dir)
        if not self.glb_dir then
            log(Colours.RED, "GLBOutputDirectory is not set.")
            error("GLBOutputDirectory is not set.")
        end
        sdk.ensure_dir(self.glb_dir)
        if not sdk.is_file(self.blank_blend_source) then
            log(Colours.RED, string.format("BlankBlendSource '%s' is not set or does not exist.", self.blank_blend_source))
            error(string.format("BlankBlendSource '%s' is not set or does not exist.", self.blank_blend_source))
        end

        local files = {}
        local map_file_path = join(self.input_dir, "normalized_map.json")
        if sdk.is_file(map_file_path) then
            log(Colours.CYAN, string.format("Using normalized_map.json from %s", self.input_dir))
            local fh = io.open(map_file_path, "r")
            if fh then
                ---@cast fh FileHandle
                local map_content = fh:read("*a")
                fh:close()
                local map_data = sdk.text.json.decode(map_content)
                if map_data then
                    for _, entry in ipairs(map_data) do
                        ---@class BlenderProcessorNormalizedMapEntry
                        ---@field new_path string|nil
                        ---@cast entry BlenderProcessorNormalizedMapEntry
                        local new_path = entry.new_path
                        if new_path and ends_with(new_path:lower(), ".preinstanced") then
                            local full_path = join(self.input_dir, new_path)
                            table.insert(files, full_path)
                        end
                    end
                end
            end
        else
            ---@param full_path string
            ---@param filename string
            iterate_files(self.input_dir, function(full_path, filename)
                if ends_with(filename:lower(), ".preinstanced") then
                    table.insert(files, full_path)
                end
            end)
        end

        log(Colours.CYAN, string.format("Found %d .preinstanced files in %s.", #files, self.input_dir))
        local input_dir_abs = self.input_dir

        for _, preinst_path in ipairs(files) do
            if self.verbose then
                log(Colours.CYAN, string.format("Processing preinstanced file: %s", preinst_path))
            end

            local rel = normalize(preinst_path):sub(#input_dir_abs + 2)
            -- Replace heavy Lua pattern with simple last-separator search
            local rel_ns = normalize(rel)
            local last_sep = 0
            for i = 1, #rel_ns do
                local ch = rel_ns:sub(i,i)
                if ch == '/' or ch == '\\' then last_sep = i end
            end
            local rel_dir = last_sep > 0 and rel_ns:sub(1, last_sep - 1) or nil
            local blend_dest_dir = rel_dir and join(self.blend_dir, rel_dir) or self.blend_dir
            local glb_dest_dir = rel_dir and join(self.glb_dir, rel_dir) or self.glb_dir

            sdk.ensure_dir(blend_dest_dir)
            sdk.ensure_dir(glb_dest_dir)

            -- Derive base name without using complex patterns
            local fn_ns = normalize(preinst_path)
            local last2 = 0
            for i = 1, #fn_ns do
                local ch = fn_ns:sub(i,i)
                if ch == '/' or ch == '\\' then last2 = i end
            end
            local fname = last2 > 0 and fn_ns:sub(last2 + 1) or fn_ns
            local suffix = '.preinstanced'
            local base_name = fname
            if #fname > #suffix and fname:sub(#fname - #suffix + 1):lower() == suffix then
                base_name = fname:sub(1, #fname - #suffix)
            end
            local blend_dest_filename = base_name .. ".blend"
            local blend_dest_full_path = join(blend_dest_dir, blend_dest_filename)

            if not sdk.is_file(blend_dest_full_path) then
                local copied = sdk.copy_file and sdk.copy_file(self.blank_blend_source, blend_dest_full_path, false)
                if copied then
                    if self.verbose then
                        log(Colours.CYAN, string.format("Copied %s to %s", self.blank_blend_source, blend_dest_full_path))
                    end
                else
                    log(Colours.RED, string.format("Error copying blank blend file to '%s'", blend_dest_full_path))
                    if self.debug_mode_enabled then
                        sdk.sleep(1)
                    end
                end
            end

            if self.debug_mode_enabled then
                sdk.sleep(0.05)
            end
        end

        log(Colours.GREEN, string.format("Total .preinstanced files processed for blend/glb structure setup: %d", #files))
    end

    local module = {
        PreinstancedFileProcessor = PreinstancedFileProcessor
    }
    ---@cast module BlenderProcessorModule
    return module
end

return M
