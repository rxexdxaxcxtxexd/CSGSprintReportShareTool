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
echo "Your report has been saved to your Downloads folder:"
echo "$HOME/Downloads/"
echo "Look for: CSG-Sprint-[NUMBER]-Report.docx"
echo ""
read -p "Press Enter to continue..."
