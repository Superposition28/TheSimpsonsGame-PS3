# SPDX-License-Identifier: MIT
"""
Main entry point for The Simpsons Game Blender Addon.
Handles addon registration, unregistration, and UI menu integration.
"""

import bpy

from . import bl_info as bl_info_helper
from .Core.MyAddonPreferences import MyAddonPreferences
from .Core.SimpGameImport import SimpGameImport, menu_func_import
from .materials import clear_material_cache
from .utils.logger import bPrinter

# Get values from TOML
_manifest = bl_info_helper.get_manifest_data()

bl_info = {
    "name": _manifest.get("name", "The Simpsons Game 3d Asset Importer"),
    "author": _manifest.get("maintainer", "Turk & Mister_Nebula & Samarixum"),
    "version": bl_info_helper.get_version_tuple(_manifest.get("version", "1.5.8")),
    "blender": bl_info_helper.get_version_tuple(_manifest.get("blender_version_min", "4.0.0")),
    "location": "File > Import-Export",
    "description": _manifest.get("tagline", ""),
    "category": "Import-Export",
}

classes = (
    SimpGameImport,
    MyAddonPreferences,
)

def register() -> None:
    """
    Registers the addon classes and appends the import menu item.
    """
    bPrinter("[Register] Registering addon components")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister() -> None:
    """
    Unregisters the addon classes and removes the import menu item.
    """
    bPrinter("[Unregister] Unregistering addon components")

    # Clear global caches on unregister
    try:
        clear_material_cache()
    except Exception as e:
        bPrinter(f"[Unregister] Warning clearing material cache: {e}", to_blender_editor=True)

    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception as e:
        bPrinter(f"[Unregister] Warning removing menu item: {e}", to_blender_editor=True)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:
            bPrinter(f"[Unregister] Warning unregistering class {cls.__name__}: {e}", to_blender_editor=True)

if __name__ == "__main__":
    register()


