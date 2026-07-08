"""
High-quality image generation helper module for Vigzone AI.

Providers:
- openai: best quality when OPENAI_API_KEY is set. Defaults to GPT Image and
  uses high quality PNG output.
- pollinations: free/keyless fallback. Uses prompt enhancement and better
  Pollinations parameters, but quality is naturally lower than OpenAI.

Important env vars:
  IMAGE_API_PROVIDER=auto|openai|pollinations
  OPENAI_API_KEY=...
  OPENAI_IMAGE_MODEL=gpt-image-1
  OPENAI_IMAGE_QUALITY=high
  OPENAI_IMAGE_OUTPUT_FORMAT=png
  IMAGE_PROMPT_ENHANCER=auto|groq|off
  IMAGE_PROMPT_ENHANCER_MODEL=llama-3.1-8b-instant
"""
from __future__ import annotations

import base64
import os
import random
import re
import urllib.parse
from typing import Dict, Optional

import httpx


class ImageGenError(Exception):
    pass


# ==========================================
# Shared config/helpers
# ==========================================
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
_DEFAULT_DIMENSION = 1024
_VALID_OPENAI_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}
_VALID_QUALITIES = {"low", "medium", "high", "auto"}
_VALID_OUTPUT_FORMATS = {"png", "webp", "jpeg"}
_VALID_BACKGROUNDS = {"transparent", "opaque", "auto"}


def _safe_env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _normalize_openai_size(size: Optional[str]) -> str:
    raw = (size or "1024x1024").strip().lower()
    if raw in _VALID_OPENAI_SIZES:
        return raw
    if raw in {"square", "1:1"}:
        return "1024x1024"
    if raw in {"portrait", "vertical", "2:3", "9:16"}:
        return "1024x1536"
    if raw in {"landscape", "horizontal", "3:2", "16:9"}:
        return "1536x1024"
    return "1024x1024"


def _parse_size(size: str) -> tuple[int, int]:
    raw = (size or "").lower().strip()
    aliases = {
        "square": "1024x1024",
        "portrait": "1024x1536",
        "vertical": "1024x1536",
        "landscape": "1536x1024",
        "horizontal": "1536x1024",
        "auto": "1024x1024",
    }
    raw = aliases.get(raw, raw)
    try:
        w_str, h_str = raw.split("x", 1)
        w, h = int(w_str), int(h_str)
        if w > 0 and h > 0:
            # Keep the free provider sane and fast.
            return min(max(w, 512), 1536), min(max(h, 512), 1536)
    except (ValueError, AttributeError):
        pass
    return _DEFAULT_DIMENSION, _DEFAULT_DIMENSION


def _has_openai_key() -> bool:
    return bool(_safe_env("OPENAI_API_KEY"))


def _select_provider() -> str:
    provider = (_safe_env("IMAGE_API_PROVIDER", "auto") or "auto").lower()
    if provider in {"auto", "best", "quality"}:
        return "openai" if _has_openai_key() else "pollinations"
    if provider in {"openai", "pollinations"}:
        return provider
    raise ImageGenError(
        f'Unknown IMAGE_API_PROVIDER "{provider}". Use auto, openai, or pollinations.'
    )


def _clean_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", (prompt or "").strip())


def _detect_intent_tags(prompt: str) -> dict:
    p = prompt.lower()
    return {
        "has_text": bool(re.search(r"\b(text|word|letter|label|logo|title|slogan|caption|write|spell|font)\b", p)),
        "has_person": bool(re.search(r"\b(person|people|man|woman|boy|girl|face|portrait|selfie|hands|fingers|eyes)\b", p)),
        "product": bool(re.search(r"\b(product|packaging|label|poster|flyer|banner|ad|advertisement|mockup)\b", p)),
        "photo": bool(re.search(r"\b(photo|photorealistic|realistic|camera|dslr|portrait)\b", p)),
        "logo": bool(re.search(r"\b(logo|icon|brand mark|mascot)\b", p)),
        "ui": bool(re.search(r"\b(ui|website|app screen|dashboard|interface|landing page)\b", p)),
    }


