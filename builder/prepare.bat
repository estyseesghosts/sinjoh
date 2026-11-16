@echo off
rem Drag your Platinum .nds onto this file. Optionally: prepare.bat --sd E:\
python "%~dp0prepare.py" %*
if errorlevel 1 pause
