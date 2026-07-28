@tool
extends Node3D
class_name NavGraphVisualizer

@export var nav_data: TSGNavGraph :
	set(value):
		nav_data = value
		_update_visuals()

@export_group("Display Settings")
@export var show_nodes: bool = true :
	set(value):
		show_nodes = value
		_update_visuals()

@export var show_edges: bool = true :
	set(value):
		show_edges = value
		_update_visuals()

@export var node_color: Color = Color.CYAN :
	set(value):
		node_color = value
		_update_visuals()
		
@export var edge_color: Color = Color.YELLOW :
	set(value):
		edge_color = value
		_update_visuals()

var mesh_instance: MeshInstance3D

func _ready() -> void:
	_update_visuals()

func _update_visuals() -> void:
	# 1. Clean up the old mesh if it exists
	if mesh_instance:
		mesh_instance.queue_free()
		mesh_instance = null
		
	# 2. Don't draw if we have no data or everything is hidden
	if not nav_data or (not show_nodes and not show_edges):
		return
		
	# 3. Set up a new MeshInstance and Material
	mesh_instance = MeshInstance3D.new()
	add_child(mesh_instance)
	
	var immediate_mesh = ImmediateMesh.new()
	mesh_instance.mesh = immediate_mesh
	
	var material = StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED # Glows in the dark!
	material.no_depth_test = true # Draws on top of the world so it's not hidden inside geometry
	mesh_instance.material_override = material
	
	immediate_mesh.clear_surfaces()
	
	# 4. Draw Edges as straight lines
	if show_edges and nav_data.edges.size() > 0:
		immediate_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
		for edge in nav_data.edges:
			var idx_a = edge["a"]
			var idx_b = edge["b"]
			
			# Ensure the indices actually exist in our node array
			if idx_a < nav_data.nodes.size() and idx_b < nav_data.nodes.size():
				var pos_a = nav_data.nodes[idx_a]["pos"]
				var pos_b = nav_data.nodes[idx_b]["pos"]
				
				immediate_mesh.surface_set_color(edge_color)
				immediate_mesh.surface_add_vertex(pos_a)
				immediate_mesh.surface_set_color(edge_color)
				immediate_mesh.surface_add_vertex(pos_b)
		immediate_mesh.surface_end()
		
	# 5. Draw Nodes as 3D crosses (easier to see than single points)
	if show_nodes and nav_data.nodes.size() > 0:
		immediate_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
		var size = 0.5 # Adjust how large the cross is here
		for node in nav_data.nodes:
			var pos = node["pos"]
			
			immediate_mesh.surface_set_color(node_color)
			
			# X Axis Line
			immediate_mesh.surface_add_vertex(pos + Vector3(-size, 0, 0))
			immediate_mesh.surface_add_vertex(pos + Vector3(size, 0, 0))
			# Y Axis Line
			immediate_mesh.surface_add_vertex(pos + Vector3(0, -size, 0))
			immediate_mesh.surface_add_vertex(pos + Vector3(0, size, 0))
			# Z Axis Line
			immediate_mesh.surface_add_vertex(pos + Vector3(0, 0, -size))
			immediate_mesh.surface_add_vertex(pos + Vector3(0, 0, size))
		immediate_mesh.surface_end()
