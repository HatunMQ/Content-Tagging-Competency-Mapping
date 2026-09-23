"""
Extract quiz questions from an .xlsx quiz file — one chunk per question.

Column names vary between quiz files, so this looks for common header
variants (case-insensitive) instead of assuming fixed column positions.
If a sheet doesn't look like a quiz table (no recognizable question
column), it's skipped rather than guessed at.
"""
from pathlib import Path

import openpyxl

import re

CANDIDATE_QUESTION_COLS = ["question", "question text", "quiz question", "q"]
CANDIDATE_ANSWER_COLS = ["correct answer", "answer", "correct_answer"]
# Some quiz files label options with letters (Option A/B/C/D), others with
# numbers (Option 1/2/3/4/5) -- both are real formats we've seen, so both
# are recognized rather than assuming one convention.
CANDIDATE_OPTION_COLS = ["option a", "option b", "option c", "option d", "a", "b", "c", "d"]
_OPTION_NUMBER_RE = re.compile(r"^option\s*\d+$")


def _is_option_col(header_lower: str) -> bool:
    return header_lower in CANDIDATE_OPTION_COLS or bool(_OPTION_NUMBER_RE.match(header_lower))


def _find_col(headers: list[str], candidates: list[str]):
    lower = [h.strip().lower() if h else "" for h in headers]
    for cand in candidates:
        if cand in lower:
            return lower.index(cand)
    return None


def extract_xlsx(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    chunks = []
    chunk_num = 0

    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        headers = [str(h) if h is not None else "" for h in rows[0]]
        q_idx = _find_col(headers, CANDIDATE_QUESTION_COLS)
        if q_idx is None:
            continue  # not a quiz-shaped sheet — skip it

        a_idx = _find_col(headers, CANDIDATE_ANSWER_COLS)
        opt_idxs = [i for i, h in enumerate(headers) if _is_option_col(h.strip().lower())]

        for row_num, row in enumerate(rows[1:], start=2):
            question = row[q_idx] if q_idx < len(row) else None
            if not question or not str(question).strip():
                continue

            chunk_num += 1
            options = [str(row[i]) for i in opt_idxs if i < len(row) and row[i] is not None]
            answer = row[a_idx] if (a_idx is not None and a_idx < len(row)) else None

            text_parts = [f"Question: {question}"]
            if options:
                text_parts.append("Options: " + " | ".join(options))
            if answer:
                text_parts.append(f"Correct answer: {answer}")

            chunks.append({
                "file_name": path.name,
                "chunk_id": f"q_{chunk_num:03d}",
                "content_type": "Quiz",
                "text": "\n".join(text_parts),
                "metadata": {"source_location": f"{sheet.title}!row{row_num}", "section_title": sheet.title},
            })

    return chunks


if __name__ == "__main__":
    import sys
    import json

    p = Path(sys.argv[1])
    for c in extract_xlsx(p):
        print(json.dumps(c, ensure_ascii=False))