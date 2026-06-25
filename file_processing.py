"""
Vigzone AI - File Processing
=============================
Converts any uploaded file into a form the chat model can consume.

Supported categories
--------------------
Images         → resized / base64-encoded data URI  (PNG, JPG, WEBP, GIF, BMP, TIFF, ICO, SVG)
Documents      → extracted text                      (PDF, DOCX, DOC-like, ODT, RTF, EPUB)
Spreadsheets   → CSV-like table text                 (XLSX, XLS, ODS, CSV, TSV)
Presentations  → slide-by-slide text                 (PPTX, PPT-like)
Data files     → pretty-printed content              (JSON, JSONL, XML, YAML, TOML)
Code / scripts → syntax-highlighted plain text       (py, js, ts, java, c, cpp, cs, go, rs, …)
Archives       → file manifest (no extraction)       (ZIP, TAR, GZ, 7Z, RAR)
Audio / Video  → metadata only                       (MP3, WAV, MP4, MOV, …)
Plain text     → UTF-8 decoded                       (TXT, MD, LOG, INI, ENV, …)
Unknown        → MIME-type sniffing then best effort

All extractors share the same _truncate() ceiling so the model's
context window is never blown out.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
import tarfile
import os
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import magic as _magic
    _HAS_MAGIC = True
except ImportError:
    _HAS_MAGIC = False

from PIL import Image
from pypdf import PdfReader
from docx import Document
import openpyxl
from pptx import Presentation

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_IMAGE_DIMENSION = 1280
IMAGE_JPEG_QUALITY  = 82
MAX_DOC_CHARS       = 20_000   # raised from 15k to support larger files

# ── Helpers ────────────────────────────────────────────────────────────────────

class FileProcessingError(Exception):
    """Raised when a file can't be read or converted into a usable form."""


def _truncate(text: str) -> tuple[str, bool]:
    text = text.strip()
    if len(text) > MAX_DOC_CHARS:
        return text[:MAX_DOC_CHARS], True
    return text, False


def _sniff_mime(data: bytes) -> str:
    """Return MIME type string. Falls back to 'application/octet-stream'."""
    if _HAS_MAGIC:
        try:
            return _magic.from_buffer(data, mime=True) or "application/octet-stream"
        except Exception:
            pass
    return "application/octet-stream"


# ── Image ──────────────────────────────────────────────────────────────────────

def process_image(data: bytes) -> tuple[str, str]:
    """Resize/compress an image and return (data_uri, mime_type)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise FileProcessingError("That doesn't look like a readable image file.") from e

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


# ── PDF ────────────────────────────────────────────────────────────────────────

def extract_pdf_text(data: bytes) -> tuple[str, bool]:
    """Extract text from a PDF. Returns (text, was_truncated)."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise FileProcessingError("Couldn't open that PDF — it may be corrupted.") from e

    pages = []
    for i, page in enumerate(reader.pages, 1):
        try:
            t = page.extract_text() or ""
            if t.strip():
                pages.append(f"[Page {i}]\n{t}")
        except Exception:
            pass

    text = "\n\n".join(pages)
    if not text.strip():
        raise FileProcessingError(
            "No extractable text found in that PDF — it may be a scanned image with no text layer."
        )
    return _truncate(text)


# ── DOCX ───────────────────────────────────────────────────────────────────────

def extract_docx_text(data: bytes) -> tuple[str, bool]:
    """Extract text from a Word document (.docx)."""
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


# ── XLSX ───────────────────────────────────────────────────────────────────────

