import os
import re
import struct
import string
import tkinter as tk
from tkinter import filedialog, ttk

# --- Constants & Signatures ---
# Extracted from EARS_MESH Documentation v2.0
TEX_HEADER_PATTERN = b'\x02\x11\x01\x00\x02\x00\x00\x00.{4}\x2D\x00\x02\x1C'
TLFD_PATTERN = b'TLFD'
EOF_PATTERN = b'\x16\xEA\x00\x00\x05\x00\x00\x00\x2D\x00\x02\x1C\x01\x00\x00\x00\x00'
MESH_SIG_PATTERN = b'\x33\xEA\x00\x00.{4}\x2D\x00\x02\x1C'

_ALLOWED_CHARS = string.ascii_letters + string.digits + '_-.'
_ALLOWED_CHARS_BYTES = _ALLOWED_CHARS.encode('ascii')
DECODED_COL_START = 79

COLORS = {
    "FILE_HEADER": {"bg": "#e9e2ff", "desc": "Main File Header"},
    "FILE_HEADER_SIG": {"bg": "#d9cbff", "desc": "File Header Marker"},
    "FILE_HEADER_META": {"bg": "#f4efff", "desc": "File Header Metadata / Unknown"},
    "TEX_HEADER": {"bg": "#a3d8f4", "desc": "Texture Header"},
    "TEX_SIZE": {"bg": "#cdefff", "desc": "Texture Header Length / Size Field"},
    "TEX_NAME": {"bg": "#a3f4b5", "desc": "Texture Name String"},
    "NULL": {"bg": "#d3d3d3", "desc": "Null Terminator"},
    "TLFD": {"bg": "#f4cca3", "desc": "Texture List Delimiter (TLFD)"},
    "EOF": {"bg": "#f4a3a3", "desc": "EOF Marker"},
    "SECTION_HDR": {"bg": "#e7e7e7", "desc": "Shared / Unknown Section Header"},
    "MESH_SIG": {"bg": "#f4f0a3", "desc": "Mesh Chunk Signature"},
    "MESH_META": {"bg": "#fff3bf", "desc": "Mesh Chunk Metadata / Unknown"},
    "MESH_VER": {"bg": "#e5a3f4", "desc": "Mesh Chunk Padding / Version (BE)"},
    "MESH_FACE_OFF": {"bg": "#a3f4eb", "desc": "FaceDataOff (LE)"},
    "MESH_DATA_SIZE": {"bg": "#a3f4eb", "desc": "MeshDataSize (LE)"},
    "MESH_COUNT": {"bg": "#b0e0e6", "desc": "Mesh Table / Submesh Counts (BE)"},
    "MESH_TABLE": {"bg": "#e0ffff", "desc": "Mesh Data Table"},
    "MESH_SUBHDR": {"bg": "#87ceeb", "desc": "Submesh Header"},
    "MESH_VERTINFO": {"bg": "#dda0dd", "desc": "Vertex Info Block"},
    "MESH_VERTS": {"bg": "#ffb6c1", "desc": "Vertex Buffer"},
    "MESH_FACES": {"bg": "#ffdab9", "desc": "Face Index Buffer"},
    "MESH_PAD": {"bg": "#ececec", "desc": "Padding / Alignment"},
    "UNKNOWN": {"bg": "white", "desc": "Unknown / Unmapped Data"}
}

class PreinstancedHexViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Preinstanced Asset Viewer (EARS_MESH)")
        self.geometry("1400x800")

        self.byte_data = b""
        self.byte_map = [] # Maps byte index to a descriptor dictionary
        self.line_notes = {}

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_open = ttk.Button(toolbar, text="Open .preinstanced File", command=self.open_file)
        btn_open.pack(side=tk.LEFT)

        self.file_label = ttk.Label(toolbar, text="No file loaded.")
        self.file_label.pack(side=tk.LEFT, padx=10)

        # Legend
        legend_frame = ttk.Frame(toolbar)
        legend_frame.pack(side=tk.RIGHT)
        for key, info in COLORS.items():
            if key == "UNKNOWN": continue
            lbl = tk.Label(legend_frame, text=key.replace("_", " "), bg=info["bg"], relief="ridge", borderwidth=1, padx=2)
            lbl.pack(side=tk.LEFT, padx=2)

        # Hex Display Area
        text_frame = ttk.Frame(self)
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add scrollbar
        scrollbar_y = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        scrollbar_x = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.text_widget = tk.Text(
            text_frame,
            font=("Courier New", 11),
            wrap="none",
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=self.text_widget.yview)
        scrollbar_x.config(command=self.text_widget.xview)

        # Configure Text Tags for highlighting
        for tag, info in COLORS.items():
            self.text_widget.tag_config(tag, background=info["bg"])
        self.text_widget.tag_config(
            "DECODED_COL",
            foreground="#0b3d91",
            background="#f3f8ff",
            font=("Courier New", 11, "bold"),
        )

        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind interactions
        self.text_widget.bind("<Button-1>", self.on_click)
        self.text_widget.bind("<Motion>", self.on_hover)

    def open_file(self):
        filepath = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Preinstanced Files", "*.preinstanced *.dff.preinstanced *.rws.preinstanced"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        self.file_label.config(text=os.path.basename(filepath))
        self.status_var.set("Loading and parsing...")
        self.update()

        try:
            with open(filepath, "rb") as f:
                self.byte_data = f.read()

            # Limit file size for GUI responsiveness (Optional safety measure)
            MAX_BYTES = 1024 * 512 # 512 KB
            if len(self.byte_data) > MAX_BYTES:
                self.byte_data = self.byte_data[:MAX_BYTES]
                self.file_label.config(text=f"{os.path.basename(filepath)} (Truncated to 512KB)")

            self.parse_data()
            self.render_hex()
            self.status_var.set(f"Loaded {len(self.byte_data)} bytes successfully.")
        except Exception as e:
            self.status_var.set(f"Error loading file: {e}")

    def add_note(self, offset, note_text):
        """Attach a decoded note to the line that contains the given byte offset."""
        line_idx = max(0, offset // 16)
        self.line_notes.setdefault(line_idx, []).append(note_text)

    def parse_data(self):
        """Analyzes binary data based on the documentation signatures."""
        data = self.byte_data
        length = len(data)

        # Initialize map with Unknown
        self.byte_map = [{"tag": "UNKNOWN", "desc": COLORS["UNKNOWN"]["desc"]} for _ in range(length)]
        self.line_notes = {}

        def apply_tag(start, end, tag, custom_desc=None):
            if start >= length or end <= start:
                return
            end = min(end, length)
            desc = custom_desc if custom_desc else COLORS[tag]["desc"]
            for i in range(start, min(end, length)):
                self.byte_map[i] = {"tag": tag, "desc": f"{desc} (Offset: 0x{start:X} - 0x{end-1:X})"}

        def read_u32_be(offset):
            if offset + 4 <= length:
                return struct.unpack(">I", data[offset:offset + 4])[0]
            return None

        def read_u32_le(offset):
            if offset + 4 <= length:
                return struct.unpack("<I", data[offset:offset + 4])[0]
            return None

        def read_f32_be(offset):
            if offset + 4 <= length:
                return struct.unpack(">f", data[offset:offset + 4])[0]
            return None

        def extract_ascii(offset, max_len=64):
            if offset >= length:
                return None

            out = bytearray()
            for idx in range(offset, min(length, offset + max_len)):
                byte = data[idx]
                if byte == 0x00:
                    break
                if byte not in _ALLOWED_CHARS_BYTES:
                    break
                out.append(byte)

            if len(out) >= 4:
                try:
                    return out.decode("ascii")
                except UnicodeDecodeError:
                    return None
            return None

        # 0. Main file header and shared metadata
        if length >= 4 and data[0:4] == b'\x10\x00\x00\x00':
            apply_tag(0, 4, "FILE_HEADER")
            self.add_note(0, "Main file header marker: 0x10")

        if length >= 8:
            apply_tag(4, 8, "FILE_HEADER_META")

        if length >= 12 and data[8:12] == b'\x2D\x00\x02\x1C':
            apply_tag(8, 12, "FILE_HEADER_SIG")
            self.add_note(8, "SOF / RenderWare marker")

        if length >= 0x38:
            apply_tag(12, 0x38, "FILE_HEADER_META")

        if length >= 0x3C and data[0x38:0x3C] == b'\x2D\x00\x02\x1C':
            apply_tag(0x38, 0x3C, "FILE_HEADER_SIG")
            self.add_note(0x38, "Secondary header marker")

        # 1. Texture Headers & Strings
        for match in re.finditer(TEX_HEADER_PATTERN, data, re.DOTALL):
            start = match.start()
            end = match.end()
            apply_tag(start, start + 8, "TEX_HEADER")
            apply_tag(start + 8, start + 12, "TEX_SIZE")
            apply_tag(start + 12, end, "TEX_HEADER")

            declared_size = read_u32_le(start + 8)
            if declared_size is not None:
                self.add_note(start, f"Texture header size field: 0x{declared_size:X}")
            else:
                self.add_note(start, "Texture header")

            str_start = end
            str_val = extract_ascii(str_start)
            if str_val:
                str_end = str_start + len(str_val)
                apply_tag(str_start, str_end, "TEX_NAME", f"Texture Name: '{str_val}'")
                self.add_note(str_start, f'Texture name: "{str_val}"')

                if str_end < length and data[str_end] == 0x00:
                    apply_tag(str_end, str_end + 1, "NULL")
            elif str_start < length and data[str_start] == 0x00:
                apply_tag(str_start, str_start + 1, "NULL")

        # 2. TLFD Markers
        for match in re.finditer(TLFD_PATTERN, data):
            apply_tag(match.start(), match.end(), "TLFD")
            self.add_note(match.start(), "TLFD delimiter")

        # 3. EOF Markers
        for match in re.finditer(EOF_PATTERN, data):
            apply_tag(match.start(), match.end(), "EOF")
            self.add_note(match.start(), "EOF marker")

        # 4. Shared section headers (unknown sections plus mesh chunks)
        section_pattern = b'(?:\x13|\x15|\x16|\x33)\xEA\x00\x00....\x2D\x00\x02\x1C'
        for match in re.finditer(section_pattern, data, re.DOTALL):
            start = match.start()
            section_id = data[start]

            if section_id == 0x16 and data[start:start + len(EOF_PATTERN)] == EOF_PATTERN:
                continue

            if section_id != 0x33:
                apply_tag(start, start + 12, "SECTION_HDR")
                self.add_note(start, f"Unknown shared section 0x{section_id:02X}")
                meta_hex = data[start + 4:start + 8].hex(" ").upper() if start + 8 <= length else ""
                if meta_hex:
                    self.add_note(start + 4, f"Header bytes: {meta_hex}")
                continue

            apply_tag(start, start + 4, "MESH_SIG")
            apply_tag(start + 4, start + 8, "MESH_META")
            apply_tag(start + 8, start + 12, "MESH_SIG")

            self.add_note(start, "Mesh chunk header")
            meta_hex = data[start + 4:start + 8].hex(" ").upper() if start + 8 <= length else ""
            if meta_hex:
                self.add_note(start + 4, f"Chunk wildcard bytes: {meta_hex}")

            if start + 24 <= length:
                apply_tag(start + 12, start + 16, "MESH_VER")
                face_off = read_u32_le(start + 16)
                mesh_size = read_u32_le(start + 20)

                if face_off is not None:
                    apply_tag(start + 16, start + 20, "MESH_FACE_OFF")
                    self.add_note(start + 16, f"FaceDataOff: 0x{face_off:X}")

                if mesh_size is not None:
                    apply_tag(start + 20, start + 24, "MESH_DATA_SIZE")
                    self.add_note(start + 20, f"MeshDataSize: 0x{mesh_size:X}")

                mesh_chunk_start = start + 24

                if mesh_chunk_start + 0x1C <= length:
                    apply_tag(mesh_chunk_start, mesh_chunk_start + 0x14, "MESH_PAD")

                    dt_count = read_u32_be(mesh_chunk_start + 0x14)
                    ds_count = read_u32_be(mesh_chunk_start + 0x18)

                    if dt_count is not None:
                        apply_tag(mesh_chunk_start + 0x14, mesh_chunk_start + 0x18, "MESH_COUNT")
                        self.add_note(mesh_chunk_start + 0x14, f"DataTableCount: {dt_count}")

                    if ds_count is not None:
                        apply_tag(mesh_chunk_start + 0x18, mesh_chunk_start + 0x1C, "MESH_COUNT")
                        self.add_note(mesh_chunk_start + 0x18, f"SubmeshCount: {ds_count}")

                    dt_bytes = (dt_count or 0) * 8
                    dt_start = mesh_chunk_start + 0x1C
                    dt_end = dt_start + dt_bytes
                    if dt_count is not None and dt_end <= length:
                        apply_tag(dt_start, dt_end, "MESH_TABLE")
                        self.add_note(dt_start, f"Data table bytes: {dt_bytes}")

                    sub_start = dt_end
                    for i in range(ds_count or 0):
                        ptr_off = sub_start + (i * 0xC) + 8
                        if ptr_off + 4 > length:
                            break

                        sub_off = read_u32_be(ptr_off)
                        if sub_off is None:
                            continue

                        sub_hdr_abs = mesh_chunk_start + sub_off
                        if sub_hdr_abs + 0x10 > length:
                            continue

                        apply_tag(sub_hdr_abs, sub_hdr_abs + 0x10, "MESH_SUBHDR")

                        flags = read_u32_be(sub_hdr_abs)
                        bound = read_f32_be(sub_hdr_abs + 4)
                        mat_id = read_u32_be(sub_hdr_abs + 8)

                        sub_notes = [f"Submesh {i}"]
                        if flags is not None:
                            sub_notes.append(f"flags=0x{flags:08X}")
                        if bound is not None:
                            sub_notes.append(f"bound={bound:.3f}")
                        if mat_id is not None:
                            sub_notes.append(f"material={mat_id}")
                        self.add_note(sub_hdr_abs, ", ".join(sub_notes))

                        v_info_rel = read_u32_be(sub_hdr_abs + 0x0C)
                        if v_info_rel is None:
                            continue

                        v_info_abs = mesh_chunk_start + v_info_rel
                        if v_info_abs + 0x34 > length:
                            continue

                        apply_tag(v_info_abs, v_info_abs + 0x34, "MESH_VERTINFO")

                        v_tot = read_u32_be(v_info_abs)
                        v_size = read_u32_be(v_info_abs + 4)
                        v_start_rel = read_u32_be(v_info_abs + 0x10)
                        face_bytes = read_u32_be(v_info_abs + 0x28)
                        face_start_rel = read_u32_be(v_info_abs + 0x30)

                        vert_notes = []
                        if v_tot is not None:
                            vert_notes.append(f"VertTotalSize={v_tot}")
                        if v_size is not None:
                            vert_notes.append(f"Stride={v_size}")
                        if v_start_rel is not None:
                            vert_notes.append(f"VertStartRel=0x{v_start_rel:X}")
                        if face_bytes is not None:
                            vert_notes.append(f"FaceByteLen={face_bytes}")
                        if face_start_rel is not None:
                            vert_notes.append(f"FaceStartRel=0x{face_start_rel:X}")
                        if vert_notes:
                            self.add_note(v_info_abs, ", ".join(vert_notes))

                        if face_off is not None and v_tot and v_size and v_start_rel is not None:
                            abs_v_start = mesh_chunk_start + face_off + v_start_rel
                            if abs_v_start + v_tot <= length:
                                apply_tag(abs_v_start, abs_v_start + v_tot, "MESH_VERTS")
                                vert_count = v_tot // v_size if v_size else 0
                                self.add_note(abs_v_start, f"Vertex buffer: {vert_count} vertices")

                                if v_tot >= 0x24 and abs_v_start + 0x24 <= length:
                                    try:
                                        vx, vy, vz = struct.unpack(">fff", data[abs_v_start:abs_v_start + 12])
                                        u0 = struct.unpack(">f", data[abs_v_start + 0x14:abs_v_start + 0x18])[0]
                                        v0 = struct.unpack(">f", data[abs_v_start + 0x18:abs_v_start + 0x1C])[0]
                                        u1 = struct.unpack(">f", data[abs_v_start + 0x1C:abs_v_start + 0x20])[0]
                                        v1 = struct.unpack(">f", data[abs_v_start + 0x20:abs_v_start + 0x24])[0]
                                        self.add_note(
                                            abs_v_start,
                                            f"V0 pos=({vx:.3f}, {vy:.3f}, {vz:.3f}) uv0=({u0:.3f}, {1.0 - v0:.3f}) uv1=({u1:.3f}, {1.0 - v1:.3f})",
                                        )
                                    except struct.error:
                                        pass

                        if face_off is not None and face_bytes and face_start_rel is not None:
                            abs_f_start = mesh_chunk_start + face_off + face_start_rel
                            if abs_f_start + face_bytes <= length:
                                apply_tag(abs_f_start, abs_f_start + face_bytes, "MESH_FACES")
                                index_count = face_bytes // 2
                                self.add_note(abs_f_start, f"Index buffer: {index_count} indices")

                                if face_bytes >= 6 and abs_f_start + 6 <= length:
                                    try:
                                        i1, i2, i3 = struct.unpack(">HHH", data[abs_f_start:abs_f_start + 6])
                                        self.add_note(abs_f_start, f"Idx0=({i1}, {i2}, {i3})")
                                    except struct.error:
                                        pass

    def render_hex(self):
        """Builds the hex view text and applies UI tags for coloring."""
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)

        data = self.byte_data
        lines = []

        # Build text
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            decoded_notes = self.line_notes.get(i // 16, [])
            decoded_str = ' ; '.join(decoded_notes)
            lines.append(f'{i:08X}  {hex_str:<47}  {ascii_str:<16}  |  {decoded_str}\n')

        self.text_widget.insert("1.0", "".join(lines))

        # Apply color tags
        for i, info in enumerate(self.byte_map):
            tag = info["tag"]
            if tag == "UNKNOWN": continue

            line_num = (i // 16) + 1
            col_idx = i % 16

            # Hex area coords
            hex_start = 10 + (col_idx * 3)
            hex_end = hex_start + 2

            # ASCII area coords
            ascii_start = 59 + col_idx
            ascii_end = ascii_start + 1

            self.text_widget.tag_add(tag, f"{line_num}.{hex_start}", f"{line_num}.{hex_end}")
            self.text_widget.tag_add(tag, f"{line_num}.{ascii_start}", f"{line_num}.{ascii_end}")

        last_line = max(1, (len(data) // 16) + 1)
        for line in range(1, last_line + 1):
            self.text_widget.tag_add("DECODED_COL", f"{line}.{DECODED_COL_START}", f"{line}.end")

        self.text_widget.config(state=tk.DISABLED)

    def _get_byte_index_from_event(self, event):
        """Calculates which byte was clicked/hovered based on text widget coordinates."""
        index = self.text_widget.index(f"@{event.x},{event.y}")
        line, col = map(int, index.split('.'))

        line_idx = line - 1

        # Check if in hex area (columns 10 to 56)
        if 10 <= col <= 56:
            col_diff = col - 10
            # Ignore spaces between hex numbers
            if col_diff % 3 == 2:
                return None
            byte_idx = (line_idx * 16) + (col_diff // 3)
            return byte_idx if byte_idx < len(self.byte_data) else None

        # Check if in ASCII area (columns 59 to 74)
        elif 59 <= col <= 74:
            byte_idx = (line_idx * 16) + (col - 59)
            return byte_idx if byte_idx < len(self.byte_data) else None

        return None

    def on_click(self, event):
        self._update_status_from_event(event, prefix="Clicked: ")

    def on_hover(self, event):
        self._update_status_from_event(event, prefix="Hover: ")

    def _update_status_from_event(self, event, prefix=""):
        if not self.byte_data:
            return

        index = self.text_widget.index(f"@{event.x},{event.y}")
        line, col = map(int, index.split('.'))

        if col >= DECODED_COL_START:
            notes = self.line_notes.get(line - 1, [])
            if notes:
                self.status_var.set(f"{prefix}{' ; '.join(notes)}")
            else:
                self.status_var.set(f"{prefix}Decoded column.")
            return

        byte_idx = self._get_byte_index_from_event(event)

        if byte_idx is not None:
            info = self.byte_map[byte_idx]
            hex_val = f"{self.byte_data[byte_idx]:02X}"
            self.status_var.set(f"{prefix}Byte 0x{byte_idx:X} [{hex_val}] - {info['desc']}")
        else:
            self.status_var.set(f"{prefix}Selection outside valid byte range.")

if __name__ == "__main__":
    app = PreinstancedHexViewer()
    app.mainloop()