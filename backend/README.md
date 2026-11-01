# Backend Service — Phase 0 Foundation

FastAPI Modular Monolith backend for the AI-Powered Incident Response & RCA Platform.

## Requirements
- Python 3.10+
- PostgreSQL

## Quickstart

```bash
# 1. Activate venv
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate # Linux/macOS

# 2. Install requirements
pip install -r requirements.txt

# 3. Run server
uvicorn app.main:app --reload --port 8000

# 4. Run tests
pytest -v
```
