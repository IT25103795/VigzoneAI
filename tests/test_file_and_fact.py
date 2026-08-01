"""Truthfulness and safety checks for files, images, and factual evidence."""

from __future__ import annotations

import asyncio
import base64
import io
import zipfile

import pytest
from PIL import Image
from pypdf import PdfWriter


def _zip_bytes(names: list[str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(name, "safe test content")
    return output.getvalue()


def test_unknown_binary_is_rejected_and_archives_are_manifest_only():
    import file_processing

    with pytest.raises(file_processing.FileProcessingError, match="binary file type"):
        file_processing.process_file(b"\x00\xff\x01\x02binary", "unknown.bin")

    result = file_processing.process_file(_zip_bytes(["notes.txt", "folder/data.csv"]), "bundle.zip")
    assert result["kind"] == "archive"
    assert result["capability"] == "manifest_only"
    assert result["analysis_limited"] is True
    assert "contents were not opened or analyzed" in result["text"]


def test_office_container_entry_limit_is_enforced(monkeypatch):
    import file_processing

    monkeypatch.setattr(file_processing, "MAX_OFFICE_ENTRIES", 2)
    malicious = _zip_bytes(["[Content_Types].xml", "word/document.xml", "word/styles.xml"])
    with pytest.raises(file_processing.FileProcessingError, match="too many internal files"):
        file_processing.process_file(malicious, "oversized.docx")


def test_blank_pdf_is_accepted_with_truthful_limitation(monkeypatch):
    import file_processing

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    monkeypatch.setattr(file_processing, "_HAS_PDF_OCR", False)

    result = file_processing.process_file(output.getvalue(), "blank.pdf")
    assert result["kind"] == "document"
    assert result["analysis_limited"] is True
    assert "cannot truthfully analyze" in result["text"]


def test_source_image_validation_checks_real_format():
    import image_generation

    with pytest.raises(image_generation.ImageGenError):
        image_generation._decode_data_uri("not-a-data-uri")
    with pytest.raises(image_generation.ImageGenError):
        image_generation._decode_data_uri("data:image/png;base64,not-valid-base64")

    output = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(output, format="PNG")
    uri = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    decoded, detected_mime = image_generation._decode_data_uri(uri)
    assert decoded == output.getvalue()
    assert detected_mime == "image/png"


def test_generated_images_are_decoded_and_remote_urls_must_be_https():
    import image_generation

    with pytest.raises(image_generation.ImageGenError, match="invalid image data"):
        image_generation._validated_generated_image_data_uri(b"<html>not an image</html>")

    output = io.BytesIO()
    Image.new("RGB", (3, 2), (0, 120, 255)).save(output, format="PNG")
    data_uri, mime = image_generation._validated_generated_image_data_uri(output.getvalue())
    assert mime == "image/png"
    assert data_uri.startswith("data:image/png;base64,")

    with pytest.raises(image_generation.ImageGenError, match="unsafe image URL"):
        image_generation._extract_openai_image(
            {"data": [{"url": "javascript:alert(1)"}]},
            provider="openai",
        )


def test_fact_verification_never_invents_a_verdict(monkeypatch):
    import fact_verification

    async def no_evidence(_claim, max_results=6):
        return []

    monkeypatch.setattr(fact_verification, "search_evidence", no_evidence)
    unavailable = asyncio.run(fact_verification.verify_factual_claim("A test claim"))
    unavailable_payload = unavailable.to_dict()
    assert unavailable_payload["verified"] is None
    assert unavailable_payload["confidence"] is None
    assert unavailable_payload["status"] == "evidence_unavailable"

    async def evidence(_claim, max_results=6):
        return [{"title": "Primary source", "url": "https://example.com", "snippet": "Lead"}]

    monkeypatch.setattr(fact_verification, "search_evidence", evidence)
    found = asyncio.run(fact_verification.verify_factual_claim("Another claim")).to_dict()
    assert found["status"] == "evidence_found"
    assert found["verified"] is None
    assert found["confidence"] is None
