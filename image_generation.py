"""
Image generation helper module.

Provides a small pluggable wrapper to generate images from text prompts.
Two providers are supported out of the box:

- "pollinations" (default, no API key required): calls the free Pollinations
  AI image endpoint (https://image.pollinations.ai) and returns the image
  bytes as a base64 data URI. This is what powers image generation
  out-of-the-box with no configuration.
- "openai": calls OpenAI's Images API (requires OPENAI_API_KEY). Better
  quality/control, but needs a paid OpenAI key.

Select the provider with the IMAGE_API_PROVIDER env var. If unset, the app
defaults to "pollinations" so image generation works with zero setup.

The function `generate_image` returns a dict with either a `data_uri` key
containing a base64-encoded image, or a `url` key with a hosted image URL,
depending on the provider's response.
"""
from __future__ import annotations

import base64
import os
import random
import urllib.parse
from typing import Dict

import httpx


class ImageGenError(Exception):
    pass


# ==========================================
# Pollinations provider (default, no API key)
# ==========================================
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

# Pollinations expects width/height query params; fall back to a square
# image for anything we can't parse out of a "WIDTHxHEIGHT" size string.
_DEFAULT_DIMENSION = 1024


def _parse_size(size: str) -> tuple[int, int]:
    try:
        w_str, h_str = size.lower().split("x")
        w, h = int(w_str), int(h_str)
        if w > 0 and h > 0:
            return w, h
    except (ValueError, AttributeError):
        pass
    return _DEFAULT_DIMENSION, _DEFAULT_DIMENSION


def _enrich_prompt(prompt: str) -> str:
    """Turn a short/vague prompt into a more deliberate one.

    Pollinations (and most diffusion-style generators) produce much more
    reliable, on-topic results when the prompt spells out subject, setting,
    and rendering style rather than a bare word or two. We don't invent new
    subject matter — we only add neutral, generic qualifiers when the
    prompt looks underspecified, so the output stays anchored to what the
    user actually typed instead of drifting into something unrelated.
    """
    cleaned = prompt.strip()
    word_count = len(cleaned.split())
    if word_count >= 6:
        # Already descriptive enough; leave it alone.
        return cleaned
    # Short prompt: append generic, non-content-changing qualifiers that
    # push the model toward a coherent, well-composed image of the exact
    # subject named, rather than a random loose association.
    return (
        f"{cleaned}, clear single coherent subject, well-lit, in-focus, "
        f"detailed, high quality photo"
    )


async def _pollinations_generate(prompt: str, size: str = "1024x1024") -> Dict:
    """Generate an image via Pollinations' free, keyless image endpoint.

    Pollinations serves the image directly as bytes at a URL built from the
    prompt, so we fetch it server-side and return it as a base64 data URI
    (keeping the API response shape consistent across providers, and
    avoiding exposing a third-party URL straight to the client).
    """
    width, height = _parse_size(size)
    effective_prompt = _enrich_prompt(prompt)
    encoded_prompt = urllib.parse.quote(effective_prompt[:800])
    # A random seed keeps repeated identical prompts from being cached to
    # the exact same image every time.
    seed = random.randint(0, 2_000_000_000)
    url = POLLINATIONS_URL.format(prompt=encoded_prompt)
    params = {
        "width": width,
        "height": height,
        "seed": seed,
        "nologo": "true",
    }

    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
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
    return {"data_uri": f"data:{content_type};base64,{encoded}"}


# ==========================================
# OpenAI provider (optional, needs OPENAI_API_KEY)
# ==========================================
def _require_openai_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ImageGenError("OPENAI_API_KEY is not set. Set it to enable OpenAI image generation.")
    return key


