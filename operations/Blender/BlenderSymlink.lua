local M = {}

function M.setup(Utils)
    local lib = {}

    -- Symlink creation is no longer required as of Blender 4.5+ which supports long paths (\\?\)
    -- These functions are kept as stubs for compatibility if needed.

    function lib.create_symlink_entry(src, dst, is_dir, debug_sleep_duration, verbose)
        return true
    end

    function lib.verify_symlink(link_folder_path, src_folder_path, asset_id, link_type_name, verbose)
        return true
    end

    function lib.create_symbolic_links(db, root_drive, debug_mode_enabled, verbose)
        Utils.log(Utils.Colours.CYAN, "Skipping symbolic link creation (deprecated in favor of full paths).")
    end

    return lib
end

return M