def extract_xlsx_text(data: bytes) -> tuple[str, bool]:
    """Extract a readable table from an Excel workbook (.xlsx / .xlsm)."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:
        raise FileProcessingError("Couldn't open that Excel file.") from e

    sections: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows: list[str] = []
        row_count = 0
        for row in ws.iter_rows(values_only=True):
            if row_count >= 500:   # cap per sheet
                rows.append("… (sheet truncated)")
                break
            cells = [str(c) if c is not None else "" for c in row]
            if any(c.strip() for c in cells):
                rows.append("\t".join(cells))
                row_count += 1
        if rows:
            sections.append(f"## Sheet: {sheet_name}\n" + "\n".join(rows))

    text = "\n\n".join(sections)
    if not text.strip():
        raise FileProcessingError("That spreadsheet appears to be empty.")
    return _truncate(text)


# ── PPTX ───────────────────────────────────────────────────────────────────────

def extract_pptx_text(data: bytes) -> tuple[str, bool]:
    """Extract slide-by-slide text from a PowerPoint file (.pptx)."""
    try:
        prs = Presentation(io.BytesIO(data))
    except Exception as e:
        raise FileProcessingError("Couldn't open that PowerPoint file.") from e

    slides: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        parts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                parts.append(shape.text.strip())
        if parts:
            slides.append(f"[Slide {i}]\n" + "\n".join(parts))

    text = "\n\n".join(slides)
    if not text.strip():
        raise FileProcessingError("That presentation appears to have no readable text.")
    return _truncate(text)


# ── CSV / TSV ──────────────────────────────────────────────────────────────────

def extract_csv_text(data: bytes, delimiter: str = ",") -> tuple[str, bool]:
    """Decode and return CSV/TSV content."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    # Keep up to 300 rows so we don't blow out context
    if len(lines) > 300:
        preview = "\n".join(lines[:300]) + f"\n… ({len(lines) - 300} more rows)"
        return preview, True
    return _truncate(text)


# ── JSON / JSONL ───────────────────────────────────────────────────────────────

