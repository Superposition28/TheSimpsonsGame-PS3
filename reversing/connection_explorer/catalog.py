"""Coverage inventory includes every current format reference, including unknowns."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from .index import MODULE


ADAPTERS = {
    "lh2.html": "LH2 StringID definitions, text/labels and bounded pointers",
    "alb.html": "Alias definitions; contextual bank/stream and LH2 StringID references",
    "smb.html": "Bank/stream definitions and literal external SNU filenames",
    "tox.PS3.html": "Timing-record StringID references to LH2",
    "simgroup.dat.html": "SimGroup entity/attached-resource GUIDs; UIE LE-word GUID references",
    "bbn.PS3.html": "Bounded documented rig/alias tables; hashes and HAnim links (layout-dependent)",
    "acs.PS3.html": "Version-1 primitive binding references; remaining ID fields unresolved",
    "preinstanced.html": "Bounded RenderWare HAnim node IDs and named material textures",
    "txd.html": "Native RenderWare texture names; no invented texture hash algorithm",
    "graph.html": "Header GUID; graph node indices are internal, not cross-file IDs",
    "meta.xml.html": "MetaModel asset-table GUID references, source-inspected layout",
    "cec.ps3.html": "Config/event IDs and labels; external event joins remain raw candidates",
    "msb.html": "Observed MUS filename literals; transition/part state machine unresolved",
    "uix.html": "Observed resource filename literals; no full APT/font resolver",
    "index.html": "See container and suffix-specific adapters",
}


class PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title, self.in_title = "", False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data


def catalog() -> dict:
    root = MODULE / "reversing/docs"
    result = []
    for path in sorted((root / "PS3_GAME/FormatAnalysis").rglob("*.html")):
        if any(part in {"oldMDonly", ".history", ".backup"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if 'id="evidence-and-limitations"' not in text:
            continue
        parser = PlainText()
        parser.feed(text[:3000])
        result.append({"title": parser.title, "doc": path.relative_to(root).as_posix(),
                       "adapter": ADAPTERS.get(path.name, "Inventory + raw words/candidate matching. No verified cross-file layout adapter; consult the reference's limitations.")})
    return {"formats": result, "policy": "Only documented namespaces are joined structurally. Raw equality and filename associations are labeled separately. Internal offsets, bone indices and Havok fixups are not universal resource IDs."}