def _rule_based_prompt(prompt: str, *, edit: bool = False) -> str:
    """Create a high-control image prompt without drifting from the user request."""
    cleaned = _clean_prompt(prompt)
    if not cleaned:
        raise ImageGenError("A prompt is required to generate an image.")

    tags = _detect_intent_tags(cleaned)
    lines: list[str] = [
        "Create a highly accurate, high-quality image based strictly on this request:",
        cleaned,
        "",
        "Quality requirements:",
        "- Follow every visible detail in the user's request exactly.",
        "- Strong composition, clear subject, correct proportions, crisp edges, high resolution.",
        "- Natural lighting, balanced contrast, no muddy colors, no random artifacts.",
        "- Do not add unrelated objects, people, logos, labels, watermarks, signatures, or extra text.",
    ]

    if tags["has_text"]:
        lines.extend([
            "- If any text is requested, spell it exactly as written by the user.",
            "- Keep text clean, readable, centered/aligned correctly, and do not invent extra words.",
        ])
    else:
        lines.append("- Avoid text in the image unless the user explicitly asked for text.")

    if tags["has_person"]:
        lines.extend([
            "- Human anatomy must be realistic: correct face, eyes, hands, fingers, limbs, and skin texture.",
            "- Avoid distorted faces, extra fingers, missing fingers, or asymmetrical eyes.",
        ])

    if tags["product"]:
        lines.extend([
            "- Product/label/poster layout must be clean, professional, print-ready, and not cluttered.",
            "- Keep margins, spacing, and hierarchy neat.",
        ])

    if tags["logo"]:
        lines.extend([
            "- Logo/icon should be simple, memorable, scalable, symmetrical, and vector-like.",
            "- No tiny unreadable details.",
        ])

    if tags["ui"]:
        lines.extend([
            "- UI must look modern, polished, consistent, and realistic.",
            "- Use clear spacing, clean cards, legible typography, and professional visual hierarchy.",
        ])

    if edit:
        lines.extend([
            "",
            "Editing requirements:",
            "- Preserve the original image identity, layout, camera angle, and important details.",
            "- Only change what the user explicitly requested.",
        ])

    lines.extend([
        "",
        "Negative constraints:",
        "low quality, blurry, distorted, deformed anatomy, extra fingers, bad hands, bad eyes, watermark, signature, wrong text, misspelled text, random logo, messy layout, duplicated objects, cropped subject, out of frame",
    ])
    return "\n".join(lines)


