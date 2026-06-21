from vigzone_ai import _build_payload, DEFAULT_MODEL
from self_learning import _ensure_kb, add_interaction

_ensure_kb()
add_interaction("How do I center a div in CSS?", "Use margin: 0 auto; on a block with width or flexbox centering.")

messages = [{"role": "user", "content": "How can I center something horizontally in CSS?"}]
payload = _build_payload(messages, DEFAULT_MODEL, stream=False)
import json
print(json.dumps(payload, indent=2, ensure_ascii=False))

