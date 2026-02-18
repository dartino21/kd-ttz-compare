import difflib
import re
from typing import Any, Dict, List, Tuple

from pipeline.match_kd import find_best_block, normalize_text

NUM_UNIT_RE = re.compile(
    r"(?i)(\d+(?:[.,]\d+)?)\s*(лм|в|вт|кг|г|мм|см|м|а|ма|ач|мбит/с|бит/с|гб|%|℃|°c|град/сек|мгц|дбмвт|ip\d{2})"
)

MIN_RE = re.compile(r"(?i)\b(?:не\s+менее|не\s+ниже|минимум)\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?")
MAX_RE = re.compile(r"(?i)\b(?:не\s+более|не\s+выше|максимум)\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?")
RANGE_RE = re.compile(r"(?i)\bот\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?\s+до\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?")

def _to_float(x: str) -> float:
    return float(x.replace(",", "."))

def _norm_unit(u: str) -> str:
    return (u or "").strip().lower().replace("°c", "℃")

def diff_summary(a: str, b: str, max_lines: int = 8) -> str:
    a_lines = [a.strip()]
    b_lines = [b.strip()]
    d = list(difflib.unified_diff(a_lines, b_lines, lineterm=""))
    out = [line for line in d if line.startswith(("+", "-", "@@"))][:max_lines]
    return "\n".join(out).strip()

def extract_kd_values(snippet: str) -> List[Tuple[float, str]]:
    vals: List[Tuple[float, str]] = []
    for n, u in NUM_UNIT_RE.findall(snippet):
        vals.append((_to_float(n), _norm_unit(u)))
    return vals

def extract_kd_constraints(snippet: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in RANGE_RE.finditer(snippet):
        a, u1, b, u2 = m.group(1), m.group(2), m.group(3), m.group(4)
        unit = _norm_unit(u1 or u2 or "")
        out.append({"op": "range", "min": _to_float(a), "max": _to_float(b), "unit": unit})
    for m in MIN_RE.finditer(snippet):
        v, u = m.group(1), m.group(2)
        out.append({"op": ">=", "value": _to_float(v), "unit": _norm_unit(u or "")})
    for m in MAX_RE.finditer(snippet):
        v, u = m.group(1), m.group(2)
        out.append({"op": "<=", "value": _to_float(v), "unit": _norm_unit(u or "")})
    return out

def eval_constraints(req_constraints: List[Dict[str, Any]], snippet: str) -> Tuple[int, int, str]:
    """
    Возвращает:
      (satisfied, total, note)
    total — число "проверяемых" ограничений (>=, <=, range). raw не считаем строгим.
    """
    strict = [c for c in req_constraints if c.get("op") in (">=", "<=", "range")]
    if not strict:
        return 0, 0, ""

    kd_vals = extract_kd_values(snippet)
    kd_cons = extract_kd_constraints(snippet)

    satisfied = 0
    total = len(strict)
    notes: List[str] = []

    def best_val_for_unit(unit: str) -> Tuple[bool, float]:
        if not unit:
            # если единицы не указаны, берём любое число (очень грубо)
            return (len(kd_vals) > 0, kd_vals[0][0] if kd_vals else 0.0)
        same = [v for v, u in kd_vals if u == unit]
        if same:
            return (True, same[0])
        return (False, 0.0)

    for c in strict:
        op = c["op"]
        unit = _norm_unit(c.get("unit", ""))
        ok = None

        # Если в КД прямо повторено ограничение (в kd_cons) — это сильный сигнал
        for kc in kd_cons:
            if _norm_unit(kc.get("unit","")) != unit:
                continue
            if op == kc["op"]:
                if op == "range":
                    ok = (kc["min"] <= c["min"] and kc["max"] >= c["max"]) or (c["min"] <= kc["min"] <= kc["max"] <= c["max"])
                else:
                    # если в КД написано "не менее X" — удовлетворяет, если X >= требуемого
                    if op == ">=":
                        ok = kc["value"] >= c["value"]
                    elif op == "<=":
                        ok = kc["value"] <= c["value"]
                if ok is True:
                    break

        if ok is None:
            has, v = best_val_for_unit(unit)
            if not has:
                notes.append(f"нет значения для единицы '{unit}'")
                continue
            if op == ">=":
                ok = v >= c["value"]
            elif op == "<=":
                ok = v <= c["value"]
            else:  # range
                ok = (v >= c["min"] and v <= c["max"])

        if ok:
            satisfied += 1
        else:
            notes.append(f"числовое несоответствие ({op} {c.get('value', '') or (str(c.get('min'))+'..'+str(c.get('max')))} {unit})")

    return satisfied, total, "; ".join(notes)

def compare_requirements(requirements, kd_text: str) -> list[dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for req in requirements:
        best = find_best_block(
            kd_text=kd_text,
            req_num=req.num,
            req_text=req.text,
            req_nums_units=req.nums_units
        )

        snippet = best["evidence"]
        match_type = best["match_type"]

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

        # Инженерная проверка чисел (>=, <=, диапазон)
        sat, tot, note = eval_constraints(getattr(req, "constraints", []), snippet)

        if tot == 0:
            # нет строгих ограничений — просто FOUND, но тип покажем
            status = "FOUND"
            numbers = ""
        else:
            numbers = f"{sat}/{tot}"
            if sat == tot:
                status = "OK"
            else:
                status = "PARTIAL"

        if note:
            match_type = f"{match_type}; {note}"

        rows.append({
            "req_id": req.req_id,
            "ttz_section": req.section,
            "req_text": req.text,
            "status": status,
            "match_type": match_type,
            "kd_evidence": snippet,
            "numbers_covered": numbers,
            "diff": diff_summary(req.text, snippet),
        })

    return rows
