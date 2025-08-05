@echo off
echo Launching Protocol Tracker App...
cd /d %~dp0
streamlit run app.py
pause
