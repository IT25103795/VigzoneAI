import asyncio
import json

from vigzone_ai import _build_payload, DEFAULT_MODEL

async def main():
    payload = await _build_payload([{"role": "user", "content": "How can I center something horizontally in CSS?"}], DEFAULT_MODEL, stream=False)
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
