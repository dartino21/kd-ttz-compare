import re
from typing import Optional

def find_explicit_ref_snippet(kd_text: str, req_num: str, window: int = 400) -> Optional[str]:
    # Strong signal: "п. 2.2.2 ТЗ" etc.
    pat = re.compile(rf"(?is)(п\.\s*{re.escape(req_num)}\s*тз|п\.\s*{re.escape(req_num)}\s*тз/тз|{re.escape(req_num)}\s*тз)")
    m = pat.search(kd_text)
    if not m:
        return None
    start = max(0, m.start() - window)
    end = min(len(kd_text), m.end() + window)
    return kd_text[start:end].strip()

def find_keyword_number_snippet(kd_text: str, req_text: str, nums_units: list[tuple[str,str]], window: int = 450) -> Optional[str]:
    # fallback: search by first number+unit or by a keyword chunk
    if nums_units:
        num, unit = nums_units[0]
        pat = re.compile(rf"(?is)(.{0,120}{re.escape(num)}\s*{re.escape(unit)}.{0,220})")
        m = pat.search(kd_text)
        if m:
            return m.group(1).strip()

    # fallback keywords: take a few longer tokens
    tokens = [t for t in re.split(r"\W+", req_text.lower()) if len(t) >= 5]
    if not tokens:
        return None
    key = tokens[0]
    pat = re.compile(rf"(?is)(.{0,180}{re.escape(key)}.{0,280})")
    m = pat.search(kd_text)
    return m.group(1).strip() if m else None
