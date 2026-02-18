import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# 1) Ловим заголовки вида "3.2.4.1 Требования ..." или "3.2.4.1."
HEADING_NUM_RE = re.compile(r"(?m)^\s*(?P<num>\d+(?:\.\d+)+)\.?\s+(?P<text>.+?)\s*$")

# 2) Ловим строгие "номерные" требования вида "2.2.1. текст"
REQ_LINE_RE = re.compile(
    r"""(?mx)
    ^\s*(?:[\*\-\u2022]\s*)?
    (?P<num>\d+(?:\.\d+)+)\.\s*
    (?P<text>.+?)\s*$
    """
)

# 3) Ловим буллеты "- ...."
BULLET_RE = re.compile(r"(?m)^\s*[-\u2022]\s+(?P<text>.+?)\s*$")

SECTION_RE = re.compile(r"(?mi)^\s*(?:Раздел|раздел)\s+(?P<sec>\d+)\.\s*(?P<title>.+?)\s*$")

# Числа + единицы (расширили)
NUM_UNIT_RE = re.compile(
    r"(?i)(\d+(?:[.,]\d+)?)\s*(лм|в|вт|кг|г|мм|см|м|а|ма|ач|мбит/с|бит/с|гб|%|℃|°c|град/сек|мгц|дбмвт|ip\d{2})"
)

# Ограничения "не менее/не более/от...до..."
MIN_RE = re.compile(r"(?i)\b(?:не\s+менее|не\s+ниже|минимум)\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?")
MAX_RE = re.compile(r"(?i)\b(?:не\s+более|не\s+выше|максимум)\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?")
RANGE_RE = re.compile(r"(?i)\bот\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?\s+до\s+(\d+(?:[.,]\d+)?)\s*([^\s,;:.]+)?")

def _norm_unit(u: Optional[str]) -> str:
    if not u:
        return ""
    u = u.strip().lower().replace("°c", "℃")
    return u

def _to_float(x: str) -> float:
    return float(x.replace(",", "."))

def extract_constraints(text: str) -> List[Dict[str, Any]]:
    """
    Возвращает список ограничений: >=, <=, range.
    """
    out: List[Dict[str, Any]] = []

    for m in RANGE_RE.finditer(text):
        a, u1, b, u2 = m.group(1), m.group(2), m.group(3), m.group(4)
        unit = _norm_unit(u1 or u2)
        out.append({"op": "range", "min": _to_float(a), "max": _to_float(b), "unit": unit})

    for m in MIN_RE.finditer(text):
        v, u = m.group(1), m.group(2)
        out.append({"op": ">=", "value": _to_float(v), "unit": _norm_unit(u)})

    for m in MAX_RE.finditer(text):
        v, u = m.group(1), m.group(2)
        out.append({"op": "<=", "value": _to_float(v), "unit": _norm_unit(u)})

    # Если не нашли явных "не менее/не более", но есть числа+единицы — сохраним как "raw"
    # (это помогает в скоринге, даже если проверить строго нельзя)
    if not out:
        nums_units = [(a.replace(",", "."), _norm_unit(b)) for a, b in NUM_UNIT_RE.findall(text)]
        for a, b in nums_units:
            out.append({"op": "raw", "value": _to_float(a), "unit": b})

    return out

@dataclass
class Requirement:
    req_id: str
    num: str                  # для ссылок типа "п. 2.2.2 ТЗ"
    section: str
    text: str
    nums_units: list[tuple[str, str]]
    constraints: List[Dict[str, Any]]
    kind: str                 # numeric / qualitative / composition / other

def _classify_requirement(text: str, constraints: List[Dict[str, Any]]) -> str:
    t = text.lower()
    if "в состав" in t and ("долж" in t or "вход" in t):
        return "composition"
    if any(c["op"] in (">=", "<=", "range") for c in constraints):
        return "numeric"
    if "долж" in t or "обеспеч" in t:
        return "qualitative"
    return "other"

def parse_ttz_requirements(ttz_text: str) -> List[Requirement]:
    current_section = ""
    current_heading_num: Optional[str] = None
    bullet_idx = 0

    requirements: List[Requirement] = []
    lines = ttz_text.splitlines()

    for raw in lines:
        s = raw.strip()
        if not s:
            continue

        msec = SECTION_RE.match(s)
        if msec:
            current_section = f"Раздел {msec.group('sec')}: {msec.group('title')}"
            current_heading_num = None
            bullet_idx = 0
            continue

        # Заголовок подпункта (например "3.2.4.1 Требования ...")
        mh = HEADING_NUM_RE.match(s)
        if mh and "требован" in mh.group("text").lower():
            current_heading_num = mh.group("num")
            bullet_idx = 0
            continue

        # Строго номерная строка "2.2.1. ..."
        m = REQ_LINE_RE.match(s)
        if m:
            num = m.group("num")
            text = m.group("text").strip()
            nums_units = [(a.replace(",", "."), _norm_unit(b)) for a, b in NUM_UNIT_RE.findall(text)]
            constraints = extract_constraints(text)
            kind = _classify_requirement(text, constraints)
            requirements.append(
                Requirement(
                    req_id=f"TTZ-{num}",
                    num=num,
                    section=current_section or "UNKNOWN",
                    text=text,
                    nums_units=nums_units,
                    constraints=constraints,
                    kind=kind,
                )
            )
            continue

        # Буллеты под текущим подпунктом: "- ..."
        mb = BULLET_RE.match(raw)
        if mb and current_heading_num:
            bullet_idx += 1
            text = mb.group("text").strip()
            # Присваиваем псевдо-номер, чтобы сохранялась связь с подпунктом
            num = f"{current_heading_num}-b{bullet_idx}"
            nums_units = [(a.replace(",", "."), _norm_unit(b)) for a, b in NUM_UNIT_RE.findall(text)]
            constraints = extract_constraints(text)
            kind = _classify_requirement(text, constraints)
            requirements.append(
                Requirement(
                    req_id=f"TTZ-{num}",
                    num=num,
                    section=current_section or "UNKNOWN",
                    text=text,
                    nums_units=nums_units,
                    constraints=constraints,
                    kind=kind,
                )
            )

    return requirements
