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

    if os.getenv('GROQ_API_KEY'):
        print("✓ GROQ_API_KEY is set (Groq chat can be configured).")
    else:
        print("⚠ GROQ_API_KEY is not set. Add it before production deploy.")

    if os.getenv('ENCRYPTION_SECRET'):
        print("✓ ENCRYPTION_SECRET is set (user Groq keys can be encrypted).")
    else:
        print("⚠ ENCRYPTION_SECRET is not set. Saved user keys may not survive restarts.")

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
