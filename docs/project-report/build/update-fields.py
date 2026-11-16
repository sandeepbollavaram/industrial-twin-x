"""Open the generated DOCX in Microsoft Word, update every field, save, and export the PDF.

Usage: python update-fields.py   (Windows with Microsoft Word; needs pywin32)
Word computes the table of contents, the lists of figures and tables, and page numbers.
It works on a temporary copy: after a forced stop, Word can silently block reopening the
original file path behind a hidden recovery prompt.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "Industrial_Twin_X_Final_Report.docx"
PDF = ROOT / "Industrial_Twin_X_Final_Report.pdf"
WD_EXPORT_PDF = 17
WD_STAT_PAGES = 2


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="twinx-report-"))
    copy = work / "report.docx"
    shutil.copyfile(DOCX, copy)
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    word.Options.CheckGrammarAsYouType = False
    word.Options.CheckSpellingAsYouType = False
    try:
        doc = word.Documents.Open(str(copy), ReadOnly=False, AddToRecentFiles=False, ConfirmConversions=False)
        for toc in doc.TablesOfContents:
            toc.Update()
        doc.Fields.Update()
        doc.Repaginate()
        # Page numbers shift once the lists are filled in, so refresh them again.
        for toc in doc.TablesOfContents:
            toc.UpdatePageNumbers()
        pages = doc.ComputeStatistics(WD_STAT_PAGES)
        doc.Save()
        doc.ExportAsFixedFormat(str(work / "report.pdf"), WD_EXPORT_PDF, OpenAfterExport=False, OptimizeFor=0, CreateBookmarks=1)
        doc.Close(SaveChanges=False)
    finally:
        word.Quit()
    shutil.copyfile(copy, DOCX)
    shutil.copyfile(work / "report.pdf", PDF)
    shutil.rmtree(work, ignore_errors=True)
    print(f"pages={pages}")


if __name__ == "__main__":
    sys.exit(main())
