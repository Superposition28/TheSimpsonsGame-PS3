local M = {}

---@return BlenderSymlinkLib
function M.setup()
    ---@class BlenderSymlinkLib
    ---@field create_symlink_entry fun(src: string, dst: string, is_dir: boolean, debug_sleep_duration: number|nil, verbose: boolean): boolean
    ---@field verify_symlink fun(link_folder_path: string, src_folder_path: string, asset_id: string, link_type_name: string, verbose: boolean): boolean
    ---@field create_symbolic_links fun(db: table, root_drive: string, preinstanced_root: string, blend_root: string, marker: string|nil, glb_root: string|nil, debug_mode_enabled: boolean, verbose: boolean): nil
    local lib = {}

    ---@param src string
    ---@param dst string
    ---@param is_dir boolean
    ---@param debug_sleep_duration number|nil
    ---@param verbose boolean
    ---@return boolean
    function lib.create_symlink_entry(src, dst, is_dir, debug_sleep_duration, verbose)
        if verbose then
            log(Colours.CYAN, string.format("Creating symlink: %s -> %s", dst, src))
        end

        local parent = parent_dir(dst)
        if parent then
            sdk.ensure_dir(parent)
        end

        local success = sdk.create_symlink(src, dst, is_dir, true)
        if not success then
            log(Colours.RED, string.format("Failed to create symlink: %s -> %s", dst, src))
            return false
        end

        if debug_sleep_duration and debug_sleep_duration > 0 then
            sdk.sleep(debug_sleep_duration)
        end
        return true
    end

    ---@param link_folder_path string
    ---@param src_folder_path string
    ---@param asset_id string
    ---@param link_type_name string
    ---@param verbose boolean
    ---@return boolean
    function lib.verify_symlink(link_folder_path, src_folder_path, asset_id, link_type_name, verbose)
        if not sdk.path_exists(link_folder_path) then
            if verbose then
                log(Colours.YELLOW, string.format("Symlink missing: %s", link_folder_path))
            end
            return false
        end
        return true
    end

    ---@param db table
    ---@param root_drive string
    ---@param preinstanced_root string
    ---@param blend_root string
    ---@param marker string|nil
    ---@param glb_root string|nil
    ---@param debug_mode_enabled boolean
    ---@param verbose boolean
    ---@return nil
    function lib.create_symbolic_links(db, root_drive, preinstanced_root, blend_root, marker, glb_root, debug_mode_enabled, verbose)
        log(Colours.CYAN, "--- Creating Symbolic Links on Root Drive ---")
        log(Colours.CYAN, "Root Drive: " .. (root_drive or "NOT SET"))

        if not root_drive or root_drive == "" then
            log(Colours.YELLOW, "Warning: root_drive is not set. Skipping symlink creation.")
            return
        end

        -- Query distinct identifiers and their source folders
        local rows = db.query("SELECT DISTINCT identifier, preinstanced_full, preinstanced_symlink FROM asset_map")

        for _, row in ipairs(rows) do
            ---@class AssetMapSymlinkRow
            ---@field identifier string
            ---@field preinstanced_full string|nil
            ---@field preinstanced_symlink string|nil
            ---@cast row AssetMapSymlinkRow
            if row.preinstanced_full and row.preinstanced_symlink then
                -- Create a single symlink root for the asset ID
                local src_dir = parent_dir(row.preinstanced_full)
                if src_dir and not sdk.path_exists(row.preinstanced_symlink) then
                    lib.create_symlink_entry(src_dir, row.preinstanced_symlink, true, debug_mode_enabled and 0.001 or 0, verbose)
                end
            end
        end
        log(Colours.GREEN, "Successfully created shared symbolic links.")
    end

    return lib
end

return M
