import tkinter as tk
from tkinter import filedialog, ttk
import re
import struct

# --- Constants & Signatures ---
TEX_HEADER_PATTERN = b'\x02\x11\x01\x00\x02\x00\x00\x00.{4}\x2D\x00\x02\x1C'
TLFD_PATTERN = b'TLFD'
EOF_PATTERN = b'\x16\xEA\x00\x00\x05\x00\x00\x00\x2D\x00\x02\x1C\x01\x00\x00\x00\x00'
MESH_SIG_PATTERN = b'\x33\xEA\x00\x00.{4}\x2D\x00\x02\x1C'

COLORS = {
    "FILE_HEADER": {"bg": "#e6e6fa", "desc": "SOF File Header"},
    "TEX_HEADER": {"bg": "#a3d8f4", "desc": "Texture Header"},
    "TEX_NAME": {"bg": "#a3f4b5", "desc": "Texture Name"},
    "NULL": {"bg": "#d3d3d3", "desc": "Null Terminator"},
    "TLFD": {"bg": "#f4cca3", "desc": "Texture List Delimiter"},
    "EOF": {"bg": "#f4a3a3", "desc": "EOF Marker"},
    "MESH_SIG": {"bg": "#f4f0a3", "desc": "Mesh Signature"},
    "MESH_PAD": {"bg": "#e8e8e8", "desc": "Mesh Padding"},
    "MESH_HDR": {"bg": "#a3f4eb", "desc": "Mesh Offsets (LE)"},
    "MESH_COUNT": {"bg": "#b0e0e6", "desc": "Mesh Counts (BE)"},
    "MESH_TABLE": {"bg": "#e0ffff", "desc": "Data Table"},
    "MESH_SUBHDR": {"bg": "#87ceeb", "desc": "Submesh Header"},
    "MESH_VERTINFO": {"bg": "#dda0dd", "desc": "Vertex Info"},
    "MESH_VERTS": {"bg": "#ffb6c1", "desc": "Vertex Buffer"},
    "MESH_FACES": {"bg": "#ffdab9", "desc": "Face Buffer"},
    "UNKNOWN": {"bg": "white", "desc": "Unknown Data"}
}

class PreinstancedHexViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Preinstanced Hex Viewer (EARS_MESH)")
        self.geometry("1500x800")

        self.byte_data = b""
        self.byte_map = []
        self.line_notes = {}
        self.sections = []
        self.section_render_lines = {}
        self.raw_line_to_render_line = {}

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_open = ttk.Button(toolbar, text="Open .preinstanced", command=self.open_file)
        btn_open.pack(side=tk.LEFT)

        self.file_label = ttk.Label(toolbar, text="No file loaded.")
        self.file_label.pack(side=tk.LEFT, padx=10)

        # Paned Window (Left: Sidebar, Right: Hex View)
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Sidebar ---
        sidebar = ttk.Frame(paned)
        paned.add(sidebar, weight=1)

        tree_frame = ttk.Frame(sidebar)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("range",),
            show="tree headings",
            yscrollcommand=tree_scrollbar.set,
        )
        self.tree.heading("#0", text="Parsed Sections (Dbl-Click)")
        self.tree.heading("range", text="Byte Range")
        self.tree.column("range", width=120, stretch=False)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.config(command=self.tree.yview)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # --- Main Hex Area ---
        main_area = ttk.Frame(paned)
        paned.add(main_area, weight=4)

        # Legend
        legend_frame = ttk.Frame(main_area)
        legend_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        row1 = ttk.Frame(legend_frame)
        row1.pack(side=tk.TOP, anchor="w")
        row2 = ttk.Frame(legend_frame)
        row2.pack(side=tk.TOP, anchor="w")

        keys = list(COLORS.keys())
        half = len(keys) // 2 + 1
        for i, key in enumerate(keys):
            if key == "UNKNOWN": continue
            target = row1 if i < half else row2
            lbl = tk.Label(target, text=key, bg=COLORS[key]["bg"], relief="ridge", borderwidth=1, padx=4, font=("Arial", 8))
            lbl.pack(side=tk.LEFT, padx=2, pady=2)

        text_frame = ttk.Frame(main_area)
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(text_frame, font=("Courier New", 10), wrap="none", yscrollcommand=scrollbar.set, cursor="arrow")
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)

        # Configure Core Tags
        for tag, info in COLORS.items():
            self.text_widget.tag_config(tag, background=info["bg"])
        self.text_widget.tag_config("DECODED_COL", foreground="#0000AA", font=("Courier New", 10, "bold"))
        self.text_widget.tag_config("COLLAPSED_HDR", foreground="#D32F2F", font=("Courier New", 10, "bold"), underline=True)

        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.text_widget.bind("<Button-1>", self.on_click)
        self.text_widget.bind("<Motion>", self.on_hover)

    def open_file(self):
        filepath = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Preinstanced Files", "*.preinstanced *.dff.preinstanced *.rws.preinstanced"), ("All Files", "*.*")]
        )
        if not filepath: return

        self.file_label.config(text=filepath.split("/")[-1])
        self.status_var.set("Loading and parsing...")
        self.update()

        try:
            with open(filepath, "rb") as f:
                self.byte_data = f.read()

            MAX_BYTES = 1024 * 1024
            if len(self.byte_data) > MAX_BYTES:
                self.byte_data = self.byte_data[:MAX_BYTES]
                self.file_label.config(text=f"{filepath.split('/')[-1]} (Truncated to 1MB)")

            self.parse_data()
            self.update_treeview()
            self.render_hex()
            self.status_var.set(f"Loaded {len(self.byte_data)} bytes.")
        except Exception as e:
            self.status_var.set(f"Error loading file: {e}")

    def add_note(self, offset, note_text):
        line_idx = offset // 16
        if line_idx not in self.line_notes:
            self.line_notes[line_idx] = []
        self.line_notes[line_idx].append(note_text)

    def add_section(self, start, end, name):
        end = min(end, len(self.byte_data))
        if start < end:
            self.sections.append({
                'id': len(self.sections),
                'start': start,
                'end': end,
                'name': name,
                'collapsed': False,
                'node_id': None
            })

    def parse_data(self):
        data = self.byte_data
        length = len(data)

        self.byte_map = [{"tag": "UNKNOWN", "desc": COLORS["UNKNOWN"]["desc"]}] * length
        self.line_notes = {}
        self.sections = []
        self.section_render_lines = {}
        self.raw_line_to_render_line = {}

        def apply_tag(start, end, tag, custom_desc=None):
            desc = custom_desc if custom_desc else COLORS[tag]["desc"]
            for i in range(start, min(end, length)):
                self.byte_map[i] = {"tag": tag, "desc": f"{desc} (Offset: 0x{start:X} - 0x{end-1:X})"}

        # 0. File Headers
        if length >= 12 and data[0:4] == b'\x10\x00\x00\x00':
            apply_tag(0, 12, "FILE_HEADER")
            self.add_note(0, "SOF File Header")
            self.add_section(0, 12, "File Header")

        # 1. Texture Headers & Strings
        for match in re.finditer(TEX_HEADER_PATTERN, data, re.DOTALL):
            start = match.start()
            end = match.end()
            apply_tag(start, end, "TEX_HEADER")

            str_start = end
            pos = str_start
            while pos < length and data[pos] != 0x00: pos += 1

            str_val = data[str_start:pos].decode('ascii', 'ignore') if pos > str_start else "Unknown"
            apply_tag(str_start, pos, "TEX_NAME", f"Texture: '{str_val}'")
            if pos < length: apply_tag(pos, pos + 1, "NULL")

            self.add_note(start, f"Tex: \"{str_val}\"")
            self.add_section(start, pos + 1, f"Texture Block: {str_val}")

        # 2. TLFD Markers
        for match in re.finditer(TLFD_PATTERN, data):
            apply_tag(match.start(), match.end(), "TLFD")
            self.add_note(match.start(), "TLFD Break")
            self.add_section(match.start(), match.end(), "TLFD Marker")

        # 3. Deep Mesh Chunk Parsing
        for match in re.finditer(MESH_SIG_PATTERN, data, re.DOTALL):
            start = match.start()
            apply_tag(start, start + 12, "MESH_SIG")
            self.add_note(start, "=== MESH CHUNK ===")
            self.add_section(start, start + 12, "Mesh Chunk Signature")

            if start + 24 <= length:
                apply_tag(start + 12, start + 16, "MESH_PAD")
                face_off = struct.unpack('<I', data[start+16:start+20])[0]
                mesh_size = struct.unpack('<I', data[start+20:start+24])[0]
                apply_tag(start+16, start+20, "MESH_HDR", f"FaceDataOff: 0x{face_off:X}")
                apply_tag(start+20, start+24, "MESH_HDR", f"MeshDataSize: {mesh_size}")
                self.add_section(start+12, start+24, "Mesh Padding & Offsets")

                mesh_chunk_start = start + 24

                if mesh_chunk_start + 0x1C <= length:
                    apply_tag(mesh_chunk_start, mesh_chunk_start+0x14, "MESH_PAD")
                    dt_count = struct.unpack('>I', data[mesh_chunk_start+0x14:mesh_chunk_start+0x18])[0]
                    ds_count = struct.unpack('>I', data[mesh_chunk_start+0x18:mesh_chunk_start+0x1C])[0]

                    apply_tag(mesh_chunk_start+0x14, mesh_chunk_start+0x18, "MESH_COUNT")
                    apply_tag(mesh_chunk_start+0x18, mesh_chunk_start+0x1C, "MESH_COUNT")
                    self.add_note(mesh_chunk_start+0x14, f"DataTables: {dt_count}, Submeshes: {ds_count}")
                    self.add_section(mesh_chunk_start, mesh_chunk_start+0x1C, "Mesh Structural Counts")

                    dt_start = mesh_chunk_start + 0x1C
                    dt_end = dt_start + (dt_count * 8)
                    if dt_end <= length:
                        apply_tag(dt_start, dt_end, "MESH_TABLE")
                        if dt_count > 0: self.add_section(dt_start, dt_end, "Mesh Data Table")

                    # Submeshes
                    sub_start = dt_end
                    for i in range(ds_count):
                        ptr_off = sub_start + (i * 0xC) + 8
                        if ptr_off + 4 <= length:
                            sub_off = struct.unpack('>I', data[ptr_off:ptr_off+4])[0]
                            sub_hdr_abs = mesh_chunk_start + sub_off

                            if sub_hdr_abs + 12 <= length:
                                mat_id = struct.unpack('>I', data[sub_hdr_abs+8:sub_hdr_abs+12])[0]
                                apply_tag(sub_hdr_abs, sub_hdr_abs+12, "MESH_SUBHDR")
                                self.add_note(sub_hdr_abs, f"Submesh {i} [MatID: {mat_id}]")
                                self.add_section(sub_hdr_abs, sub_hdr_abs+12, f"Submesh {i} Header")

                                vert_ptr_off = sub_hdr_abs + 0xC
                                if vert_ptr_off + 4 <= length:
                                    v_info_rel = struct.unpack('>I', data[vert_ptr_off:vert_ptr_off+4])[0]
                                    v_info_abs = mesh_chunk_start + v_info_rel

                                    if v_info_abs + 0x34 <= length:
                                        v_tot, v_size = struct.unpack('>II', data[v_info_abs:v_info_abs+8])
                                        v_start_rel = struct.unpack('>I', data[v_info_abs+0x10:v_info_abs+0x14])[0]
                                        f_count_bytes = struct.unpack('>I', data[v_info_abs+0x28:v_info_abs+0x2C])[0]
                                        f_start_rel = struct.unpack('>I', data[v_info_abs+0x30:v_info_abs+0x34])[0]

                                        apply_tag(v_info_abs, v_info_abs+0x34, "MESH_VERTINFO")
                                        self.add_section(v_info_abs, v_info_abs+0x34, f"Submesh {i} Vertex Info")

                                        abs_v_start = mesh_chunk_start + face_off + v_start_rel
                                        abs_f_start = mesh_chunk_start + face_off + f_start_rel

                                        if abs_v_start + v_tot <= length and v_tot > 0:
                                            v_count = v_tot // v_size if v_size > 0 else 0
                                            apply_tag(abs_v_start, abs_v_start+v_tot, "MESH_VERTS")
                                            self.add_note(abs_v_start, f"-> Vertices [{v_count}]")
                                            self.add_section(abs_v_start, abs_v_start+v_tot, f"Submesh {i} Vertex Buffer")

                                        if abs_f_start + f_count_bytes <= length and f_count_bytes > 0:
                                            f_count = f_count_bytes // 2
                                            apply_tag(abs_f_start, abs_f_start+f_count_bytes, "MESH_FACES")
                                            self.add_note(abs_f_start, f"-> Indices [{f_count}]")
                                            self.add_section(abs_f_start, abs_f_start+f_count_bytes, f"Submesh {i} Face Buffer")

        # 4. EOF Markers
        for match in re.finditer(EOF_PATTERN, data):
            apply_tag(match.start(), match.end(), "EOF")
            self.add_note(match.start(), "End of File")
            self.add_section(match.start(), match.end(), "EOF Marker")

        # Ensure sorted
        self.sections.sort(key=lambda x: x['start'])

    def update_treeview(self):
        self.tree.delete(*self.tree.get_children())
        for sec in self.sections:
            prefix = "[-]" if not sec['collapsed'] else "[+]"
            node_id = self.tree.insert("", tk.END, text=f"{prefix} {sec['name']}", values=(f"{sec['start']:08X}-{sec['end']:08X}",))
            sec['node_id'] = node_id

    def toggle_section(self, sec):
        sec['collapsed'] = not sec['collapsed']
        # Update tree label
        prefix = "[-]" if not sec['collapsed'] else "[+]"
        self.tree.item(sec['node_id'], text=f"{prefix} {sec['name']}")
        self.render_hex()

    def jump_to_section(self, sec):
        target_line = self.section_render_lines.get(sec['id'])
        if target_line is None:
            target_line = self.raw_line_to_render_line.get(sec['start'] // 16)
        if target_line is None:
            return

        self.text_widget.see(f"{target_line}.0")
        self.text_widget.mark_set(tk.INSERT, f"{target_line}.0")
        self.text_widget.tag_remove("sel", "1.0", tk.END)
        self.text_widget.tag_add("sel", f"{target_line}.0", f"{target_line}.end")
        self.status_var.set(f"Jumped to: {sec['name']} ({sec['start']:08X}-{sec['end']:08X})")

    def on_tree_select(self, event):
        selection = self.tree.selection()
        item_id = selection[0] if selection else None
        if not item_id:
            return
        sec = next((s for s in self.sections if s['node_id'] == item_id), None)
        if sec:
            self.jump_to_section(sec)

    def on_tree_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        sec = next((s for s in self.sections if s['node_id'] == item_id), None)
        if sec:
            self.toggle_section(sec)

    def render_hex(self):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)

        data = self.byte_data

        # Pre-calculate byte collapse boundaries
        collapsed_by = [None] * len(data)
        for sec in self.sections:
            if sec['collapsed']:
                for i in range(sec['start'], sec['end']):
                    collapsed_by[i] = sec

        lines = []
        tags_to_apply = {tag: [] for tag in COLORS.keys()}
        tags_to_apply["COLLAPSED_HDR"] = []
        tags_to_apply["DECODED_COL"] = []
        dynamic_tags = {}
        self.section_render_lines = {}
        self.raw_line_to_render_line = {}

        line_num = 1
        i = 0
        while i < len(data):
            chunk = data[i:i+16]
            chunk_coll = collapsed_by[i:i+16]

            # Entire line fully eclipsed by ONE section
            if all(chunk_coll) and chunk_coll[0] == chunk_coll[-1]:
                sec = chunk_coll[0]
                if sec['start'] >= i and sec['start'] < i+16:
                    # Print structural header
                    self.section_render_lines[sec['id']] = line_num
                    lines.append(f"[+] {sec['start']:08X}-{sec['end']:08X} collapsed: {sec['name']}\n")
                    tag_name = f"HDR_{sec['id']}"
                    if tag_name not in dynamic_tags:
                        dynamic_tags[tag_name] = []
                    dynamic_tags[tag_name].append((f"{line_num}.0", f"{line_num}.end"))
                    tags_to_apply["COLLAPSED_HDR"].append((f"{line_num}.0", f"{line_num}.end"))
                    line_num += 1
                i += 16
                continue

            # Line is fully visible or partially hidden. Inject header if a section starts here.
            starts_here = []
            seen_ids = set()
            for sec in chunk_coll:
                if sec is None:
                    continue
                if sec['start'] < i or sec['start'] >= i + 16:
                    continue
                if sec['id'] in seen_ids:
                    continue
                seen_ids.add(sec['id'])
                starts_here.append(sec)

            for sec in sorted(starts_here, key=lambda x: x['start']):
                self.section_render_lines[sec['id']] = line_num
                lines.append(f"[+] {sec['start']:08X}-{sec['end']:08X} collapsed: {sec['name']}\n")
                tag_name = f"HDR_{sec['id']}"
                if tag_name not in dynamic_tags:
                    dynamic_tags[tag_name] = []
                dynamic_tags[tag_name].append((f"{line_num}.0", f"{line_num}.end"))
                tags_to_apply["COLLAPSED_HDR"].append((f"{line_num}.0", f"{line_num}.end"))
                line_num += 1

            hex_parts = []
            ascii_parts = []

            for j, b in enumerate(chunk):
                abs_idx = i + j
                if chunk_coll[j] is not None:
                    # Collapse Replacement (Spacing exactly mimics hex footprint)
                    hex_parts.append("  ")
                    ascii_parts.append(" ")
                else:
                    hex_parts.append(f"{b:02X}")
                    ascii_parts.append(chr(b) if 32 <= b <= 126 else '.')

                    tag = self.byte_map[abs_idx]["tag"]
                    if tag != "UNKNOWN":
                        hex_start = 10 + (j * 3)
                        hex_end = hex_start + 2
                        ascii_start = 59 + j
                        ascii_end = ascii_start + 1
                        tags_to_apply[tag].append((f"{line_num}.{hex_start}", f"{line_num}.{hex_end}"))
                        tags_to_apply[tag].append((f"{line_num}.{ascii_start}", f"{line_num}.{ascii_end}"))

            hex_str = ' '.join(hex_parts)
            if len(chunk) < 16:
                hex_str += "   " * (16 - len(chunk))
                ascii_parts.extend([" "] * (16 - len(chunk)))
            ascii_str = ''.join(ascii_parts)

            # Fetch Decoded notes strictly for visible parts
            decoded_str = ""
            abs_line_idx = i // 16
            if abs_line_idx in self.line_notes:
                decoded_str = "  |  " + " ; ".join(self.line_notes[abs_line_idx])

            self.raw_line_to_render_line[abs_line_idx] = line_num
            lines.append(f"{i:08X}  {hex_str:<47}  {ascii_str:<16}{decoded_str}\n")
            tags_to_apply["DECODED_COL"].append((f"{line_num}.75", f"{line_num}.end"))

            line_num += 1
            i += 16

        self.text_widget.insert("1.0", "".join(lines))

        # Apply static colors efficiently via native TK
        for tag, ranges in tags_to_apply.items():
            if not ranges: continue
            flat = [item for sub in ranges for item in sub]
            if flat:
                self.text_widget.tk.call(self.text_widget._w, 'tag', 'add', tag, *flat)

        for tag_name, ranges in dynamic_tags.items():
            if not ranges:
                continue
            flat = [item for sub in ranges for item in sub]
            if flat:
                self.text_widget.tk.call(self.text_widget._w, 'tag', 'add', tag_name, *flat)

        # Bind Click Events for dynamically created Collapsed Headers
        for tag_name, ranges in dynamic_tags.items():
            sec_id = int(tag_name.split("_")[1])
            sec = self.sections[sec_id]
            self.text_widget.tag_bind(tag_name, "<Button-1>", lambda e, s=sec: self.toggle_section(s))
            self.text_widget.tag_bind(tag_name, "<Enter>", lambda e: self.text_widget.config(cursor="hand2"))
            self.text_widget.tag_bind(tag_name, "<Leave>", lambda e: self.text_widget.config(cursor="arrow"))

        self.text_widget.config(state=tk.DISABLED)

    def _get_byte_index_from_event(self, event):
        index = self.text_widget.index(f"@{event.x},{event.y}")
        line, col = map(int, index.split('.'))
        line_idx = line - 1

        if 10 <= col <= 56:
            col_diff = col - 10
            if col_diff % 3 == 2: return None
            byte_idx = (line_idx * 16) + (col_diff // 3)
            return byte_idx if byte_idx < len(self.byte_data) else None
        elif 59 <= col <= 74:
            byte_idx = (line_idx * 16) + (col - 59)
            return byte_idx if byte_idx < len(self.byte_data) else None
        return None

    def on_click(self, event):
        self._update_status_from_event(event, prefix="Clicked: ")

    def on_hover(self, event):
        self._update_status_from_event(event, prefix="Hover: ")

    def _update_status_from_event(self, event, prefix=""):
        if not self.byte_data: return
        byte_idx = self._get_byte_index_from_event(event)

        if byte_idx is not None:
            info = self.byte_map[byte_idx]
            hex_val = f"{self.byte_data[byte_idx]:02X}"
            self.status_var.set(f"{prefix}Byte 0x{byte_idx:X} [{hex_val}] - {info['desc']}")
        else:
            self.status_var.set(f"{prefix}Ready.")

if __name__ == "__main__":
    app = PreinstancedHexViewer()
    app.mainloop()