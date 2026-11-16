"""List Word's spelling and grammar flags in the report, for manual review.

Usage: python proof.py
"""

import collections
import sys
from pathlib import Path

import win32com.client

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(__file__).resolve().parents[1] / "Industrial_Twin_X_Final_Report.docx"

word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
try:
    doc = word.Documents.Open(str(DOCX), ReadOnly=True, AddToRecentFiles=False)
    doc.Content.LanguageID = 2057  # English (United Kingdom)
    spelling = collections.Counter(e.Text for e in doc.SpellingErrors)
    grammar = [e.Text.strip()[:110] for e in doc.GrammaticalErrors]
    print("spelling flags:", sum(spelling.values()), "unique:", len(spelling))
    for text, n in spelling.most_common():
        print(f"  {n:3d} {text}")
    print("grammar flags:", len(grammar))
    for g in grammar[:60]:
        print("  -", g)
    doc.Close(SaveChanges=False)
finally:
    word.Quit()
