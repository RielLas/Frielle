"""
cogs/_attachments.py
Helper module for extracting text and image content from Discord message attachments.
Supports: .txt, .pdf, .docx, images (.png, .jpg, .jpeg, .webp, .gif).
"""

import io
import re
import logging

_TEXT_ATTACHMENT_EXTS = (".txt", ".pdf", ".docx")
_IMAGE_ATTACHMENT_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
ATTACHMENT_TEXT_MAX_CHARS = 4000


def _extract_txt_text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def _extract_docx_text(data: bytes) -> str:
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with zf.open("word/document.xml") as doc:
                tree = ET.parse(doc)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = []
        for para in tree.iter(f"{ns}p"):
            text = "".join(node.text or "" for node in para.iter(f"{ns}t"))
            if text.strip():
                paragraphs.append(text.strip())
        return "\n".join(paragraphs)
    except Exception as docx_err:
        logging.warning(f"DOCX text extraction failed: {docx_err}")
        return ""


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        pass
    return _extract_pdf_text_stream(data)


def _extract_pdf_text_stream(data: bytes) -> str:
    import zlib
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        raw = m.group(1)
        try:
            raw = zlib.decompress(raw)
        except Exception:
            continue
        for op in re.findall(rb"\((?:\\.|[^()\\])*\)\s*Tj|\[(?:[^\]]*)\]\s*TJ", raw):
            for s in re.findall(rb"\((?:\\.|[^()\\])*\)", op):
                txt = s[1:-1]
                txt = re.sub(
                    rb"\\([nrtbf()\\])",
                    lambda mm: {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}[mm.group(1)],
                    txt,
                )
                texts.append(txt.decode("utf-8", errors="replace"))
    return " ".join(t for t in texts if t.strip())


def extract_attachment_text(filename: str, data: bytes) -> str:
    if not filename:
        return ""
    lower = filename.lower()
    if lower.endswith(".txt"):
        text = _extract_txt_text(data)
    elif lower.endswith(".pdf"):
        text = _extract_pdf_text(data)
    elif lower.endswith(".docx"):
        text = _extract_docx_text(data)
    else:
        return ""
    text = text.strip()
    if len(text) > ATTACHMENT_TEXT_MAX_CHARS:
        marker = "\n...[truncated]"
        text = text[:ATTACHMENT_TEXT_MAX_CHARS - len(marker)].rstrip() + marker
    return text