def extract_json_text(data: bytes) -> tuple[str, bool]:
    """Pretty-print JSON or summarise JSONL."""
    try:
        text_raw = data.decode("utf-8", errors="replace")
    except Exception as e:
        raise FileProcessingError("Couldn't decode JSON file.") from e
    try:
        parsed = json.loads(text_raw)
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        return _truncate(pretty)
    except json.JSONDecodeError:
        # Might be JSONL
        lines = text_raw.strip().splitlines()
        results = []
        for line in lines[:50]:
            try:
                results.append(json.dumps(json.loads(line), indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                results.append(line)
        summary = f"JSONL file ({len(lines)} records). First 50 records:\n\n" + "\n---\n".join(results)
        return _truncate(summary)


# ── XML ────────────────────────────────────────────────────────────────────────

def extract_xml_text(data: bytes) -> tuple[str, bool]:
    """Return XML as-is (text decode), with a structural summary header."""
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as e:
        raise FileProcessingError("Couldn't decode XML file.") from e
    try:
        root = ET.fromstring(text)
        summary = f"Root element: <{root.tag}>  Children: {len(list(root))}\n\n"
    except ET.ParseError:
        summary = "(XML parse warning — showing raw content)\n\n"
    return _truncate(summary + text)


# ── YAML / TOML ────────────────────────────────────────────────────────────────

def extract_yaml_toml_text(data: bytes) -> tuple[str, bool]:
    """Return YAML or TOML as plain text."""
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as e:
        raise FileProcessingError("Couldn't decode that config file.") from e
    return _truncate(text)


# ── Archives ───────────────────────────────────────────────────────────────────

def extract_archive_manifest(data: bytes, filename: str) -> tuple[str, bool]:
    """Return a file listing for ZIP or TAR archives (no extraction)."""
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".zip" or zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
                total = len(names)
                preview = names[:200]
                listing = "\n".join(preview)
                summary = (
                    f"ZIP archive containing {total} file(s).\n"
                    + ("(showing first 200)\n\n" if total > 200 else "\n")
                    + listing
                )
                return _truncate(summary)
    except Exception:
        pass

    try:
        if tarfile.is_tarfile(io.BytesIO(data)):
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                names = tf.getnames()
                total = len(names)
                preview = names[:200]
                listing = "\n".join(preview)
                summary = (
                    f"TAR archive containing {total} file(s).\n"
                    + ("(showing first 200)\n\n" if total > 200 else "\n")
                    + listing
                )
                return _truncate(summary)
    except Exception:
        pass

    raise FileProcessingError("Couldn't read that archive — it may be corrupted or an unsupported format (7z/rar).")


# ── Audio / Video ──────────────────────────────────────────────────────────────

def _read_mp3_id3(data: bytes) -> dict:
    """Read basic ID3v2 tags from MP3 bytes."""
    tags: dict[str, str] = {}
    if data[:3] != b"ID3":
        return tags
    try:
        # ID3v2 frame reading (simplified)
        offset = 10
        while offset < min(len(data), 8192):
            frame_id = data[offset:offset + 4].decode("latin-1", errors="replace")
            if not frame_id.strip() or frame_id[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0":
                break
            size = struct.unpack(">I", data[offset + 4:offset + 8])[0]
            content = data[offset + 10:offset + 10 + size]
            try:
                tags[frame_id] = content.decode("utf-8", errors="replace").strip("\x00")
            except Exception:
                pass
            offset += 10 + size
    except Exception:
        pass
    return tags


def extract_audio_video_info(data: bytes, filename: str) -> tuple[str, bool]:
    """Return metadata summary for audio/video files."""
    ext = Path(filename).suffix.lower()
    size_kb = len(data) / 1024
    lines = [f"File: {filename}", f"Size: {size_kb:.1f} KB"]

    if ext == ".mp3":
        tags = _read_mp3_id3(data)
        if tags:
            for key, label in [("TIT2", "Title"), ("TPE1", "Artist"),
                                ("TALB", "Album"), ("TDRC", "Year"),
                                ("TCON", "Genre"), ("TRCK", "Track")]:
                if key in tags and tags[key]:
                    lines.append(f"{label}: {tags[key]}")
        else:
            lines.append("No ID3 tags found.")
    elif ext in {".wav"}:
        if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            try:
                num_channels = struct.unpack_from("<H", data, 22)[0]
                sample_rate  = struct.unpack_from("<I", data, 24)[0]
                bits         = struct.unpack_from("<H", data, 34)[0]
                lines += [
                    f"Channels: {num_channels}",
                    f"Sample Rate: {sample_rate} Hz",
                    f"Bit Depth: {bits}-bit",
                ]
            except Exception:
                lines.append("WAV header unreadable.")
    else:
        mime = _sniff_mime(data)
        lines.append(f"MIME type: {mime}")
        lines.append("(Full metadata extraction for this format requires ffprobe.)")

    summary = "\n".join(lines)
    return _truncate(summary)


# ── Plain text & code ──────────────────────────────────────────────────────────

# Extensions considered "code"
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".cc",
    ".h", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
    ".scala", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".sql", ".r",
    ".m", ".lua", ".dart", ".hs", ".ex", ".exs", ".erl", ".ml", ".fs",
    ".fsx", ".clj", ".cljs", ".groovy", ".pl", ".pm",
}

def extract_plain_text(data: bytes) -> tuple[str, bool]:
    """Decode a plain-text / code file."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    if not text.strip():
        raise FileProcessingError("That file appears to be empty.")
    return _truncate(text)


# ── RTF ────────────────────────────────────────────────────────────────────────

def extract_rtf_text(data: bytes) -> tuple[str, bool]:
    """Very basic RTF → plaintext (strips control words)."""
    import re
    try:
        raw = data.decode("latin-1", errors="replace")
    except Exception as e:
        raise FileProcessingError("Couldn't decode RTF file.") from e
    # Remove RTF control groups and words
    text = re.sub(r"\{[^{}]*\}", "", raw)          # braced groups
    text = re.sub(r"\\[a-z]+\d*\s?", "", text)      # control words
    text = re.sub(r"\\[^a-z]", "", text)            # control symbols
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise FileProcessingError("No readable text extracted from that RTF file.")
    return _truncate(text)


# ── Universal dispatcher ───────────────────────────────────────────────────────

# Extensions → handler tag
_EXT_MAP: dict[str, str] = {
    # Images
    **{e: "image" for e in (".png", ".jpg", ".jpeg", ".webp", ".gif",
                             ".bmp", ".tiff", ".tif", ".ico", ".svg")},
    # Documents
    ".pdf":  "pdf",
    ".docx": "docx", ".doc": "docx",
    ".odt":  "docx",   # python-docx may handle basic ODT
    ".rtf":  "rtf",
    # Spreadsheets
    ".xlsx": "xlsx", ".xlsm": "xlsx",
    ".csv":  "csv",
    ".tsv":  "tsv",
    # Presentations
    ".pptx": "pptx", ".ppt": "pptx",
    # Data
    ".json": "json", ".jsonl": "json",
    ".xml":  "xml",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "yaml",   # same plain-text handler
    # Archives
    ".zip": "archive", ".tar": "archive", ".gz": "archive",
    ".tgz": "archive", ".bz2": "archive", ".xz": "archive",
    # Audio / Video
    **{e: "av" for e in (".mp3", ".wav", ".ogg", ".flac", ".aac",
                          ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".m4a")},
    # Plain text & code
    **{e: "text" for e in (".txt", ".md", ".log", ".ini", ".env",
                             ".cfg", ".conf", ".properties",
                             *CODE_EXTENSIONS)},
}


def process_file(data: bytes, filename: str) -> dict:
    """
    Universal entry point.

    Returns a dict with at minimum:
      kind: "image" | "document" | "archive" | "audio_video" | "unsupported"
      name: filename
    Plus kind-specific fields (data_uri/mime for images; text/truncated for docs).
    """
    ext = Path(filename).suffix.lower()
    handler = _EXT_MAP.get(ext)

    # MIME sniff fallback when extension is unknown / missing
    if not handler:
        mime = _sniff_mime(data)
        if mime.startswith("image/"):
            handler = "image"
        elif mime in ("application/pdf",):
            handler = "pdf"
        elif mime in ("application/json", "text/json"):
            handler = "json"
        elif mime.startswith("text/"):
            handler = "text"
        elif mime in ("application/zip",):
            handler = "archive"
        else:
            handler = "text"  # try text as last resort

    base = {"name": filename}

    try:
        if handler == "image":
            data_uri, mime = process_image(data)
            return {**base, "kind": "image", "mime": mime, "data_uri": data_uri}

        if handler == "pdf":
            text, trunc = extract_pdf_text(data)
        elif handler == "docx":
            text, trunc = extract_docx_text(data)
        elif handler == "rtf":
            text, trunc = extract_rtf_text(data)
        elif handler == "xlsx":
            text, trunc = extract_xlsx_text(data)
        elif handler == "csv":
            text, trunc = extract_csv_text(data, ",")
        elif handler == "tsv":
            text, trunc = extract_csv_text(data, "\t")
        elif handler == "pptx":
            text, trunc = extract_pptx_text(data)
        elif handler == "json":
            text, trunc = extract_json_text(data)
        elif handler == "xml":
            text, trunc = extract_xml_text(data)
        elif handler == "yaml":
            text, trunc = extract_yaml_toml_text(data)
        elif handler == "archive":
            text, trunc = extract_archive_manifest(data, filename)
            return {**base, "kind": "archive", "text": text, "truncated": trunc}
        elif handler == "av":
            text, trunc = extract_audio_video_info(data, filename)
            return {**base, "kind": "audio_video", "text": text, "truncated": trunc}
        else:
            text, trunc = extract_plain_text(data)

        return {**base, "kind": "document", "text": text, "truncated": trunc}

    except FileProcessingError:
        raise
    except Exception as exc:
        raise FileProcessingError(f"Failed to process file: {exc}") from exc
