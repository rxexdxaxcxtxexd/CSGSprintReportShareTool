#!/bin/bash
echo "============================================================"
echo "CSG Sprint Reporter - Generate Report"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

read -p "Enter sprint number (e.g., 13): " SPRINT_NUM

if [ -z "$SPRINT_NUM" ]; then
    echo "[ERROR] Sprint number is required"
    exit 1
fi

echo ""
echo "Generating report for Sprint $SPRINT_NUM..."
echo "This will take 1-2 minutes."
echo ""

python3 csg-sprint-reporter.py --ai --quick --sprint "$SPRINT_NUM"

echo ""
echo "============================================================"
echo "DONE!"
echo "============================================================"
echo ""
echo "Your Word report has been saved to:"
echo "OneDrive - Cornerstone Solutions Group/Desktop/Files in use/Michael SRT/"
echo "Look for: CSG-Sprint-$SPRINT_NUM-Report.docx"
echo ""
echo "(Markdown version also saved to Downloads if needed)"
echo ""
read -p "Press Enter to continue..."
