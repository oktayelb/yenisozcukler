@echo off

:: 1. Start Playit.gg in a separate window
:: "Playit Tunnel" is just the title of the window
start "Playit Tunnel" "C:\Program Files\playit_gg\bin\playit.exe"

:: 2. Start Django Server in the current window
:: Assuming you are in the project folder with the virtual environment
echo Starting Django Server...
python manage.py runserver

:: Pause so the window doesn't close immediately if Django crashes
pause