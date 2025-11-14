bl_info = {
    "name": "Import The Simpsons Game NavGraph (.graph)",
    "author": "samarixum",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "File > Import > The Simpsons Game NavGraph (.graph)",
    "description": "Import navigation graph files from The Simpsons Game (.graph)",
    "category": "Import-Export",
}

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import Vector
import os
import struct

def tsg_to_blender(x, y, z):
    # OPTION A: swap Y and Z (common when one system is Y-up, the other Z-up)
    return Vector((x, z, y))
# ----------------- LOW-LEVEL PARSER -----------------

def _u32_be(data, offset):
    return int.from_bytes(data[offset:offset+4], "big", signed=False)


def _u16_be(data, offset):
    return int.from_bytes(data[offset:offset+2], "big", signed=False)


def _i16_be(data, offset):
    return int.from_bytes(data[offset:offset+2], "big", signed=True)


def _f32_be(data, offset):
    return struct.unpack(">f", data[offset:offset+4])[0]


def _guid_str_from_header(data):
    # GUID is at 0x10..0x1F, big-endian, same order as filename
    g = data[0x10:0x20]
    if len(g) != 16:
        return None
    h = g.hex().upper()
    # 8-4-4-4-12
    return "{%s-%s-%s-%s-%s}" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def parse_tsg_graph(filepath):
    """
    Parse a Simpsons Game .graph file.

    Returns a dict:
    {
        "guid": str or None,
        "nodes": [ {x,y,z,radius,area,flags}, ... ],
        "edges": [ {a,b,cost,tag_c,tag_d}, ... ],
        "vertices": [ (x,y,z), ... ],      # coord-ref block
        "polygons": [ [idx0, idx1, ...], ... ]   # indices into vertices
    }
    """
    with open(filepath, "rb") as f:
        data = f.read()

    size = len(data)
    if size < 0x80:
        raise ValueError("File too small to be a valid .graph")

    guid_str = _guid_str_from_header(data)

    # Header fields
    raw0C = _u32_be(data, 0x0C)
    node_offset = _u32_be(data, 0x20)
    node_end_24 = _u32_be(data, 0x24)

    off40 = _u32_be(data, 0x40)
    off44 = _u32_be(data, 0x44)
    off48 = _u32_be(data, 0x48)
    off60 = _u32_be(data, 0x60)
    count_64 = _u32_be(data, 0x64)
    off68 = _u32_be(data, 0x68)
    off70 = _u32_be(data, 0x70)

    node_count = raw0C >> 16
    other_count = raw0C & 0xFFFF  # currently unused, but might be edges+others

    # Sanity
    if node_offset == 0 or node_offset >= size:
        node_offset = 0

    def valid_node_end(v):
        if v is None or v == 0:
            return False
        if v < node_offset or v > size:
            return False
        # each node is 0x20 bytes
        return ((v - node_offset) % 0x20) == 0

    expected_node_end = node_offset + node_count * 0x20
    node_end = expected_node_end

    if valid_node_end(node_end_24):
        node_end = node_end_24
    elif valid_node_end(off68):
        node_end = off68

    if node_end > size:
        node_end = size
    if node_end < node_offset:
        node_end = node_offset

    # ------------ Parse nodes ------------
    nodes = []
    if node_offset != 0 and node_count > 0:
        off = node_offset
        for i in range(node_count):
            if off + 0x20 > size:
                break
            x = _f32_be(data, off + 0x00)
            y = _f32_be(data, off + 0x04)
            z = _f32_be(data, off + 0x08)
            radius = _f32_be(data, off + 0x0C)
            node_id = _u16_be(data, off + 0x10)
            area_id = _i16_be(data, off + 0x12)
            flags = _u32_be(data, off + 0x14)
            # unk1 = _u32_be(data, off + 0x18)
            # unk2 = _u32_be(data, off + 0x1C)

            nodes.append({
                "x": x,
                "y": y,
                "z": z,
                "radius": radius,
                "node_id": node_id,
                "area": area_id,
                "flags": flags,
            })
            off += 0x20

    # ------------ Determine where edge block could be ------------
    # Collect all potential block offsets after node_end
    potential_blocks = []
    for v in (off40, off44, off48, off60 if count_64 > 0 else 0, off68, off70):
        if v and node_end <= v < size:
            potential_blocks.append(v)
    potential_blocks = sorted(set(potential_blocks))
    next_block_after_nodes = potential_blocks[0] if potential_blocks else size

    # ------------ Parse edges (heuristic) ------------
    edges = []
    off = node_end
    # Only attempt if we have nodes
    if node_count > 0:
        while off + 16 <= next_block_after_nodes:
            cost = _f32_be(data, off + 0x00)
            a = _u16_be(data, off + 0x04)
            b = _u16_be(data, off + 0x06)
            tag_c = _i16_be(data, off + 0x08)
            tag_d = _u16_be(data, off + 0x0A)
            zero = _u32_be(data, off + 0x0C)

            # Simple validation: indices must be in range and different
            if a >= node_count or b >= node_count or a == b:
                break
            # cost should be finite and not insane
            if not (cost == cost) or abs(cost) > 1e6:
                break

            edges.append({
                "a": a,
                "b": b,
                "cost": cost,
                "tag_c": tag_c,
                "tag_d": tag_d,
                "zero": zero,
            })
            off += 16

    # ------------ Parse coord-ref vertices (off48) ------------
    vertices = []
    if 0 < off48 < size:
        # find next block after off48
        others = []
        for v in (off40, off44, off60 if count_64 > 0 else 0, off68, off70):
            if v and v > off48 and v <= size:
                others.append(v)
        limit = min(others) if others else size

        off = off48
        while off + 12 <= limit:
            x = _f32_be(data, off + 0x00)
            y = _f32_be(data, off + 0x04)
            z = _f32_be(data, off + 0x08)
            vertices.append((x, y, z))
            off += 12

    # ------------ Parse index lists (off44) into polygons ------------
    polygons = []
    if 0 < off44 < size and vertices:
        others = []
        for v in (off40, off48, off60 if count_64 > 0 else 0, off68, off70):
            if v and v > off44 and v <= size:
                others.append(v)
        limit = min(others) if others else size

        off = off44
        current = []
        vcount = len(vertices)

        while off + 2 <= limit:
            idx = _u16_be(data, off)
            off += 2
            if idx == 0xFFFF:
                # end of one polygon
                if len(current) >= 3 and all(0 <= i < vcount for i in current):
                    polygons.append(current[:])
                current = []
            else:
                current.append(idx)

        if len(current) >= 3 and all(0 <= i < vcount for i in current):
            polygons.append(current)

    return {
        "guid": guid_str,
        "nodes": nodes,
        "edges": edges,
        "vertices": vertices,
        "polygons": polygons,
        "node_count": node_count,
        "other_count": other_count,
    }


