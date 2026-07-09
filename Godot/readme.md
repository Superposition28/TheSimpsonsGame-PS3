# Godot Workflow

This folder contains the Godot-side part of the TheSimpsonsGame-PS3 pipeline. The important idea is that the project is not authored directly as a full set of hand-written scenes. Instead, Godot is rebuilt from a small persistent Core template plus JSON scene descriptions at build time.

## Folder Roles

`Godot/Core` is the reusable project template. It contains the persistent files that should remain in source control and survive across rebuilds, including:

- `Core/project.godot` for project-wide settings that should stay stable between builds
- `Core/addons/` for shared plugins and editor extensions
- `Core/Scripts/` for the build-time importer and any shared runtime/editor scripts
- `Core/Json/` for the JSON scene descriptions that define the game layout

The generated Godot project is written under `Godot/GodotGame/<ProjectName>/`. If that folder already exists, the bootstrap appends `_1`, `_2`, and so on to avoid overwriting a previous generated project.

## Build Workflow

The Lua bootstrap script `Godot/godot-init-V0.5.2.lua` is responsible for creating and updating the Godot project. Its workflow is:

1. Resolve the Godot executable.
2. Create the target project folder inside `Godot/GodotGame/<ProjectName>/`.
3. Copy the persistent Core files into the target project so the editor has the expected addons, scripts, and project configuration.
4. Scan the resolved source asset root and copy or link imported game content into `res://assets/`.
5. Run Godot headless to import the generated content.
6. Run the scene-building entrypoint `Godot/Core/Scripts/import-V0.5.2.gd`, which loads `res://addons/remake_pipeline/core/importer_core.gd` and turns the JSON layout into `.tscn` scene files.

That separation is deliberate: the bootstrap script handles orchestration and file staging, while the GDScript importer handles scene construction inside Godot.

## JSON-Driven Layout

The layout of the game is described in `Godot/Core/Json/**/*.json`. These files act as the source of truth for the scene tree.

Each JSON file describes one scene or one branch of a scene tree. The importer reads the JSON, instantiates the requested root node, and then recursively creates children from nested `children` arrays.

Typical fields used by the JSON files include:

- `name` for the node name
- `class` for the Godot class to instantiate when the node is created dynamically
- `path` for the output scene path or resource reference
- `config_file` for nested JSON files that continue the scene definition
- `config` for transforms, layout settings, collision settings, visuals, and other node properties
- `editable_children` when a child instance should remain editable in the saved scene

For example, `Core/Json/Node4D.json` defines the top-level scene and then delegates to child JSON files such as `Node4D/Node2D.json` and `Node4D/Node3D.json`. Those children can continue the tree with their own nested scene definitions, which keeps the layout modular and easy to extend.

## Build-Time Scene Generation

The scene builder lives in `Godot/Core/Scripts/import-V0.5.2.gd`. This script is executed inside Godot during the build, and it is the part that actually converts JSON into Godot scenes.

The importer does the following:

- loads the JSON scene description
- resolves asset paths using `res://assets/normalized_map.json` when available
- instantiates nodes from the JSON `class` and `children` data
- applies transforms, UI layout, collision shapes, textures, and other node config
- saves the finished scene back to disk as `.tscn`

This means the scene files are generated at build time, not edited as the primary source of truth. If a scene needs to change, update the JSON definition and rebuild.

## Static Files vs Generated Files

Not everything in the Godot project needs to be regenerated.

Static or persistent files, such as `Core/project.godot`, can live in the repository and be copied into the output project without being rebuilt from JSON every time. This is useful for editor settings, autoloads, rendering configuration, input maps, and other project-wide behavior that should remain stable across builds.

Generated files, especially scene files, should be produced during the build. That keeps the source layout editable in JSON while allowing the resulting Godot project to be recreated consistently.

## Practical Rule

- Change `Core/project.godot` when you want persistent project configuration.
- Change files under `Core/Json/` when you want to alter the game layout.
- Change `Core/Scripts/import-V0.5.2.gd` when you need to adjust how JSON is converted into scenes.
- Rebuild the Godot project after changing JSON or importer logic so the generated `.tscn` files are refreshed.
