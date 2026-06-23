#!/usr/bin/env python3
"""
Vigzone AI Launcher - Simple startup script for development and production
"""

import os
import sys
import argparse
import subprocess


def setup_environment():
    """Setup environment variables"""
    os.environ.setdefault('ENV', 'development')
    os.environ.setdefault('PORT', '8000')
    os.environ.setdefault('LOG_LEVEL', 'INFO')
    os.environ.setdefault('CORS_ORIGINS', 'http://localhost:8000,http://localhost:3000')


def run_dev_server():
    """Run development server with auto-reload"""
    setup_environment()
    print("🚀 Starting Vigzone AI in DEVELOPMENT mode...")
    print("📍 Server: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")

    subprocess.run([
        sys.executable, '-m', 'uvicorn',
        'app:app',
        '--host', '0.0.0.0',
        '--port', os.getenv('PORT', '8000'),
        '--reload',
    ])


def run_prod_server():
    """Run production server with uvicorn workers"""
    setup_environment()
    os.environ['ENV'] = 'production'

    print("🚀 Starting Vigzone AI in PRODUCTION mode...")
    print("📍 Server: http://0.0.0.0:8000")

    workers = int(os.getenv('WORKERS', '4'))
    subprocess.run([
        sys.executable, '-m', 'uvicorn',
        'app:app',
        '--host', '0.0.0.0',
        '--port', os.getenv('PORT', '8000'),
        '--workers', str(workers),
        '--timeout-keep-alive', '30',
    ])


def check_dependencies():
    """Check if all dependencies are installed"""
    required = ['fastapi', 'uvicorn', 'pydantic', 'httpx', 'dotenv', 'multipart', 'PIL', 'pypdf', 'docx']
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print(f"   Install with: pip install -r requirements.txt")
        return False

    print("✓ All dependencies installed!")

    try:
        import httpx
        base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        resp = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            models = [m.get('name', '?') for m in resp.json().get('models', [])]
            print(f"✓ Ollama is running at {base_url}")
            if models:
                print(f"  Models available: {', '.join(models)}")
            else:
                print("  ⚠ No models pulled yet. Run: ollama pull gemma3")
        else:
            print(f"⚠ Ollama responded with status {resp.status_code} at {base_url}")
    except Exception:
        base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        print(f"⚠ Can't reach Ollama at {base_url}.")
        print("  Install it from https://ollama.com/download and make sure it's running")
        print("  (`ollama serve`), then run: ollama pull gemma3")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Vigzone AI Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launcher.py dev       # Start development server
  python launcher.py prod      # Start production server
  python launcher.py check     # Check dependencies
        """
    )

    parser.add_argument('command', choices=['dev', 'prod', 'check'], help='Command to run')
    parser.add_argument('--port', type=int, default=8000, help='Port to run server on (default: 8000)')
    parser.add_argument('--workers', type=int, default=4, help='Number of production workers (default: 4)')

    args = parser.parse_args()
    os.environ['PORT'] = str(args.port)
    os.environ['WORKERS'] = str(args.workers)

    if args.command == 'check':
        check_dependencies()
    elif args.command == 'dev':
        if check_dependencies():
            run_dev_server()
    elif args.command == 'prod':
        if check_dependencies():
            run_prod_server()


if __name__ == '__main__':
    main()
