-- Organize generated audio using the maintained AudioMap V2 registry.
-- Operation 4 passes --execute; direct script calls default to a dry run.
---@type AudioV2Runtime
local Audio = import("Audio/AudioV2.lua")
Audio.Run(argv or {})
