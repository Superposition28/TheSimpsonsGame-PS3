-- Shared domain types for global imports; this file has no executable entry point.

---@class VariantOptions
---@field Project string
---@field Assets string
---@field Source string|nil
---@field Logos string|nil
---@field Godot string|nil
---@field Output string
---@field Work string
---@field Collision boolean
---@field DryRun boolean
---@field Clean boolean
---@field Help boolean

---@class VariantBlock
---@field Header string
---@field Body string

---@class VariantDisabled
---@field scene string|nil
---@field file string|nil
---@field node string|nil
---@field resource string|nil
---@field canonical_path string|nil
---@field reason string

---@class VariantCollision
---@field scene string
---@field node string
---@field asset string
---@field uid string|nil
---@field status string

---@class VariantJob
---@field uid string
---@field source string
---@field source_hash string SHA-256, populated by hash_jobs.gd before baking.
---@field canonical_path string
---@field output string

---@class VariantAttachment
---@field scene string
---@field node string
---@field uid string

---@class VariantSceneInstance
---@field scene string
---@field node string
---@field asset string

---@class VariantBakeResult
---@field uid string
---@field ok boolean
---@field source_hash string|nil
---@field error string|nil
---@field physics_shapes integer|nil
---@field stats table<string, any>|nil
---@field warnings string[]|nil

---@class VariantBakeResults
---@field jobs VariantBakeResult[]

---@class VariantValidation
---@field failures string[]
---@field scenes integer
---@field physics_bodies integer

---@class VariantReport
---@field schema_version integer
---@field canonical_project string
---@field assets string
---@field source string
---@field logos string
---@field collision_enabled boolean
---@field disabled VariantDisabled[]
---@field collisions VariantCollision[]
---@field warnings string[]
---@field bake_results VariantBakeResults|nil
---@field asset_files_copied integer|nil

---@class VariantBuilder
---@field Project string
---@field Assets string
---@field Source string|nil
---@field Logos string
---@field Collision boolean
---@field ByUid table<string, GodotAssetMapping[]>
---@field CollisionByDirectory table<string, GodotAssetMapping[]>
---@field SourceEntries table<string, GodotAssetMapping[]>|nil
---@field Report VariantReport
---@field Materialized table<string, boolean>
---@field Jobs table<string, VariantJob>
---@field Attachments VariantAttachment[]
---@field SceneInstances VariantSceneInstance[]
---@field Preview boolean

---@class VariantResource
---@field Resolved string|nil
---@field Reason string
---@field Original string

---@class VariantReference
---@field Kind string ExtResource or SubResource.
---@field Id string