async def _groq_enhance_prompt(prompt: str, *, edit: bool = False) -> str:
    """Optional prompt engineer using Groq. Falls back silently to rules if unavailable."""
    enhancer_mode = (_safe_env("IMAGE_PROMPT_ENHANCER", "auto") or "auto").lower()
    if enhancer_mode in {"off", "false", "0", "none"}:
        return _rule_based_prompt(prompt, edit=edit)

    groq_key = _safe_env("GROQ_API_KEY")
    if not groq_key:
        return _rule_based_prompt(prompt, edit=edit)

    model = _safe_env("IMAGE_PROMPT_ENHANCER_MODEL", "llama-3.1-8b-instant")
    url = "https://api.groq.com/openai/v1/chat/completions"
    system = (
        "You are an expert image prompt engineer for a production AI image generator. "
        "Rewrite the user's request into one precise, image-model-ready prompt. "
        "Never add new subject matter. Preserve exact requested text, names, brand words, "
        "colors, counts, and layout instructions. Include quality, composition, lighting, "
        "accuracy, and negative constraints. Return only the final prompt, no markdown."
    )
    user = (
        "Rewrite this for accurate image generation"
        + (" / image editing" if edit else "")
        + ":\n"
        + _clean_prompt(prompt)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.25,
        "max_tokens": 900,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code != 200:
            return _rule_based_prompt(prompt, edit=edit)
        data = resp.json()
        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        # Guard against empty or wildly short rewrite.
        if len(text) < max(80, len(prompt) // 2):
            return _rule_based_prompt(prompt, edit=edit)
        return text[:3500]
    except Exception:
        return _rule_based_prompt(prompt, edit=edit)


# ==========================================
# Pollinations provider (free fallback)
# ==========================================
async def _pollinations_generate(prompt: str, size: str = "1024x1024") -> Dict:
    width, height = _parse_size(size)
    effective_prompt = await _groq_enhance_prompt(prompt)
    encoded_prompt = urllib.parse.quote(effective_prompt[:1800])
    seed = random.randint(0, 2_000_000_000)
    url = POLLINATIONS_URL.format(prompt=encoded_prompt)

    params = {
        "width": width,
        "height": height,
        "seed": seed,
        "nologo": "true",
        "private": "true",
        "safe": "true",
        # Flux usually gives much better coherence than older defaults when available.
        "model": _safe_env("POLLINATIONS_MODEL", "flux"),
        "enhance": _safe_env("POLLINATIONS_ENHANCE", "true"),
    }

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError as e:
            raise ImageGenError(f"Could not reach the image generation service: {e}") from e

    if resp.status_code != 200:
        raise ImageGenError(
            f"Image generation service error {resp.status_code}: {resp.text[:300]}"
        )

    content_type = resp.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        raise ImageGenError("Image generation service returned an unexpected response.")

    encoded = base64.b64encode(resp.content).decode("ascii")
    return {
        "data_uri": f"data:{content_type};base64,{encoded}",
        "provider": "pollinations",
        "quality_note": "Free fallback provider. For best accuracy, set IMAGE_API_PROVIDER=openai and OPENAI_API_KEY.",
    }


# ==========================================
# OpenAI provider (best quality)
# ==========================================
def _require_openai_key() -> str:
    key = _safe_env("OPENAI_API_KEY")
    if not key:
        raise ImageGenError("OPENAI_API_KEY is not set. Set it to enable high-quality OpenAI image generation.")
    return key


def _openai_image_payload(prompt: str, size: str, *, edit: bool = False) -> dict:
    model = _safe_env("OPENAI_IMAGE_MODEL", "gpt-image-1")
    quality = (_safe_env("OPENAI_IMAGE_QUALITY", "high") or "high").lower()
    output_format = (_safe_env("OPENAI_IMAGE_OUTPUT_FORMAT", "png") or "png").lower()
    background = (_safe_env("OPENAI_IMAGE_BACKGROUND", "auto") or "auto").lower()

    if quality not in _VALID_QUALITIES:
        quality = "high"
    if output_format not in _VALID_OUTPUT_FORMATS:
        output_format = "png"
    if background not in _VALID_BACKGROUNDS:
        background = "auto"

    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": _normalize_openai_size(size),
        "quality": quality,
        "output_format": output_format,
    }
    if not edit:
        payload["background"] = background
    return payload


async def _post_openai_image(url: str, headers: dict, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as e:
            raise ImageGenError(f"Could not reach OpenAI Images API: {e}") from e

    if resp.status_code == 200:
        return resp.json()

    # Some accounts/models may reject newer optional params. Retry minimal but keep model/prompt/size.
    if resp.status_code in (400, 422):
        minimal = {
            "model": payload.get("model", "gpt-image-1"),
            "prompt": payload["prompt"],
            "n": 1,
            "size": payload.get("size", "1024x1024"),
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            retry = await client.post(url, headers=headers, json=minimal)
        if retry.status_code == 200:
            return retry.json()
        raise ImageGenError(f"Images API error {retry.status_code}: {retry.text[:500]}")

    raise ImageGenError(f"Images API error {resp.status_code}: {resp.text[:500]}")


async def _openai_generate(prompt: str, size: str = "1024x1024") -> Dict:
    api_key = _require_openai_key()
    enhanced_prompt = await _groq_enhance_prompt(prompt)
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = _openai_image_payload(enhanced_prompt, size)

    data = await _post_openai_image(url, headers, payload)
    return _extract_openai_image(data, provider="openai", model=payload.get("model"))


def _extract_openai_image(data: dict, *, provider: str, model: Optional[str] = None) -> Dict:
    imgs = data.get("data", [])
    if not imgs:
        raise ImageGenError("Images API returned no images")
    first = imgs[0]
    b64 = first.get("b64_json")
    if b64:
        try:
            base64.b64decode(b64)
            return {
                "data_uri": "data:image/png;base64," + b64,
                "provider": provider,
                "model": model,
            }
        except Exception:
            raise ImageGenError("Images API returned invalid base64 data")
    url_out = first.get("url")
    if url_out:
        return {"url": url_out, "provider": provider, "model": model}
    raise ImageGenError("Images API returned an unexpected response format")


def _decode_data_uri(data_uri: str) -> tuple[bytes, str]:
    if not data_uri.startswith("data:"):
        raise ImageGenError("Expected a base64 data URI for the source image.")
    try:
        header, b64data = data_uri.split(",", 1)
        mime = header.split(";")[0][len("data:"):] or "image/png"
        return base64.b64decode(b64data), mime
    except (ValueError, IndexError) as e:
        raise ImageGenError("Couldn't read the uploaded image data.") from e


async def _openai_edit(
    image_bytes: bytes,
    image_mime: str,
    prompt: str,
    size: str = "1024x1024",
) -> Dict:
    api_key = _require_openai_key()
    enhanced_prompt = await _groq_enhance_prompt(prompt, edit=True)
    url = "https://api.openai.com/v1/images/edits"
    headers = {"Authorization": f"Bearer {api_key}"}

    ext = "png" if "png" in image_mime else ("webp" if "webp" in image_mime else "jpg")
    files = {"image": (f"source.{ext}", image_bytes, image_mime or "image/png")}

    model = _safe_env("OPENAI_IMAGE_MODEL", "gpt-image-1")
    quality = (_safe_env("OPENAI_IMAGE_QUALITY", "high") or "high").lower()
    output_format = (_safe_env("OPENAI_IMAGE_OUTPUT_FORMAT", "png") or "png").lower()
    if quality not in _VALID_QUALITIES:
        quality = "high"
    if output_format not in _VALID_OUTPUT_FORMATS:
        output_format = "png"

    data = {
        "prompt": enhanced_prompt,
        "model": model,
        "n": "1",
        "size": _normalize_openai_size(size),
        "quality": quality,
        "output_format": output_format,
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(url, headers=headers, files=files, data=data)
        except httpx.RequestError as e:
            raise ImageGenError(f"Could not reach OpenAI Images API: {e}") from e

    if resp.status_code != 200:
        # Retry minimal if quality/output_format rejected.
        minimal = {"prompt": enhanced_prompt, "model": model, "n": "1", "size": _normalize_openai_size(size)}
        async with httpx.AsyncClient(timeout=180.0) as client:
            retry = await client.post(url, headers=headers, files=files, data=minimal)
        if retry.status_code != 200:
            raise ImageGenError(f"Image edit API error {retry.status_code}: {retry.text[:500]}")
        result = retry.json()
    else:
        result = resp.json()

    return _extract_openai_image(result, provider="openai-edit", model=model)


# ==========================================
# Public entrypoints
# ==========================================
async def generate_image(prompt: str, size: str = "1024x1024") -> Dict:
    if not prompt or not prompt.strip():
        raise ImageGenError("A prompt is required to generate an image.")

    provider = _select_provider()
    if provider == "openai":
        return await _openai_generate(prompt, size=size)
    if provider == "pollinations":
        return await _pollinations_generate(prompt, size=size)

    raise ImageGenError(f'Unsupported image provider "{provider}".')


async def edit_image(image_data_uri: str, prompt: str, size: str = "1024x1024") -> Dict:
    if not prompt or not prompt.strip():
        raise ImageGenError("Describe the change you want made to the photo.")
    if not image_data_uri:
        raise ImageGenError("No source photo was provided to edit.")

    if not _has_openai_key():
        raise ImageGenError(
            "Photo editing needs an OpenAI API key. Set OPENAI_API_KEY and IMAGE_API_PROVIDER=openai "
            "to enable accurate image editing."
        )

    image_bytes, image_mime = _decode_data_uri(image_data_uri)
    return await _openai_edit(image_bytes, image_mime, prompt.strip(), size=size)
