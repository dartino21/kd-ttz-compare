import re
from typing import List, Optional, Dict, Any, Tuple

STOPWORDS = {
    "и","в","во","на","по","к","с","со","из","для","не","что","это","как",
    "а","но","или","ли","же","бы","при","от","до","над","под","о","об",
    "должна","должен","должны","обеспечивать","обеспечивает","обеспечение",
    "возможность","выполнение","проведение"
}

def normalize_text(s: str) -> str:
    s = s.lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def tokenize(s: str) -> List[str]:
    s = normalize_text(s)
    tokens = re.split(r"[^a-zа-я0-9%℃°./\-]+", s)
    out = []
    for t in tokens:
        if not t or len(t) < 3:
            continue
        if t in STOPWORDS:
            continue
        out.append(t)
    return out

def split_into_blocks(kd_text: str) -> List[str]:
    """
    Делим КД на смысловые блоки.
    1) Сначала по пустым строкам
    2) Если пустых строк нет — по "длинным" переносам
    """
    text = kd_text.replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(parts) >= 5:
        return parts

    # fallback: резать по строкам и склеивать в блоки
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    blocks: List[str] = []
    buf: List[str] = []
    for l in lines:
        buf.append(l)
        if len(" ".join(buf)) >= 700:
            blocks.append(" ".join(buf))
            buf = []
    if buf:
        blocks.append(" ".join(buf))
    return blocks or [kd_text.strip()]

def find_all_explicit_refs(kd_text: str, req_num: str) -> List[Tuple[int, int]]:
    """
    Находит все вхождения ссылок вида "п. 2.2.2 ТЗ" / "2.2.2 ТЗ" / "пункт 2.2.2"
    """
    n = re.escape(req_num)
    pat = re.compile(rf"(?is)(п\.\s*{n}\s*(?:тз|техническ\w*\s+задан\w*)|{n}\s*(?:тз|техническ\w*\s+задан\w*)|пункт\w*\s+{n})")
    return [(m.start(), m.end()) for m in pat.finditer(kd_text)]

def pick_window(kd_text: str, start: int, end: int, window: int = 450) -> str:
    a = max(0, start - window)
    b = min(len(kd_text), end + window)
    return kd_text[a:b].strip()

def score_block(req_tokens: List[str], req_nums_units: List[tuple[str,str]], block: str) -> float:
    """
    Скоринг блока по:
    - совпадению токенов (Jaccard-like)
    - наличию чисел/единиц
    """
    bt = tokenize(block)
    if not bt:
        return 0.0
    bset = set(bt)
    rset = set(req_tokens)

    overlap = len(rset & bset)
    denom = max(1, len(rset))
    tok_score = overlap / denom

    num_score = 0.0
    s = normalize_text(block)
    for num, unit in req_nums_units:
        if num and (num in s):
            num_score += 0.6
        if unit and (unit in s):
            num_score += 0.4

    # ограничим
    num_score = min(2.0, num_score)

    return tok_score * 3.0 + num_score

def find_best_block(
        kd_text: str,
        req_num: str,
        req_text: str,
        req_nums_units: List[tuple[str,str]]
) -> Dict[str, Any]:
    """
    Возвращает:
      {
        "evidence": "...",
        "match_type": "...",
        "score": float
      }
    """
    kd_norm = normalize_text(kd_text)
    req_tokens = tokenize(req_text)

    # 1) Сильнейший сигнал: явная ссылка на пункт ТЗ
    refs = find_all_explicit_refs(kd_norm, req_num)
    if refs:
        # берём первый лучший (обычно достаточно)
        start, end = refs[0]
        return {
            "evidence": pick_window(kd_text, start, end, window=500),
            "match_type": "explicit_ref",
            "score": 10.0
        }

    # 2) Блочная эвристика: выбираем лучший блок по скорингу
    blocks = split_into_blocks(kd_text)
    best = {"evidence": "", "match_type": "", "score": 0.0}

    for b in blocks:
        sc = score_block(req_tokens, req_nums_units, b)
        if sc > best["score"]:
            best = {"evidence": b.strip(), "match_type": "scored_block", "score": sc}

    # если совсем низкий скор — считаем не найдено
    if best["score"] < 0.9:
        return {"evidence": "", "match_type": "", "score": 0.0}

    # Подрежем evidence чтобы не было слишком длинно
    ev = best["evidence"]
    if len(ev) > 1200:
        ev = ev[:1200].rstrip() + "..."
    best["evidence"] = ev
    return best
