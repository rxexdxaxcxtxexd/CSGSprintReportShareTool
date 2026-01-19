@echo off
echo ============================================================
echo CSG Sprint Reporter - Interactive Menu
echo ============================================================
echo.

cd /d "%~dp0"

python csg-sprint-reporter.py --ai

echo.
echo ============================================================
echo DONE!
echo ============================================================
echo.
echo Your report has been saved to your Downloads folder:
echo %USERPROFILE%\Downloads\
echo Look for: CSG-Sprint-[NUMBER]-Report.docx
echo.
pause