async def _openai_generate(prompt: str, size: str = "1024x1024") -> Dict:
    """Call OpenAI Images API (image generation) and return a result.

    This implementation expects the compatibility endpoint at
    https://api.openai.com/v1/images/generations and returns the first image
    as a data URI (base64 PNG) when available.
    """
    api_key = _require_openai_key()
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt, "n": 1, "size": size}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as e:
            raise ImageGenError(f"Could not reach OpenAI Images API: {e}") from e

    if resp.status_code != 200:
        raise ImageGenError(f"Images API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    # OpenAI can return base64 data in data[0].b64_json or a URL in data[0].url
    imgs = data.get("data", [])
    if not imgs:
        raise ImageGenError("Images API returned no images")
    first = imgs[0]
    b64 = first.get("b64_json")
    if b64:
        try:
            # ensure it's valid base64
            base64.b64decode(b64)
            data_uri = "data:image/png;base64," + b64
            return {"data_uri": data_uri}
        except Exception:
            raise ImageGenError("Images API returned invalid base64 data")

    url_out = first.get("url")
    if url_out:
        return {"url": url_out}

    raise ImageGenError("Images API returned an unexpected response format")


def _decode_data_uri(data_uri: str) -> tuple[bytes, str]:
    """Decode a `data:<mime>;base64,<...>` URI into (bytes, mime_type)."""
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
    """Call OpenAI's images/edits endpoint to modify an existing photo.

    This is the only provider that can actually take a user's uploaded
    photo as input and apply a described change to it — Pollinations is
    text-to-image only and has no concept of an input image.
    """
    api_key = _require_openai_key()
    url = "https://api.openai.com/v1/images/edits"
    headers = {"Authorization": f"Bearer {api_key}"}

    ext = "png" if "png" in image_mime else ("webp" if "webp" in image_mime else "jpg")
    files = {
        "image": (f"source.{ext}", image_bytes, image_mime or "image/png"),
    }
    data = {
        "prompt": prompt,
        "model": "gpt-image-1",
        "n": "1",
        "size": size,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(url, headers=headers, files=files, data=data)
        except httpx.RequestError as e:
            raise ImageGenError(f"Could not reach OpenAI Images API: {e}") from e

    if resp.status_code != 200:
        raise ImageGenError(f"Image edit API error {resp.status_code}: {resp.text[:300]}")

    result = resp.json()
    imgs = result.get("data", [])
    if not imgs:
        raise ImageGenError("Image edit API returned no images")
    first = imgs[0]
    b64 = first.get("b64_json")
    if b64:
        try:
            base64.b64decode(b64)
            return {"data_uri": "data:image/png;base64," + b64}
        except Exception:
            raise ImageGenError("Image edit API returned invalid base64 data")
    url_out = first.get("url")
    if url_out:
        return {"url": url_out}
    raise ImageGenError("Image edit API returned an unexpected response format")


# ==========================================
# Public entrypoint
# ==========================================
async def generate_image(prompt: str, size: str = "1024x1024") -> Dict:
    """Public generator entrypoint.

    Selects backend according to the IMAGE_API_PROVIDER environment
    variable. Supported values: "pollinations" (default, no key needed),
    "openai" (needs OPENAI_API_KEY).
    """
    if not prompt or not prompt.strip():
        raise ImageGenError("A prompt is required to generate an image.")

    provider = (os.getenv("IMAGE_API_PROVIDER") or "pollinations").lower()
    if provider == "openai":
        return await _openai_generate(prompt, size=size)
    if provider == "pollinations":
        return await _pollinations_generate(prompt, size=size)
    raise ImageGenError(
        f"Unknown IMAGE_API_PROVIDER \"{provider}\". Supported values: pollinations, openai."
    )


async def edit_image(image_data_uri: str, prompt: str, size: str = "1024x1024") -> Dict:
    """Public photo-editing entrypoint.

    Takes an existing photo (as a base64 data URI, e.g. from the /api/upload
    endpoint) plus an instruction describing the desired change, and returns
    an edited version. Always uses OpenAI's images/edits endpoint — there is
    no free/keyless provider capable of editing a specific input photo, so
    this raises a clear, actionable ImageGenError if OPENAI_API_KEY isn't
    configured, rather than silently falling back to plain generation.
    """
    if not prompt or not prompt.strip():
        raise ImageGenError("Describe the change you want made to the photo.")
    if not image_data_uri:
        raise ImageGenError("No source photo was provided to edit.")

    if not os.getenv("OPENAI_API_KEY"):
        raise ImageGenError(
            "Photo editing needs an OpenAI API key. Set OPENAI_API_KEY in your .env file "
            "to enable it (get one at https://platform.openai.com/api-keys)."
        )

    image_bytes, image_mime = _decode_data_uri(image_data_uri)
    return await _openai_edit(image_bytes, image_mime, prompt.strip(), size=size)
