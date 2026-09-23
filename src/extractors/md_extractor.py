"""
Extract chunks from a Markdown (.md) file — one chunk per heading section
(#, ##, ###). A file with no headings comes back as a single chunk.
"""
import re
from pathlib import Path


def extract_md(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    sections = []
    current_title = "Introduction"
    current_lines: list[str] = []
    start_line = 1

    for i, line in enumerate(lines, start=1):
        heading = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading:
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip(), start_line))
            current_title = heading.group(2).strip()
            current_lines = []
            start_line = i
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip(), start_line))

    # Heuristic: hands-on/lab files are "Practical lab", everything else
    # plain-markdown is "Reading". Adjust the keyword list to your file names.
    is_lab = any(kw in path.name.lower() for kw in ["handson", "hands-on", "lab"])
    content_type = "Practical lab" if is_lab else "Reading"

    chunks = []
    for i, (title, body, line_no) in enumerate(sections, start=1):
        if not body.strip():
            continue
        chunks.append({
            "file_name": path.name,
            "chunk_id": f"section_{i:02d}",
            "content_type": content_type,
            "text": body,
            "metadata": {"source_location": f"line {line_no}", "section_title": title},
        })

    return chunks


if __name__ == "__main__":
    import sys
    import json

    p = Path(sys.argv[1])
    for c in extract_md(p):
        print(json.dumps(c, ensure_ascii=False))