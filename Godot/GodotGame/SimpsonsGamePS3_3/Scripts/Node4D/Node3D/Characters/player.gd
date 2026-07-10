## Path: Node4D/Node3D/Characters/player.gd
## Binding, bound to 4D/Node3D/Characters/player.tscn
##
## default Player character controller
##
##
##
##

extends CharacterBody3D

@export_category("Player Movement")
@export var speed := 5.0
@export var jump_velocity := 4.5
const ROTATION_SPEED := 6.0

@onready var camera_pivot : Node3D = $camera_pivot
@onready var playermodel : Node3D = $playermodel
@onready var animation_player : AnimationPlayer = $"playermodel/character-male-e/AnimationPlayer"

enum animation_state {IDLE, RUNNING, JUMPING}
var player_animation_state : animation_state = animation_state.IDLE

func _ready() -> void:
    # Expose this node so console commands can find the player.
    add_to_group("player")

func _physics_process(delta: float) -> void:
    # With tree paused during console, physics still runs for bodies if required.
    # --- Gravity logic is unchanged ---
    if not is_on_floor():
        velocity += get_gravity() * delta

    # --- Movement logic now reads from CVars, not the Input singleton ---
    var forward_axis := 0.0
    var right_axis := 0.0
    var vf = Console.get_cvar("player.move.forward")
    var vr = Console.get_cvar("player.move.right")
    if vf != null:
        forward_axis = float(vf)
    if vr != null:
        right_axis = float(vr)

    var input_dir := Vector2(right_axis, forward_axis)
    var direction = (camera_pivot.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()
    
    if direction:
        velocity.x = direction.x * speed
        velocity.z = direction.z * speed
        rotate_model(direction, delta)
        player_animation_state = animation_state.RUNNING
    else:
        velocity.x = move_toward(velocity.x, 0, speed)
        velocity.z = move_toward(velocity.z, 0, speed)
        player_animation_state = animation_state.IDLE

    # --- Jump logic removed; handled via console command/jump RPC ---

    if not is_on_floor():
        player_animation_state = animation_state.JUMPING

    move_and_slide()
    _play_anim_for_state()

func rotate_model(direction: Vector3, delta : float) -> void:
    playermodel.basis = lerp(playermodel.basis, Basis.looking_at(direction), 10.0 * delta)

func _play_anim_for_state() -> void:
    match player_animation_state:
        animation_state.IDLE:
            animation_player.play("idle")
        animation_state.RUNNING:
            animation_player.play("sprint")
        animation_state.JUMPING:
            animation_player.play("jump")
