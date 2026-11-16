# Project Report: Industrial Twin-X

This folder contains the B.Tech third-year IoT mini project report and everything needed to regenerate it.

| Path | Contents |
| --- | --- |
| `Industrial_Twin_X_Final_Report.docx` | Editable report (Word) |
| `Industrial_Twin_X_Final_Report.pdf` | PDF exported from that DOCX by Microsoft Word |
| `chapters/` | Report source text in Markdown, one file per chapter (`00-front.md` holds the preliminary pages) |
| `references.bib` | Verified bibliography (BibTeX) |
| `diagrams/*.mmd`, `diagrams/png/` | Editable Mermaid diagram sources and their rendered images |
| `figures/` | Charts generated from the recorded results, and dashboard screenshots |
| `evidence/` | Evidence inventory, reference verification, traceability, saved test and live-run output |
| `build/` | Scripts that build the report |
| `REPORT_AUDIT.md` | Final audit: what is complete, verified and still missing |

## Before submission

All team, guide, university and date details are filled in. Signatures are added by hand on the printed copy. See `REPORT_AUDIT.md` for the final checks.

## Regenerating the report

Requirements: Windows with Microsoft Word, Node.js, Google Chrome (for diagram rendering), and the project's Python environment.

```powershell
# 1. Build tools (once). Puppeteer uses the installed Chrome, so no browser is downloaded.
cd docs\project-report\build
$env:PUPPETEER_SKIP_DOWNLOAD = "1"; npm install

# 2. References (only if the reference list changes; needs the saved Crossref records)
#    python make_references.py <crossref.json>

# 3. Diagrams, after editing ..\diagrams\*.mmd
node render-diagrams.js

# 4. Charts, from research\reports\experiments\summary.json and research\reports\ai-evaluation\metrics.json
cd ..\..\..
.\.venv\Scripts\python.exe docs\project-report\build\make_figures.py

# 5. DOCX from chapters\*.md
cd docs\project-report\build
node build-docx.js

# 6. Word updates the contents, figure and table lists and page numbers, then exports the PDF.
#    Needs pywin32 in any Python environment: pip install pywin32
python update-fields.py
```

Optional checks:

- `python inspect_pdf.py ..\Industrial_Twin_X_Final_Report.pdf <outdir>` renders contact sheets and lists the page where each chapter starts (needs PyMuPDF).
- `python proof.py` lists Word's spelling and grammar flags.

## Editing conventions

- Write text in `chapters/*.md`, not in the DOCX. Edits made directly in the DOCX are lost on the next build.
- **Citations:** `[@key]` or `[@key1; @key2]`, using keys from `build/references.json`. Numbers are assigned in order of first citation.
- **Cross-references:** `@fig:label`, `@tab:label` and `@eq:label`. Figures and tables are numbered within each chapter, for example Figure 4.3.
- **Tables:** a line `Table: caption {#tab:label}` followed by a pipe table.
- **Figures:** `![caption](figures/file.png){#fig:label}`.
- **Equations:** `$$ text $$ {#eq:label}`.
- Add a reference only after opening and checking the source, and record it in `evidence/reference-verification.md`.
- Keep every result traceable to a file in `research/reports/` or `evidence/`, and keep the label "simulated" on every result.
