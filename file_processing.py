"""
Vigzone AI - File Processing
=============================
Turns uploaded files into a form the chat model can consume:

- Images  -> resized/compressed and base64-encoded as a data URI, sent to
  Groq's vision model as an `image_url` content part.
- Documents (PDF, DOCX, TXT/MD/CSV) -> plain extracted text, which gets
  folded into the user's message as context for a normal text model.

Kept deliberately simple/dependency-light: pypdf for PDFs, python-docx for
Word docs, Pillow for image resizing.
"""

from __future__ import annotations

import base64
import io

from docx import Document
from PIL import Image
from pypdf import PdfReader

# Keep encoded images small enough to be cheap to send and to not bloat
# browser localStorage (the frontend keeps conversation history there).
MAX_IMAGE_DIMENSION = 1280
IMAGE_JPEG_QUALITY = 82

# Cap extracted document text so one huge file can't blow out the model's
# context window or the request payload. Generous enough for most reports.
MAX_DOC_CHARS = 15_000


class FileProcessingError(Exception):
    """Raised when a file can't be read or converted into a usable form."""


def _truncate(text: str) -> tuple[str, bool]:
    text = text.strip()
    if len(text) > MAX_DOC_CHARS:
        return text[:MAX_DOC_CHARS], True
    return text, False


def process_image(data: bytes) -> tuple[str, str]:
    """Resize/compress an image and return (data_uri, mime_type)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise FileProcessingError(
            "That doesn't look like a readable image file."
        ) from e

    is_png = img.format == "PNG"

    if not is_png and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    width, height = img.size
    if max(width, height) > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / max(width, height)
        img = img.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.LANCZOS,
        )

    buf = io.BytesIO()
    if is_png:
        img.save(buf, format="PNG", optimize=True)
        mime_type = "image/png"
    else:
        img.save(buf, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
        mime_type = "image/jpeg"
        
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}", mime_type


def extract_pdf_text(data: bytes) -> tuple[str, bool]:
    """Extract text from a PDF. Returns (text, was_truncated)."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise FileProcessingError("Couldn't open that PDF — it may be corrupted.") from e

    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n\n".join(p for p in pages if p.strip())

    if not text.strip():
        raise FileProcessingError(
            "No extractable text found in that PDF — it may be a scanned "
            "image with no text layer."
        )
    return _truncate(text)


def extract_docx_text(data: bytes) -> tuple[str, bool]:
    """Extract text (paragraphs + table cells) from a Word document."""
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise FileProcessingError("Couldn't open that Word document.") from e

    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    text = "\n".join(parts)
    if not text.strip():
        raise FileProcessingError("That document appears to be empty.")
    return _truncate(text)


def extract_plain_text(data: bytes) -> tuple[str, bool]:
    """Decode a plain-text file (.txt, .md, .csv)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    if not text.strip():
        raise FileProcessingError("That file appears to be empty.")
    return _truncate(text)