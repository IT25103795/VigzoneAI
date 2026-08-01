"""Production entry point for Vigzone AI."""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    workers = int(os.getenv("WORKERS", "1"))
    if workers != 1:
        raise SystemExit(
            "Vigzone currently requires WORKERS=1 because SQLite and stream controls "
            "are process-local. Use a single replica with persistent storage."
        )

    trusted_proxies = os.getenv("TRUSTED_PROXY_IPS", "").strip()
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        workers=1,
        proxy_headers=bool(trusted_proxies),
        forwarded_allow_ips=trusted_proxies or "127.0.0.1",
        timeout_keep_alive=30,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
