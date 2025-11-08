#!/usr/bin/env python3
import os, io, json, struct, math, argparse, re
from statistics import median
from typing import List, Tuple, Optional, Dict

# ---- mesh header signature (from your addon) ----
MESH_REGEX = re.compile(b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C", re.DOTALL)

UV_METHODS = [
    "AUTO_TAIL",
    "F32_BE_TAIL", "F32_LE_TAIL",
    "F16_BE_TAIL", "F16_LE_TAIL",
    "SN16_BE_TAIL", "SN16_LE_TAIL",
    "UN16_BE_TAIL", "UN16_LE_TAIL",
]

# origin sweep (offset relative to tail or head of vertex)
ORIGINS = ["tail", "head"]

# permutations/inversions to try
PERMUTATIONS = [
    ("uv", False, False),   # (u,v)
    ("vu", False, False),   # (v,u)
    ("uv", True,  False),   # (u, 1-v)
    ("vu", True,  False),   # (v, 1-u) then renamed to (u,v) via swap
    ("uv", False, True),    # (1-u, v)
    ("uv", True,  True),    # (1-u, 1-v)
    ("vu", False, True),
    ("vu", True,  True),
]

def strip2face(strip: List[int]) -> List[Tuple[int, int, int]]:
    flipped = False
    out = []
    if len(strip) < 3:
        return out
    for i in range(len(strip) - 2):
        a, b, c = strip[i], strip[i+1], strip[i+2]
        if a == b or a == c or b == c:
            flipped = not flipped
            continue
        out.append((c, b, a) if flipped else (b, c, a))
        flipped = not flipped
    return out

def _read_uv_pair(buf: bytes, vert_data_start: int, vert_stride: int, offset_from_end: int, method: str) -> Optional[Tuple[float, float]]:
    start = vert_data_start + vert_stride - offset_from_end
    if start < 0 or start >= len(buf):
        return None
    try:
        if method == "F32_BE_TAIL":
            if start + 8 > len(buf): return None
            return struct.unpack(">ff", buf[start:start+8])
        if method == "F32_LE_TAIL":
            if start + 8 > len(buf): return None
            return struct.unpack("<ff", buf[start:start+8])
        if method == "F16_BE_TAIL":
            if start + 4 > len(buf): return None
            u = struct.unpack(">e", buf[start:start+2])[0]
            v = struct.unpack(">e", buf[start+2:start+4])[0]
            return float(u), float(v)
        if method == "F16_LE_TAIL":
            if start + 4 > len(buf): return None
            u = struct.unpack("<e", buf[start:start+2])[0]
            v = struct.unpack("<e", buf[start+2:start+4])[0]
            return float(u), float(v)
        if method == "SN16_BE_TAIL":
            if start + 4 > len(buf): return None
            u, v = struct.unpack(">hh", buf[start:start+4])
            return (u / 32767.0, v / 32767.0)
        if method == "SN16_LE_TAIL":
            if start + 4 > len(buf): return None
            u, v = struct.unpack("<hh", buf[start:start+4])
            return (u / 32767.0, v / 32767.0)
        if method == "UN16_BE_TAIL":
            if start + 4 > len(buf): return None
            u, v = struct.unpack(">HH", buf[start:start+4])
            return (u / 65535.0, v / 65535.0)
        if method == "UN16_LE_TAIL":
            if start + 4 > len(buf): return None
            u, v = struct.unpack("<HH", buf[start:start+4])
            return (u / 65535.0, v / 65535.0)
        if method == "AUTO_TAIL":
            for m in ["F32_BE_TAIL","F32_LE_TAIL","F16_LE_TAIL","F16_BE_TAIL","SN16_LE_TAIL","SN16_BE_TAIL","UN16_LE_TAIL","UN16_BE_TAIL"]:
                uv = _read_uv_pair(buf, vert_data_start, vert_stride, offset_from_end, m)
                if uv and all(math.isfinite(c) for c in uv):
                    return uv
            return None
    except Exception:
        return None
    return None

# origin-aware read, reusing tail reader
def _read_uv_pair_any(buf: bytes, vert_data_start: int, vert_stride: int, offset: int, origin: str, method: str):
    """
    origin='tail': offset is bytes from end-of-vertex (current meaning)
    origin='head': offset is bytes from start-of-vertex
    """
    if origin == "tail":
        return _read_uv_pair(buf, vert_data_start, vert_stride, offset, method)
    # origin == 'head' -> convert to tail offset for the shared reader
    tail_off = vert_stride - offset
    if tail_off <= 0:
        return None
    return _read_uv_pair(buf, vert_data_start, vert_stride, tail_off, method)

def _avg3(a, b, c):
    return [(a[0]+b[0]+c[0])/3.0, (a[1]+b[1]+c[1])/3.0, (a[2]+b[2]+c[2])/3.0]

def parse_mesh_part(data: bytes, mesh_idx: int, part_idx: int):
    events = list(MESH_REGEX.finditer(data))
    if not events:
        raise RuntimeError("No mesh chunks found")
    if mesh_idx < 0 or mesh_idx >= len(events):
        raise IndexError(f"mesh_idx {mesh_idx} out of range (found {len(events)})")

    m = events[mesh_idx]
    data_io = io.BytesIO(data)
    data_io.seek(m.end() + 4)

    FaceDataOff = int.from_bytes(data_io.read(4), byteorder='little')
    MeshDataSize = int.from_bytes(data_io.read(4), byteorder='little')
    MeshChunkStart = data_io.tell()
    data_io.seek(0x14, 1)
    mDataTableCount = int.from_bytes(data_io.read(4), byteorder='big')
    mDataSubCount   = int.from_bytes(data_io.read(4), byteorder='big')

    for _ in range(mDataTableCount):
        data_io.seek(4, 1)
        data_io.read(4)

    if part_idx < 0 or part_idx >= mDataSubCount:
        raise IndexError(f"part_idx {part_idx} out of range (has {mDataSubCount})")

    mDataSubStart = data_io.tell()
    data_io.seek(mDataSubStart + part_idx * 0xC + 8)
    offset = int.from_bytes(data_io.read(4), byteorder='big')
    data_io.seek(offset + MeshChunkStart + 0xC)
    VertCountDataOff = int.from_bytes(data_io.read(4), byteorder='big') + MeshChunkStart
    data_io.seek(VertCountDataOff)
    VertChunkTotalSize = int.from_bytes(data_io.read(4), byteorder='big')
    VertChunkSize      = int.from_bytes(data_io.read(4), byteorder='big')
    VertCount          = int(VertChunkTotalSize / VertChunkSize)

    data_io.seek(8, 1)
    VertexStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart

    data_io.seek(0x14, 1)
    FaceCount = int(int.from_bytes(data_io.read(4), byteorder='big') / 2)
    data_io.seek(4, 1)
    FaceStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart

    # Read triangle strips
    if FaceStart < 0 or FaceStart >= len(data):
        raise ValueError(f"FaceStart {FaceStart:08X} OOB")
    data_io.seek(FaceStart)
    if FaceStart + FaceCount * 2 > len(data):
        FaceCount = (len(data) - FaceStart) // 2

    strips: List[List[int]] = []
    cur: List[int] = []
    for _ in range(FaceCount):
        if data_io.tell() + 2 > len(data): break
        idx = int.from_bytes(data_io.read(2), byteorder='big')
        if idx == 65535:
            if cur: strips.append(cur.copy())
            cur.clear()
        else:
            cur.append(idx)
    if cur: strips.append(cur)

    faces: List[Tuple[int,int,int]] = []
    for s in strips:
        faces.extend(strip2face(s))

    # Read vertices (positions only here)
    if VertexStart < 0 or VertexStart >= len(data):
        raise ValueError(f"VertexStart {VertexStart:08X} OOB")

    verts = []
    for v in range(VertCount):
        base = VertexStart + v * VertChunkSize
        if base + VertChunkSize > len(data): break
        x, y, z = struct.unpack(">fff", data[base:base+12])
        verts.append((x,y,z))

    return {
        "VertexStart": VertexStart,
        "VertChunkSize": VertChunkSize,
        "VertCount": len(verts),
        "Verts": verts,
        "Faces": faces,
        "MeshName": f"Mesh_{mesh_idx}_{part_idx}"
    }

def candidate_decode(data_blob: dict, data: bytes, origin: str, method: str, offset: int,
                     perm: Tuple[str,bool,bool]) -> Tuple[List[Tuple[float,float]], dict]:
    """Decode UVs for a candidate (origin + method + offset + permutation/inversions)."""
    vert_stride = data_blob["VertChunkSize"]
    vstart = data_blob["VertexStart"]
    uv_list: List[Tuple[float,float]] = []
    perm_kind, inv_v, inv_u = perm

    finite = 0
    in01 = 0
    values_u, values_v = [], []

    for vi in range(data_blob["VertCount"]):
        base = vstart + vi * vert_stride
        uv = None
        if method == "AUTO_TAIL":
            for m in ["F32_BE_TAIL","F32_LE_TAIL","F16_LE_TAIL","F16_BE_TAIL",
                      "SN16_LE_TAIL","SN16_BE_TAIL","UN16_LE_TAIL","UN16_BE_TAIL"]:
                uv = _read_uv_pair_any(data, base, vert_stride, offset, origin, m)
                if uv and all(math.isfinite(c) for c in uv):
                    break
        else:
            uv = _read_uv_pair_any(data, base, vert_stride, offset, origin, method)

        if uv is None:
            uv = (float("nan"), float("nan"))

        u, v = uv
        if perm_kind == "vu":
            u, v = v, u
        if inv_u:
            u = 1.0 - u
        if inv_v:
            v = 1.0 - v

        uv_list.append((u, v))

        if math.isfinite(u) and math.isfinite(v):
            finite += 1
            if 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0:
                in01 += 1
            values_u.append(u); values_v.append(v)

    score = {
        "finite_ratio": finite / max(1, data_blob["VertCount"]),
        "in01_ratio": in01 / max(1, finite),
        "u_median": median(values_u) if values_u else float("nan"),
        "v_median": median(values_v) if values_v else float("nan"),
        "u_span": (max(values_u) - min(values_u)) if values_u else float("nan"),
        "v_span": (max(values_v) - min(values_v)) if values_v else float("nan"),
    }
    return uv_list, score

def build_json(mesh_name: str, verts: List[Tuple[float,float,float]],
               faces: List[Tuple[int,int,int]], uvs: List[Tuple[float,float]]) -> dict:
    def avg3(a, b, c):
        return [(a[0]+b[0]+c[0])/3.0, (a[1]+b[1]+c[1])/3.0, (a[2]+b[2]+c[2])/3.0]
    def r4(x: float) -> float:
        # format to 4 decimals then back to float to keep JSON numeric type while limiting precision
        try:
            return float(f"{x:.4f}")
        except Exception:
            return x

    faces_json = []
    for fi, (i,j,k) in enumerate(faces):
        if i >= len(verts) or j >= len(verts) or k >= len(verts):
            continue
        cx, cy, cz = avg3(verts[i], verts[j], verts[k])
        faces_json.append({
            "index": int(fi),
            "center": [float(cx), float(cy), float(cz)],
            "vertex_indices": [int(i), int(j), int(k)],
            "loops": [
                {"index": 0, "uv": [r4(uvs[i][0]), r4(uvs[i][1])]},
                {"index": 1, "uv": [r4(uvs[j][0]), r4(uvs[j][1])]},
                {"index": 2, "uv": [r4(uvs[k][0]), r4(uvs[k][1])]},
            ]
        })
    # collections left empty to avoid false mismatches
    return {"objects": [{"name": mesh_name, "collections": [], "faces": faces_json}]}

def load_ref_face_uvs(ref_json_path: str) -> Optional[List[Tuple[float,float]]]:
    """Load a reference JSON (face-local loop indices) and flatten UVs in face order."""
    try:
        with open(ref_json_path, "r", encoding="utf-8") as f:
            ref = json.load(f)
        obj = ref["objects"][0]
        flat: List[Tuple[float,float]] = []
        faces = obj.get("faces", [])
        faces_sorted = sorted(faces, key=lambda f: f.get("index", 0))
        for face in faces_sorted:
            loops = face.get("loops", [])
            loops_sorted = sorted(loops, key=lambda l: l.get("index", 0))
            for lp in loops_sorted:
                uv = lp.get("uv")
                if isinstance(uv, list) and len(uv) == 2:
                    flat.append((float(uv[0]), float(uv[1])))
        return flat if flat else None
    except Exception:
        return None

def flatten_candidate_face_uvs(verts, faces, uvs) -> List[Tuple[float,float]]:
    """Flatten candidate UVs to the same per-face order (i,j,k) → loop 0,1,2."""
    flat: List[Tuple[float,float]] = []
    for (i,j,k) in faces:
        if i < len(uvs) and j < len(uvs) and k < len(uvs):
            flat.append(uvs[i]); flat.append(uvs[j]); flat.append(uvs[k])
    return flat

def mse_against_ref_face(flat_cand: List[Tuple[float,float]], flat_ref: List[Tuple[float,float]]) -> float:
    import math
    n = min(len(flat_cand), len(flat_ref))
    if n == 0:
        return float("inf")
    err = 0.0
    cnt = 0
    for a, b in zip(flat_cand[:n], flat_ref[:n]):
        u1, v1 = a; u2, v2 = b
        if math.isfinite(u1) and math.isfinite(v1):
            du = u1 - u2; dv = v1 - v2
            err += du*du + dv*dv
            cnt += 1
    return err / cnt if cnt else float("inf")

def main():
    ap = argparse.ArgumentParser(description="Brute-force UV decode: methods × tail offsets × permutations.")
    ap.add_argument("input", help="Path to .preinstanced file")
    ap.add_argument("--mesh-idx", type=int, default=7)
    ap.add_argument("--part-idx", type=int, default=0)
    ap.add_argument("--tail-min", type=int, default=4, help="Min tail offset (bytes)")
    ap.add_argument("--tail-max", type=int, default=64, help="Max tail offset (bytes)")
    ap.add_argument("--tail-step", type=int, default=2, help="Step (bytes)")
    ap.add_argument("--out-dir", default="uv_bruteforce_out")
    ap.add_argument("--ref-json", default=None, help="Optional path to reference JSON to rank candidates")
    ap.add_argument("--top-k", type=int, default=10, help="Also write a summary of top-K candidates")
    args = ap.parse_args()

    with open(args.input, "rb") as f:
        data = f.read()

    mesh = parse_mesh_part(data, args.mesh_idx, args.part_idx)
    mesh_name = mesh["MeshName"]
    verts = mesh["Verts"]
    faces = mesh["Faces"]

    os.makedirs(args.out_dir, exist_ok=True)

    ref_flat = load_ref_face_uvs(args.ref_json) if args.ref_json else None

    summary = []
    base = os.path.splitext(os.path.basename(args.input))[0]

    for origin in ORIGINS:
        for method in UV_METHODS:
            for off in range(args.tail_min, args.tail_max + 1, args.tail_step):
                for perm in PERMUTATIONS:
                    uvs, score = candidate_decode(mesh, data, origin, method, off, perm)
                    if score["finite_ratio"] == 0.0:
                        continue

                    # If reference is present, compute MSE (lower is better) using face-local flattening
                    flat_cand = flatten_candidate_face_uvs(verts, faces, uvs)
                    mse = mse_against_ref_face(flat_cand, ref_flat) if ref_flat else None

                    # Build filename hint
                    perm_kind, inv_v, inv_u = perm
                    tag = f"{origin}_{method}_off{off}_perm{perm_kind}_invV{int(inv_v)}_invU{int(inv_u)}"
                    out_name = f"{base}_{mesh_name}_{tag}.json"
                    out_path = os.path.join(args.out_dir, out_name)

                    # Write JSON
                    data_json = build_json(mesh_name, verts, faces, uvs)
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(data_json, f, indent=2)

                    entry = {
                        "file": out_name,
                        "origin": origin,
                        "method": method,
                        "tail_off": off,
                        "perm": {"swap_uv": perm_kind=="vu", "invert_v": inv_v, "invert_u": inv_u},
                        "finite_ratio": score["finite_ratio"],
                        "in01_ratio": score["in01_ratio"],
                        "u_median": score["u_median"],
                        "v_median": score["v_median"],
                        "u_span": score["u_span"],
                        "v_span": score["v_span"],
                        "mse_vs_ref": mse
                    }
                    summary.append(entry)
                    print(f"Wrote {out_name}  finite={score['finite_ratio']:.2f} in01={score['in01_ratio']:.2f}"
                          + (f"  mse={mse:.6g}" if mse is not None else ""))

    # rank + write summary
    if ref_flat:
        summary.sort(key=lambda e: (e["mse_vs_ref"], -e["in01_ratio"], -e["finite_ratio"]))
    else:
        summary.sort(key=lambda e: (-e["in01_ratio"], -e["finite_ratio"]))

    with open(os.path.join(args.out_dir, f"{base}_{mesh_name}__SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # also dump a small top-K txt for quick glance
    topk = summary[:max(1, args.top_k)]
    with open(os.path.join(args.out_dir, f"{base}_{mesh_name}__TOP{len(topk)}.txt"), "w", encoding="utf-8") as f:
        for i, e in enumerate(topk, 1):
            f.write(f"{i:02d}. {e['file']}  finite={e['finite_ratio']:.2f} in01={e['in01_ratio']:.2f}"
                    + (f"  mse={e['mse_vs_ref']:.6g}" if e['mse_vs_ref'] is not None else "")
                    + f"  med=({e['u_median']:.4f},{e['v_median']:.4f}) span=({e['u_span']:.4f},{e['v_span']:.4f})\n")

if __name__ == "__main__":
    main()
