import re
from dataclasses import dataclass
from typing import List, Optional

REQ_LINE_RE = re.compile(
    r"""(?mx)
    ^\s*(?:[\*\-\u2022]\s*)?          # optional bullet like "*" or "-"
    (?P<num>\d+(?:\.\d+)+)\.\s*       # 2.2.1.
    (?P<text>.+?)\s*$                # text
    """
)

SECTION_RE = re.compile(r"(?mi)^\s*Раздел\s+(?P<sec>\d+)\.\s*(?P<title>.+?)\s*$")

NUM_UNIT_RE = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*(лм|в|вт|кг|г|мм|см|м|ч|час|часов|%|ip\d{2})")

@dataclass
class Requirement:
    req_id: str          # e.g. TTZ-2.2.1
    num: str             # 2.2.1
    section: str         # "Раздел 2" or more specific if you later want
    text: str
    nums_units: list[tuple[str, str]]

def parse_ttz_requirements(ttz_text: str) -> List[Requirement]:
    current_section = ""
    requirements: List[Requirement] = []

    lines = ttz_text.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            continue

        msec = SECTION_RE.match(s)
        if msec:
            current_section = f"Раздел {msec.group('sec')}: {msec.group('title')}"
            continue

        m = REQ_LINE_RE.match(s)
        if not m:
            continue

        num = m.group("num")
        text = m.group("text").strip()
        nums_units = [(a.replace(",", "."), b.lower()) for a, b in NUM_UNIT_RE.findall(text)]
        requirements.append(
            Requirement(
                req_id=f"TTZ-{num}",
                num=num,
                section=current_section or "UNKNOWN",
                text=text,
                nums_units=nums_units,
            )
        )

    return requirements
