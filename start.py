"""
Vigzone AI - Production Launcher
==================================
Reads the PORT environment variable directly in Python and starts uvicorn
with it. This sidesteps shell-substitution issues (e.g. "$PORT" being
passed through literally instead of expanded) that can happen depending on
exactly how a host (Railway, Render, Fly.io, Docker, etc.) invokes the
container's start command.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
