import difflib
from typing import Any
from pipeline.match_kd import find_explicit_ref_snippet, find_keyword_number_snippet

def numbers_covered(req_nums_units: list[tuple[str,str]], snippet: str) -> tuple[int,int]:
    """
    Returns (covered, total).
    We consider covered if "num"+"unit" appear in snippet (roughly).
    """
    total = len(req_nums_units)
    if total == 0:
        return (0, 0)
    s = snippet.lower()
    covered = 0
    for num, unit in req_nums_units:
        if (num in s) and (unit in s):
            covered += 1
    return covered, total

def diff_summary(a: str, b: str, max_lines: int = 8) -> str:
    a_lines = [a.strip()]
    b_lines = [b.strip()]
    d = list(difflib.unified_diff(a_lines, b_lines, lineterm=""))
    # Keep it short
    out = [line for line in d if line.startswith(("+", "-", "@@"))][:max_lines]
    return "\n".join(out).strip()

def compare_requirements(requirements, kd_text: str) -> list[dict[str, Any]]:
    rows = []
    for req in requirements:
        snippet = find_explicit_ref_snippet(kd_text, req.num)
        match_type = "explicit_ref" if snippet else None

        if not snippet:
            snippet = find_keyword_number_snippet(kd_text, req.text, req.nums_units)
            match_type = "heuristic" if snippet else None

        if not snippet:
            rows.append({
                "req_id": req.req_id,
                "ttz_section": req.section,
                "req_text": req.text,
                "status": "NOT_FOUND",
                "match_type": "",
                "kd_evidence": "",
                "numbers_covered": "",
                "diff": "",
            })
            continue

        cov, tot = numbers_covered(req.nums_units, snippet)
        if tot == 0:
            status = "FOUND"
        else:
            status = "OK" if cov == tot else "PARTIAL"

        rows.append({
            "req_id": req.req_id,
            "ttz_section": req.section,
            "req_text": req.text,
            "status": status,
            "match_type": match_type,
            "kd_evidence": snippet,
            "numbers_covered": f"{cov}/{tot}" if tot else "",
            "diff": diff_summary(req.text, snippet),
        })
    return rows
