#!/bin/bash
# Vigzone AI - Quick Start Script for Linux/Mac

set -e

echo "🚀 Vigzone AI - Setup & Launch Script"
echo "======================================"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found! Please install Python 3.10+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

if [ ! -d "venv" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

echo -e "${BLUE}Installing dependencies...${NC}"
pip install --upgrade pip setuptools wheel > /dev/null
pip install -r requirements.txt > /dev/null
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo -e "${BLUE}Checking configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ No .env file found. Creating one from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠ Add your free Groq API key to .env before chatting: https://console.groq.com/keys${NC}"
elif ! grep -q "^GROQ_API_KEY=.\+" .env || grep -q "^GROQ_API_KEY=your_groq_api_key_here" .env; then
    echo -e "${YELLOW}⚠ GROQ_API_KEY is missing in .env. Get a free key at https://console.groq.com/keys${NC}"
else
    echo -e "${GREEN}✓ API key configured${NC}"
fi

echo -e "${YELLOW}"
echo "======================================"
echo "🎉 Setup complete! Starting server..."
echo "======================================"
echo -e "${NC}"

echo -e "${GREEN}Server will be available at:${NC}"
echo -e "  🌐 Web UI: ${BLUE}http://localhost:8000${NC}"
echo -e "  📚 API Docs: ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

python app.py
