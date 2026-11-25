@echo off
cd /d %~dp0backend
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env ( copy .env.example .env & echo Edit backend\.env with your MySQL password, then run this again. & pause & exit /b )
python init_db.py
uvicorn app.main:app --reload --port 8000
