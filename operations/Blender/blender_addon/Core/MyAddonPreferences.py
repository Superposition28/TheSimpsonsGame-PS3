"""
Defines the addon preferences for The Simpsons Game Blender Addon, including a debug mode toggle and UI drawing method.
"""
# SPDX-License-Identifier: MIT
import bpy

class MyAddonPreferences(bpy.types.AddonPreferences):
    """
    Blender Addon Preferences for The Simpsons Game Importer. Provides a toggle for debug mode to enable additional logging and diagnostics.
    """
    bl_idname = __package__.split(sep='.', maxsplit=1)[0] if __package__ else __name__
    debugmode: bpy.props.BoolProperty(
        name="Debug Mode",
        description="Enable or disable debug mode",
        default=False
    )
    def draw(self, _context: bpy.types.Context) -> None:
        """Draw the addon preferences UI."""
        layout = self.layout
        layout.prop(self, "debugmode")
