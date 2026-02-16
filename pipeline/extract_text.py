import io
import fitz  # PyMuPDF
from docx import Document

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts = []
    for i in range(doc.page_count):
        parts.append(doc.load_page(i).get_text("text"))
    return "\n".join(parts).strip()

def extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    f = io.BytesIO(docx_bytes)
    doc = Document(f)
    return "\n".join(p.text for p in doc.paragraphs).strip()

def extract_text(file_bytes: bytes, filename: str) -> tuple[str, dict]:
    """
    Returns: (text, meta)
    meta can store stats and later OCR artifacts.
    """
    name = filename.lower().strip()
    meta = {"method": None, "text_len": 0}

    if name.endswith(".pdf"):
        text = extract_text_from_pdf_bytes(file_bytes)
        meta["method"] = "pdf_text"
    elif name.endswith(".docx"):
        text = extract_text_from_docx_bytes(file_bytes)
        meta["method"] = "docx_text"
    else:
        # For MVP: treat as plain text if possible
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
            meta["method"] = "plain_decode"
        except Exception:
            text = ""
            meta["method"] = "unknown"

    meta["text_len"] = len(text)

    # FUTURE HOOK:
    # if meta["text_len"] < SOME_THRESHOLD:
    #    text = run_ocr_vlm(file_bytes, filename)
    #    meta["method"] = "ocr_vlm"

    return text, meta
