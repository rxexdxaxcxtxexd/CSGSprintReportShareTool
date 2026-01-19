#!/bin/bash
echo "============================================================"
echo "CSG Sprint Reporter - Interactive Menu"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

python3 csg-sprint-reporter.py --ai

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
