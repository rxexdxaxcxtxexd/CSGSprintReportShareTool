@echo off
echo ============================================================
echo CSG Sprint Reporter - Generate Report
echo ============================================================
echo.

cd /d "%~dp0"

set /p SPRINT_NUM="Enter sprint number (e.g., 13): "

if "%SPRINT_NUM%"=="" (
    echo [ERROR] Sprint number is required
    pause
    exit /b 1
)

echo.
echo Generating report for Sprint %SPRINT_NUM%...
echo This will take 1-2 minutes.
echo.

python csg-sprint-reporter.py --ai --quick --sprint %SPRINT_NUM%

echo.
echo ============================================================
echo DONE!
echo ============================================================
echo.
echo Your Word report has been saved to:
echo OneDrive - Cornerstone Solutions Group\Desktop\Files in use\Michael SRT\
echo Look for: CSG-Sprint-%SPRINT_NUM%-Report.docx
echo.
echo (Markdown version also saved to Downloads if needed)
echo.
pause
