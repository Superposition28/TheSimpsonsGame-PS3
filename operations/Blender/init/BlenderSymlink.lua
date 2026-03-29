local M = {}


---@param Utils BlenderUtils
function M.setup(Utils)
    local lib = {}

    function lib.create_symlink_entry(src, dst, is_dir, debug_sleep_duration, verbose)
        if verbose then
            Utils.log(Utils.Colours.CYAN, string.format("Creating symlink: %s -> %s", dst, src))
        end

        local parent = Utils.parent_dir(dst)
        if parent then
            sdk.ensure_dir(parent)
        end

        local success = sdk.create_symlink(src, dst, is_dir, true)
        if not success then
            Utils.log(Utils.Colours.RED, string.format("Failed to create symlink: %s -> %s", dst, src))
            return false
        end

        if debug_sleep_duration and debug_sleep_duration > 0 then
            sdk.sleep(debug_sleep_duration)
        end
        return true
    end

    function lib.verify_symlink(link_folder_path, src_folder_path, asset_id, link_type_name, verbose)
        if not sdk.path_exists(link_folder_path) then
            if verbose then
                Utils.log(Utils.Colours.YELLOW, string.format("Symlink missing: %s", link_folder_path))
            end
            return false
        end
        return true
    end

    function lib.create_symbolic_links(db, root_drive, preinstanced_root, blend_root, marker, glb_root, debug_mode_enabled, verbose)
        Utils.log(Utils.Colours.CYAN, "--- Creating Symbolic Links on Root Drive ---")
        Utils.log(Utils.Colours.CYAN, "Root Drive: " .. (root_drive or "NOT SET"))

        if not root_drive or root_drive == "" then
            Utils.log(Utils.Colours.YELLOW, "Warning: root_drive is not set. Skipping symlink creation.")
            return
        end

        -- Query distinct identifiers and their source folders
        local rows = db.query("SELECT DISTINCT identifier, preinstanced_full, preinstanced_symlink FROM asset_map")

        for _, row in ipairs(rows) do
            if row.preinstanced_full and row.preinstanced_symlink then
                -- Create a single symlink root for the asset ID
                local src_dir = Utils.parent_dir(row.preinstanced_full)
                if src_dir and not sdk.path_exists(row.preinstanced_symlink) then
                    lib.create_symlink_entry(src_dir, row.preinstanced_symlink, true, debug_mode_enabled and 0.001 or 0, verbose)
                end
            end
        end
        Utils.log(Utils.Colours.GREEN, "Successfully created shared symbolic links.")
    end

    return lib
end

return M