# ----------------- BLENDER IMPORT LOGIC -----------------

def make_nodes_mesh(context, graph_data, base_name):
    nodes = graph_data["nodes"]
    if not nodes:
        return None

    verts = [tsg_to_blender(n["x"], n["y"], n["z"]) for n in nodes]

    mesh = bpy.data.meshes.new(base_name + "_Nodes")
    mesh.from_pydata(verts, [], [])
    mesh.update()

    obj = bpy.data.objects.new(base_name + "_Nodes", mesh)
    obj["tsg_type"] = "nodes"
    if graph_data["guid"]:
        obj["tsg_guid"] = graph_data["guid"]

    context.collection.objects.link(obj)
    return obj


def make_edges_mesh(context, graph_data, base_name):
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    if not nodes or not edges:
        return None

    verts = [tsg_to_blender(n["x"], n["y"], n["z"]) for n in nodes]
    edge_pairs = [(e["a"], e["b"]) for e in edges]

    mesh = bpy.data.meshes.new(base_name + "_Edges")
    mesh.from_pydata(verts, edge_pairs, [])
    mesh.update()

    obj = bpy.data.objects.new(base_name + "_Edges", mesh)
    obj["tsg_type"] = "edges"
    if graph_data["guid"]:
        obj["tsg_guid"] = graph_data["guid"]

    context.collection.objects.link(obj)
    return obj


def make_polygons_mesh(context, graph_data, base_name):
    verts = graph_data["vertices"]
    polys = graph_data["polygons"]
    if not verts or not polys:
        return None

    mesh = bpy.data.meshes.new(base_name + "_Polys")
    mesh.from_pydata([tsg_to_blender(*v) for v in verts], [], polys)
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(base_name + "_Polys", mesh)
    obj["tsg_type"] = "polygons"
    if graph_data["guid"]:
        obj["tsg_guid"] = graph_data["guid"]

    context.collection.objects.link(obj)
    return obj


# ----------------- OPERATOR -----------------

class IMPORT_OT_tsg_graph(Operator, ImportHelper):
    """Import a Simpsons Game navgraph (.graph)"""
    bl_idname = "import_scene.tsg_graph"
    bl_label = "Import .graph (The Simpsons Game)"
    bl_options = {'UNDO'}

    filename_ext: StringProperty(
        default=".graph",
        options={'HIDDEN'},
    )

    filter_glob: StringProperty(
        default="*.graph",
        options={'HIDDEN'},
    )

    def execute(self, context):
        filepath = self.filepath
        try:
            graph_data = parse_tsg_graph(filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse .graph: {e}")
            return {'CANCELLED'}

        guid = graph_data.get("guid") or "UNKNOWN"
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        base_name = f"TSG_{base_name}"

        # Create a parent empty to keep things tidy
        parent = bpy.data.objects.new(base_name, None)
        parent.empty_display_type = 'PLAIN_AXES'
        parent["tsg_type"] = "graph_root"
        parent["tsg_guid"] = guid
        context.collection.objects.link(parent)

        nodes_obj = make_nodes_mesh(context, graph_data, base_name)
        edges_obj = make_edges_mesh(context, graph_data, base_name)
        polys_obj = make_polygons_mesh(context, graph_data, base_name)

        for child in (nodes_obj, edges_obj, polys_obj):
            if child is not None:
                child.parent = parent

        self.report({'INFO'}, f"Imported .graph with GUID {guid}")
        return {'FINISHED'}


# ----------------- MENU REGISTRATION -----------------

def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_tsg_graph.bl_idname,
        text="The Simpsons Game NavGraph (.graph)"
    )


def register():
    bpy.utils.register_class(IMPORT_OT_tsg_graph)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_OT_tsg_graph)


if __name__ == "__main__":
    register()
