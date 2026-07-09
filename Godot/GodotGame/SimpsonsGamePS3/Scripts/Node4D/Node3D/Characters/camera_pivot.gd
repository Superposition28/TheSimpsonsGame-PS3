## Path: Node4D/Node3D/Characters/camera_pivot.gd
## Binding, bound to 4D/Node3D/Characters/camera_pivot.tscn
##
## 
##
##
##
##

extends Node3D

@onready var debug := bool(Console.get_cvar("debug"))

const MOUSE_SENSITIVITY = 0.002
@onready var springarm : Node3D = $SpringArm3D

func _process(_delta: float) -> void:
    if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
        if debug: print("camera_pivot: process skipped, mouse not captured")
        return

    var dx := 0.0
    var dy := 0.0
    var vdx = Console.get_cvar("player.look.dx")
    var vdy = Console.get_cvar("player.look.dy")
    if vdx != null:
        dx = float(vdx)
    if vdy != null:
        dy = float(vdy)

    if dx != 0.0:
        rotate_y(dx * -MOUSE_SENSITIVITY)
    if dy != 0.0:
        springarm.rotation.x = clamp(
            springarm.rotation.x - dy * MOUSE_SENSITIVITY,
            -0.6, 0.6
        )
