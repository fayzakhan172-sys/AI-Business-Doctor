@echo off
cd /d C:\Users\HP\OneDrive\Desktop\AI_Business_Doctor
call .venv\Scripts\activate
python -m streamlit run frontend/app.py --server.fileWatcherType none
pause