# extract_buvd_uvs.py
import struct, json, sys, os

HEADER_FMT = '<4sBI'   # magic(4s), version(uint8), num_objects(uint32)
U32_FMT    = '<I'
LOOP_FMT   = '<Iff'    # loop_index(uint32), u(float32), v(float32)
CENTER_FMT = '<3f'

def read_exact(f, size, what):
    buf = f.read(size)
    if len(buf) != size:
        raise EOFError(f"Unexpected EOF while reading {what}")
    return buf

def read_u32(f, what='uint32'):
    return struct.unpack(U32_FMT, read_exact(f, struct.calcsize(U32_FMT), what))[0]

def read_str(f, label):
    n = read_u32(f, f'{label}_length')
    data = read_exact(f, n, f'{label}_bytes')
    return data.decode('utf-8')

def extract_mesh_uvs_from_buvd(buvd_path, target_name):
    with open(buvd_path, 'rb') as f:
        # --- header ---
        magic, version, num_objects = struct.unpack(HEADER_FMT, read_exact(f, struct.calcsize(HEADER_FMT), "header"))
        if magic != b'BUVD':
            raise ValueError(f"Invalid magic {magic!r}, expected b'BUVD'")
        # version check (your writer uses version=1)
        if version != 1:
            # Not fatal—just warn; structure is identical in your code
            print(f"Warning: file version is {version}, expected 1")

        # --- iterate objects until we find the target ---
        for _ in range(num_objects):
            name = read_str(f, 'object_name')
            # collections
            num_collections = read_u32(f, 'num_collections')
            collections = [read_str(f, f'collection[{i}]') for i in range(num_collections)]
            # faces
            num_faces = read_u32(f, 'num_faces')

            # If it's not the target, we still have to seek past its faces cleanly
            def read_face(skip_only=False):
                face_index = read_u32(f, 'face_index')
                num_loops  = read_u32(f, 'num_loops')
                center     = struct.unpack(CENTER_FMT, read_exact(f, struct.calcsize(CENTER_FMT), 'face_center'))
                # vertex indices
                num_vertices = read_u32(f, 'num_vertices')
                verts = list(struct.unpack(f'<{num_vertices}I',
                                           read_exact(f, struct.calcsize(f'<{num_vertices}I'), 'vertex_indices')))
                # loops
                loops = []
                for _ in range(num_loops):
                    loop_index, u, v = struct.unpack(LOOP_FMT, read_exact(f, struct.calcsize(LOOP_FMT), 'loop'))
                    if not skip_only:
                        loops.append({"index": loop_index, "uv": [u, v]})
                if skip_only:
                    return None
                return {
                    "index": face_index,
                    "center": [float(center[0]), float(center[1]), float(center[2])],
                    "vertex_indices": verts,
                    "loops": loops
                }

            if name == target_name:
                faces = []
                for _fi in range(num_faces):
                    faces.append(read_face(skip_only=False))
                # Build the same JSON schema as your exporter
                return {
                    "objects": [{
                        "name": name,
                        "collections": collections,
                        "faces": faces
                    }]
                }
            else:
                # Skip faces for this non-target object
                for _fi in range(num_faces):
                    read_face(skip_only=True)

    # If we reached here, not found
    raise KeyError(f"Mesh '{target_name}' not found in {os.path.basename(buvd_path)}")

def main():
    if len(sys.argv) < 4:
        print("Usage: python extract_buvd_uvs.py <path/to/uv_export.buvd> <MeshName> <out.json>")
        sys.exit(1)
    buvd_path, mesh_name, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    data = extract_mesh_uvs_from_buvd(buvd_path, mesh_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Wrote UVs for '{mesh_name}' to {out_path}")

if __name__ == "__main__":
    main()
