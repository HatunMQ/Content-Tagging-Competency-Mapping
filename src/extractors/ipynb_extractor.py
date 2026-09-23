"""
Extract chunks from a Jupyter notebook (.ipynb).

A notebook is parsed as plain JSON (no nbformat dependency needed — .ipynb
IS json). Cells are grouped under the nearest preceding markdown heading
(#, ##, ###) so one chunk = one learning section, not one raw cell —
this matches how a student actually experiences the notebook.
"""
import json
import re
from pathlib import Path


def _cell_text(cell: dict) -> str:
    src = cell.get("source", [])
    return "".join(src) if isinstance(src, list) else str(src)


def extract_ipynb(path: Path) -> list[dict]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = nb.get("cells", [])

    sections = []
    current = {"title": "Introduction", "parts": [], "start_cell": 0}

    for idx, cell in enumerate(cells):
        text = _cell_text(cell)
        if cell.get("cell_type") == "markdown":
            heading_match = re.match(r"^#{1,3}\s+(.*)", text.strip())
            if heading_match:
                if current["parts"]:
                    sections.append(current)
                current = {
                    "title": heading_match.group(1).strip(),
                    "parts": [],
                    "start_cell": idx,
                }
        tag = "markdown" if cell.get("cell_type") == "markdown" else "code"
        if text.strip():
            current["parts"].append(f"[{tag}]\n{text}")

    if current["parts"]:
        sections.append(current)

    chunks = []
    for i, sec in enumerate(sections, start=1):
        text = "\n\n".join(sec["parts"]).strip()
        if not text:
            continue
        chunks.append({
            "file_name": path.name,
            "chunk_id": f"section_{i:02d}",
            "content_type": "Code notebook",
            "text": text,
            "metadata": {
                "source_location": f"cell {sec['start_cell']}",
                "section_title": sec["title"],
            },
        })

    return chunks


if __name__ == "__main__":
    import sys

    p = Path(sys.argv[1])
    for c in extract_ipynb(p):
        print(json.dumps(c, ensure_ascii=False))