# The Simpsons Game (2007) Asset Extraction Tool

## Overview


## Features

*   **Automated Initialization:** Attempts to Sets up the necessary environment and tools for the extraction processes.
*   **Asset Conversion:**         Converts extracted files (audio, video, textures, 3D models) into more compatible modern formats.
## "Tools" - Module,
*   "STR Archive Extraction" - Extract,    Extracts Asset files, 3d, texture, etc from .str archives using [QuickBMS](https://aluigi.altervista.org/quickbms.htm) with [Simpsons Str - Simpsons Game STR . dk2 . SToc . 0x10fb \[simpsons_str.bms\]](https://aluigi.altervista.org/bms/simpsons_str.bms)
*   "Directory restructuring"               changes base folder names and directory structure to be more human.
*   "Audio Conversion" - Audio,             converts .snu audio files into .wav using [vgmstream-cli r1980](https://github.com/vgmstream/vgmstream/releases/tag/r1980)
*   "Video Conversion" - Video,             converts .vp6 movie files into .ogv using [FFmpeg](https://www.ffmpeg.org/download.html)
*   "Blender" - Model,                      converts .rws.PS3.preinstanced & .dff.PS3.preinstanced 3D models into .blend files, optionally generates .glb or .fbx assets
*   "Texture Extraction" - Texture,         extracts textures from the .txd files using Noesis, requires some manual input.
*   "Godot test" - Godot                    generates basic godot game with .blend assets imported and auto assigned to nodes to make a game world preview, no textures
*   "Asset Registry"                        indexes all assets and attempts to define relation ships between files, like textures and models
*   "Auto Repair"                           uses preset fix files and manually created maps to fix issues like broken UV maps in assets, and better define relation ships

## prerequisites

ensure windows long paths are enabled



## Dependencies

* python
* ffmpeg
* vgmstream-cli


## Getting Started

Clone the repo with submodules:

```pwsh
git clone https://github.com/Superposition28/RemakeEngine.git
```


# how to

just run main.py



## Obligatory Legal Disclaimer

**Please read this disclaimer carefully before using this project.**

This project provides code that automates the process of extracting assets (3D models, sounds, and videos) from variouse games. It is intended for personal use only, Ie:.. hobby projects, learning purposes, research, etc .. nothing commercial or distributed.

**Key Points to Understand:**

*   **Requires Ownership of the Game:** This tool requires you to possess your own legally obtained ISO copy of game for the PlayStation 3. It does not provide access to the game files themselves.
*   **Respect Copyright:** The assets extracted from game are copyrighted by Electronic Arts (EA) and Disney. This tool is provided solely to facilitate personal exploration and modification of assets from a game you legally own. You are solely responsible for ensuring your use of these assets complies with all applicable copyright laws and the game's End User License Agreement (EULA) or Terms of Service.
*   **No Distribution of Assets:** This project does not involve the distribution of any copyrighted game assets. It only provides the code to automate the extraction process from your own game files.
*   **Compliance with Takedown Requests:** The developer of this project respects the intellectual property rights of EA and Disney. If either Electronic Arts or Disney (or their legal representatives) requests the removal of this code, the developer will promptly comply.

**By using this project, you acknowledge that you have read and understood this disclaimer and agree to use it responsibly and in accordance with all applicable laws and terms of service.**


# DO NOT USE THIS FOR COMMERCIAL PURPOSES OR DISTRIBUTE ANY EXTRACTED ASSETS WITHOUT PERMISSION FROM THE COPYRIGHT HOLDERS.
