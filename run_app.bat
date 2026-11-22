@echo off
cd /d C:\Users\HP\OneDrive\Desktop\AI_Business_Doctor

start "Backend" cmd /k "call C:\venvs\business_doctor\Scripts\activate && python -m uvicorn backend.main:app --port 8000"

timeout /t 5 >nul

start "Frontend" cmd /k "call C:\venvs\business_doctor\Scripts\activate && python -m streamlit run frontend/app.py"