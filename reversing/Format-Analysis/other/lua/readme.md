

## README — Original PS3 Lua files for "The Simpsons Game"

Purpose
-------
This document explains the purpose of the three original `.lua` files used by the PS3 release of "The Simpsons Game". It documents what each original game Lua file does, how `.lua` scripts are typically used by the game engine, and how those scripts interact. No copyrighted source code from EA is reproduced here — this README only summarizes structure and behavior.

Copyright / Ownership WARNING
-----------------------------
The Lua source files referenced here are copyrighted and owned by Electronic Arts (EA). Do not redistribute or publish the original source text from these files without explicit permission from the copyright holder.

Files and their roles
---------------------
- `simpsons_scores.lua`
	- Role: Defines the entire scoring system for the game. It installs score objects, score events, watchers, and gates (AND/OR/NAND/NOT) that implement episode gating, achievements, costume unlocks, tutorial/tracker behaviour, and other game-state driven logic.
	- Key responsibilities (summary):
		- Acquire the ScoreKeeper instance and set scoring version.
		- Create and register scores (global/session), score events, and message watchers.
		- Build episode helpers (episode completion, challenge scoring, cliches/collectibles) and gating logic that controls episode availability.
		- Provide helper functions for building gates and composite score logic (e.g., CreateNandGate, CreateNotGate, EpisodeHelper, CreateCheatEvent).
		- Install the scores by calling setup functions in a defined order and finalizing the installation.

- `simpsons_gameflow.lua`
	- Role: Builds the high-level GameFlow model — episodes, modes, maps, movies, and the relationships between them. In short, this file defines the navigation and structure of the single-player/co-op experiences (which episodes exist, their modes, and which maps/movies/metric screens attach to them).
	- Key responsibilities (summary):
		- Create a Game object and set the active gameflow version.
		- Instantiate Episode objects (with completion and locked-score bindings and cheat-event names), mark root/default episodes, and set episode-level flags (restore positions, disable replay, etc.).
		- Create Mode objects for each episode (standard/timed), attach maps and movies, and add metric screens and entries used by the front-end.
		- Register costumes via the costume registry (ties costume unlock scores to UI entries).

- `simpsons_gameflow_helpers.lua`
	- Role: Small helper/wrapper library used by `simpsons_gameflow.lua` to simplify creating GameFlow objects (Game, Episode, Mode, Map, Movie, MetricScreen). These helpers take care of allocation and ownership transfer semantics the game engine expects when constructing package objects from Lua.
	- Key responsibilities (summary):
		- Provide NewGame, NewEpisode, NewMode, NewMovie, NewMap, NewMetricScreen convenience functions.
		- Wrap engine package creation calls and handle ownership (the engine's tolua wrapper semantics), then add objects to their parent containers.

.lua extension usage in this project
----------------------------------
- Purpose: The `.lua` files here are runtime scripts used by the game engine to define data-driven configurations (gameflow model) and gameplay logic (scores / achievements / unlocks). The engine exposes host objects (ScoreKeeper, GameFlowManager, package constructors, registries) to Lua and the scripts call into those APIs to register and configure behavior.
- Typical runtime pattern observed in these files:
	- Initialization functions named `Setup*` (e.g., `SetupEpisodeScores`, `SetupGame`) build and register objects in a specific order.
	- Helper functions encapsulate repeated construction patterns (gates, episodes, maps, metric screens) to keep the primary setup code readable.
	- Scripts follow a deterministic load/install sequence and call an engine-provided Begin/Finalize installation lifecycle when available.
- Where they fit: These Lua scripts are data/configuration scripts rather than standalone applications. They are expected to be loaded by the game engine during startup (or when the relevant content module is loaded), not invoked directly as external programs.

How the three files interact
---------------------------
- `simpsons_gameflow_helpers.lua` provides constructor helpers used by `simpsons_gameflow.lua` when building the GameFlow structure.
- `simpsons_gameflow.lua` defines episodes, modes, and costume registrations; it references score names and events that are created and managed by `simpsons_scores.lua`.
- `simpsons_scores.lua` creates the score objects and score events that drive gating, achievements, unlocks, and the cheat cascade referenced by the gameflow entries and UI.


Where these original files are located
------------------------------------------------------------------
The three Lua files this README documents come from the original PS3 game and would normally live in the game's USRDIR folder (shipped with the game's data).

