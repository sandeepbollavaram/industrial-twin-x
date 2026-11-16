// Builds Industrial_Twin_X_Final_Report.docx from chapters/*.md.
//
// Supported Markdown subset: # / ## / ### headings, paragraphs, "-" and "1." lists,
// pipe tables preceded by "Table: caption {#tab:id}", figures "![caption](path){#fig:id}",
// display equations "$$ text $$ {#eq:id}", fenced code blocks, **bold**, *italic*, `code`,
// citations [@key; @key2], and cross-references @fig:id, @tab:id, @eq:id.
// Word fills the table of contents and lists of figures and tables when update-fields.py runs.

const fs = require("node:fs");
const path = require("node:path");
const docx = require("docx");

const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, LevelFormat,
  NumberFormat, Packer, PageBreak, PageNumber, Paragraph, ShadingType, StyleLevel, TabStopType,
  Table, TableCell, TableOfContents, TableRow, TextRun, VerticalAlign, WidthType,
} = docx;

const ROOT = path.resolve(__dirname, "..");
const CHAPTER_DIR = path.join(ROOT, "chapters");
const OUT = path.join(ROOT, "Industrial_Twin_X_Final_Report.docx");
const REFS = JSON.parse(fs.readFileSync(path.join(__dirname, "references.json"), "utf8"));

const FONT = "Times New Roman";
const MONO = "Consolas";
const TEXT_WIDTH = 9026; // A4 width 11906 minus two 1440 margins, in DXA.
const MAX_W_IN = 6.27;
const MAX_H_IN = 7.4;

// ---------------------------------------------------------------- parsing

function parseFile(file) {
  const lines = fs.readFileSync(file, "utf8").replace(/\r/g, "").split("\n");
  const blocks = [];
  let i = 0;
  let pendingTable = null;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m;
    if ((m = line.match(/^(#{1,3}) (.*)$/))) {
      blocks.push({ type: "heading", level: m[1].length, text: m[2].trim() });
      i++;
    } else if (line.startsWith("```")) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      blocks.push({ type: "code", lines: code });
    } else if ((m = line.match(/^Table: (.*?)\s*\{#(tab:[\w-]+)\}\s*$/))) {
      pendingTable = { caption: m[1], label: m[2] };
      i++;
    } else if (line.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-{3,}:?$/.test(c))) rows.push(cells);
        i++;
      }
      blocks.push({ type: "table", rows, caption: pendingTable?.caption, label: pendingTable?.label });
      pendingTable = null;
    } else if ((m = line.match(/^!\[(.*)\]\((.*?)\)\{#(fig:[\w-]+)\}\s*$/))) {
      blocks.push({ type: "figure", caption: m[1], src: m[2], label: m[3] });
      i++;
    } else if ((m = line.match(/^\$\$ (.*) \$\$\s*\{#(eq:[\w-]+)\}\s*$/))) {
      blocks.push({ type: "equation", text: m[1], label: m[2] });
      i++;
    } else if (/^- /.test(line)) {
      const items = [];
      while (i < lines.length && /^- /.test(lines[i])) items.push(lines[i++].slice(2));
      blocks.push({ type: "bullets", items });
    } else if (/^\d+\. /.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) items.push(lines[i++].replace(/^\d+\. /, ""));
      blocks.push({ type: "numbered", items });
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^(#|```|\||!\[|\$\$|- |\d+\. |Table: )/.test(lines[i])) {
        para.push(lines[i++].trim());
      }
      blocks.push({ type: "para", text: para.join(" ") });
    }
  }
  return blocks;
}

const files = fs.readdirSync(CHAPTER_DIR).filter((f) => f.endsWith(".md")).sort();
const front = parseFile(path.join(CHAPTER_DIR, files[0]));
const chapters = files.slice(1, -1).map((f) => parseFile(path.join(CHAPTER_DIR, f)));
const appendices = parseFile(path.join(CHAPTER_DIR, files[files.length - 1]));

// ---------------------------------------------------------------- numbering

const labels = {};
const figureList = [];
const tableList = [];
const citeOrder = [];

function numberBlocks(blocks, prefixOf) {
  let prefix = null;
  let fig = 0, tab = 0, eq = 0;
  for (const b of blocks) {
    if (b.type === "heading" && b.level === 1) {
      prefix = prefixOf(b);
      fig = tab = eq = 0;
    }
    if (b.type === "figure") { b.number = `${prefix}.${++fig}`; labels[b.label] = `Figure ${b.number}`; figureList.push(b); }
    if (b.type === "table" && b.label) { b.number = `${prefix}.${++tab}`; labels[b.label] = `Table ${b.number}`; tableList.push(b); }
    if (b.type === "equation") { b.number = `${prefix}.${++eq}`; labels[b.label] = `Equation (${b.number})`; }
    const texts = b.type === "para" ? [b.text] : b.type === "bullets" || b.type === "numbered" ? b.items
      : b.type === "table" ? b.rows.flat() : [];
    for (const t of texts) {
      for (const m of t.matchAll(/\[@([^\]]+)\]/g)) {
        for (const key of m[1].split(";").map((k) => k.trim().replace(/^@/, ""))) {
          if (!REFS[key]) throw new Error(`Unknown citation key ${key}`);
          if (!citeOrder.includes(key)) citeOrder.push(key);
        }
      }
    }
  }
}
chapters.forEach((blocks, idx) => numberBlocks(blocks, () => String(idx + 1)));
numberBlocks(appendices, (h) => h.text.match(/^Appendix ([A-Z])/)[1]);

// ---------------------------------------------------------------- inline text

function resolveText(text) {
  return text
    .replace(/\[@([^\]]+)\]/g, (_, keys) =>
      keys.split(";").map((k) => `[${citeOrder.indexOf(k.trim().replace(/^@/, "")) + 1}]`).join(", "))
    .replace(/@((?:fig|tab|eq):[\w-]+)/g, (_, label) => {
      if (!labels[label]) throw new Error(`Unknown reference ${label}`);
      return labels[label];
    });
}

function runs(text, base = {}) {
  const out = [];
  const tokens = resolveText(text).split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g);
  for (const token of tokens) {
    if (!token) continue;
    if (token.startsWith("`")) out.push(new TextRun({ text: token.slice(1, -1), font: MONO, size: (base.size || 24) - 3 }));
    else if (token.startsWith("**")) out.push(new TextRun({ ...base, text: token.slice(2, -2), bold: true }));
    else if (token.startsWith("*")) out.push(new TextRun({ ...base, text: token.slice(1, -1), italics: true }));
    else out.push(new TextRun({ ...base, text: token }));
  }
  return out;
}

// ---------------------------------------------------------------- block rendering

let listInstance = 0;

function pngSize(file) {
  const buf = fs.readFileSync(file);
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20), buf };
}

function figure(b) {
  const file = path.join(ROOT, b.src);
  const { w, h, buf } = pngSize(file);
  let widthIn;
  if (b.src.startsWith("diagrams/")) widthIn = (w / 2 / 96) * 0.85; // Scale-2 renders, shown at 85% of CSS size.
  else if (b.src.includes("/fig-")) widthIn = (w / 200) * 0.9; // Matplotlib at 200 dpi, shown at 90%.
  else widthIn = MAX_W_IN; // Screenshots use the full text width.
  widthIn = Math.min(widthIn, MAX_W_IN);
  let heightIn = (widthIn * h) / w;
  if (heightIn > MAX_H_IN) { widthIn *= MAX_H_IN / heightIn; heightIn = MAX_H_IN; }
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60, line: 240 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: Math.round(widthIn * 96), height: Math.round(heightIn * 96) } })],
    }),
    new Paragraph({
      style: "FigureCaption",
      children: [new TextRun({ text: `Figure ${b.number}: `, bold: true }), ...runs(b.caption)],
    }),
  ];
}

function table(b) {
  const cols = b.rows[0].length;
  const weights = Array.from({ length: cols }, (_, c) =>
    Math.max(6, Math.min(48, Math.max(...b.rows.map((r) => resolveText(r[c] || "").length)))));
  const total = weights.reduce((a, x) => a + x, 0);
  const widths = weights.map((x) => Math.floor((x / total) * TEXT_WIDTH));
  widths[cols - 1] += TEXT_WIDTH - widths.reduce((a, x) => a + x, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const rows = b.rows.map((r, ri) => new TableRow({
    tableHeader: ri === 0 && Boolean(b.caption),
    cantSplit: true,
    children: r.map((cell, ci) => new TableCell({
      width: { size: widths[ci], type: WidthType.DXA },
      borders,
      verticalAlign: VerticalAlign.CENTER,
      shading: ri === 0 && b.caption ? { type: ShadingType.CLEAR, fill: "E7E6E3", color: "auto" } : undefined,
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      children: [new Paragraph({
        alignment: AlignmentType.LEFT, spacing: { before: 0, after: 0, line: 240 },
        children: runs(cell, { size: 20, bold: ri === 0 && Boolean(b.caption) }),
      })],
    })),
  }));
  const out = [];
  if (b.caption) {
    out.push(new Paragraph({
      style: "TableCaption",
      children: [new TextRun({ text: `Table ${b.number}: `, bold: true }), ...runs(b.caption)],
    }));
  }
  out.push(new Table({ width: { size: TEXT_WIDTH, type: WidthType.DXA }, columnWidths: widths, rows }));
  out.push(new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }));
  return out;
}

function render(blocks, kind) {
  const out = [];
  let chapterNo = 0;
  for (const b of blocks) {
    switch (b.type) {
      case "heading": {
        if (b.level === 1) {
          let text = b.text;
          if (kind === "chapter") text = `Chapter ${++chapterNo + chapterOffset}: ${b.text}`;
          out.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: runs(text, { font: FONT }) }));
        } else {
          out.push(new Paragraph({ heading: b.level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3, children: runs(b.text, { font: FONT }) }));
        }
        break;
      }
      case "para":
        out.push(new Paragraph({ style: "Body", children: runs(b.text) }));
        break;
      case "bullets":
        for (const item of b.items) out.push(new Paragraph({ style: "Body", numbering: { reference: "bullets", level: 0 }, children: runs(item) }));
        break;
      case "numbered": {
        const instance = ++listInstance;
        for (const item of b.items) out.push(new Paragraph({ style: "Body", numbering: { reference: "numbers", level: 0, instance }, children: runs(item) }));
        break;
      }
      case "code":
        b.lines.forEach((l, idx) => out.push(new Paragraph({
          style: "Code",
          spacing: { before: idx === 0 ? 120 : 0, after: idx === b.lines.length - 1 ? 160 : 0, line: 240 },
          children: [new TextRun({ text: l || " ", font: MONO, size: 18 })],
        })));
        break;
      case "equation":
        out.push(new Paragraph({
          style: "Equation",
          tabStops: [{ type: TabStopType.CENTER, position: TEXT_WIDTH / 2 }, { type: TabStopType.RIGHT, position: TEXT_WIDTH }],
          children: [new TextRun({ text: "\t" }), new TextRun({ text: b.text, font: "Cambria Math" }), new TextRun({ text: `\t(${b.number})` })],
        }));
        break;
      case "figure":
        out.push(...figure(b));
        break;
      case "table":
        out.push(...table(b));
        break;
      default:
        throw new Error(`unknown block ${b.type}`);
    }
  }
  return out;
}
let chapterOffset = 0;

// ---------------------------------------------------------------- page assembly

function centered(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: opts.before ?? 0, after: opts.after ?? 120, line: 300 },
    children: [new TextRun({ text, font: FONT, size: opts.size ?? 24, bold: opts.bold, italics: opts.italics })],
  });
}

const logo = fs.readFileSync(path.join(ROOT, "figures", "scsvmv-logo.png"));
const titlePage = [
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 240 },
    children: [new ImageRun({ type: "png", data: logo, transformation: { width: 120, height: Math.round((120 * logo.readUInt32BE(20)) / logo.readUInt32BE(16)) } })],
  }),
  centered("INDUSTRIAL TWIN-X", { size: 40, bold: true, after: 160 }),
  centered("An Intelligent, Autonomous and Cyber-Resilient Industrial Internet of Things Digital Twin Using Software Simulation", { size: 30, bold: true, after: 360 }),
  centered("A Project Report submitted in partial fulfilment of the requirements for the award of the degree of", { after: 120 }),
  centered("Bachelor of Technology", { size: 28, bold: true, after: 60 }),
  centered("in", { after: 60 }),
  centered("Computer Science and Engineering", { size: 28, bold: true, after: 360 }),
  centered("Submitted by", { italics: true }),
  centered("BOLLAVRAM SANDEEP KUMAR (11249A040)"),
  centered("D. GOPALA KRISHNA RAYUDU (11249A078)"),
  centered("K. HARISH (11249A150)", { after: 360 }),
  centered("Under the guidance of", { italics: true }),
  centered("Ms. HEMA POORANI J", { bold: true }),
  centered("[DESIGNATION OF PROJECT GUIDE]", { after: 300 }),
  centered("DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING", { bold: true }),
  centered("SRI CHANDRASEKHARENDRA SARASWATHI VISWA MAHAVIDYALAYA", { bold: true }),
  centered("KANCHEEPURAM"),
  centered("[ACADEMIC YEAR]", { after: 200 }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 40, line: 240 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(ROOT, "figures", "github-qr.png")), transformation: { width: 84, height: 84 } })],
  }),
  centered("Source code: https://github.com/sandeepbollavaram/industrial-twin-x", { size: 18, after: 160 }),
];

function listPage(title, options) {
  return [
    new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun({ text: title, font: FONT })] }),
    new TableOfContents(title, options),
  ];
}

const frontRendered = render(front, "front");
// Insert contents, figure and table lists before the abbreviations page (the last front section).
const abbrevIndex = frontRendered.findIndex((p) => p instanceof Paragraph && JSON.stringify(p).includes("List of Abbreviations"));
const contents = [
  new Paragraph({ style: "ContentsTitle", pageBreakBefore: true, children: [new TextRun({ text: "Table of Contents" })] }),
  new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
  ...listPage("List of Figures", { hyperlink: true, stylesWithLevels: [new StyleLevel("Figure Caption", 1)] }),
  ...listPage("List of Tables", { hyperlink: true, stylesWithLevels: [new StyleLevel("Table Caption", 1)] }),
];
frontRendered.splice(abbrevIndex, 0, ...contents);

const body = [];
chapters.forEach((blocks) => body.push(...render(blocks, "chapter")) && chapterOffset++);
// render() numbers chapters from its own counter; correct it with the running offset above.

const references = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun({ text: "References", font: FONT })] }),
  ...citeOrder.map((key, idx) => new Paragraph({
    style: "Reference",
    tabStops: [{ type: TabStopType.LEFT, position: 600 }],
    children: [new TextRun({ text: `[${idx + 1}]\t` }), new TextRun({ text: REFS[key].ieee })],
  })),
];
const appendixRendered = render(appendices, "appendix");

const footer = new Footer({
  children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 22 })] })],
});
const header = new Header({
  children: [new Paragraph({
    alignment: AlignmentType.RIGHT,
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "999999", space: 4 } },
    children: [new TextRun({ text: "Industrial Twin-X: Software-Simulated IIoT Digital Twin", font: FONT, size: 18, italics: true, color: "555555" })],
  })],
});
const page = { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440, header: 708, footer: 708 } };

const doc = new Document({
  creator: "Bollavram Sandeep Kumar, D. Gopala Krishna Rayudu, K. Harish",
  title: "Industrial Twin-X: An Intelligent, Autonomous and Cyber-Resilient IIoT Digital Twin Using Software Simulation",
  description: "B.Tech major project report (software simulation)",
  styles: {
    default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: 360 } } } },
    paragraphStyles: [
      { id: "Body", name: "Body Text Report", basedOn: "Normal", run: { font: FONT, size: 24 }, paragraph: { alignment: AlignmentType.JUSTIFIED, spacing: { before: 0, after: 120, line: 360 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Body", quickFormat: true, run: { font: FONT, size: 32, bold: true }, paragraph: { spacing: { before: 0, after: 360, line: 276 }, keepNext: true, keepLines: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Body", quickFormat: true, run: { font: FONT, size: 28, bold: true }, paragraph: { spacing: { before: 300, after: 120, line: 276 }, keepNext: true, keepLines: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Body", quickFormat: true, run: { font: FONT, size: 24, bold: true }, paragraph: { spacing: { before: 200, after: 80, line: 276 }, keepNext: true, keepLines: true, outlineLevel: 2 } },
      { id: "FigureCaption", name: "Figure Caption", basedOn: "Normal", run: { font: FONT, size: 21 }, paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 60, after: 240, line: 276 } } },
      { id: "TableCaption", name: "Table Caption", basedOn: "Normal", run: { font: FONT, size: 21 }, paragraph: { alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 80, line: 276 } } },
      { id: "Equation", name: "Equation", basedOn: "Normal", run: { font: FONT, size: 24 }, paragraph: { spacing: { before: 120, after: 160, line: 276 } } },
      { id: "Code", name: "Code Block", basedOn: "Normal", run: { font: MONO, size: 18 }, paragraph: { shading: { type: ShadingType.CLEAR, fill: "F3F3F1", color: "auto" }, indent: { left: 240 } } },
      { id: "Reference", name: "Reference Entry", basedOn: "Normal", run: { font: FONT, size: 22 }, paragraph: { alignment: AlignmentType.LEFT, indent: { left: 600, hanging: 600 }, spacing: { before: 0, after: 100, line: 276 } } },
      { id: "ContentsTitle", name: "Contents Title", basedOn: "Normal", run: { font: FONT, size: 32, bold: true }, paragraph: { spacing: { before: 0, after: 360 } } },
      { id: "TOC1", name: "toc 1", basedOn: "Normal", run: { font: FONT, size: 22 }, paragraph: { spacing: { before: 60, after: 0, line: 276 } } },
      { id: "TOC2", name: "toc 2", basedOn: "Normal", run: { font: FONT, size: 22 }, paragraph: { indent: { left: 360 }, spacing: { before: 0, after: 0, line: 276 } } },
      { id: "TOC3", name: "toc 3", basedOn: "Normal", run: { font: FONT, size: 22 }, paragraph: { indent: { left: 720 }, spacing: { before: 0, after: 0, line: 276 } } },
      { id: "TableofFigures", name: "table of figures", basedOn: "Normal", run: { font: FONT, size: 22 }, paragraph: { spacing: { before: 0, after: 40, line: 276 } } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    ],
  },
  sections: [
    { properties: { page }, children: titlePage },
    {
      properties: { page: { ...page, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } },
      footers: { default: footer },
      children: frontRendered,
    },
    {
      properties: { page: { ...page, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } },
      headers: { default: header },
      footers: { default: footer },
      children: [...body, ...references, ...appendixRendered],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  const words = [front, ...chapters, appendices].flat()
    .map((b) => (b.type === "para" ? b.text : (b.items || []).join(" ")))
    .join(" ").split(/\s+/).filter(Boolean).length;
  console.log(`wrote ${path.basename(OUT)}: ${chapters.length} chapters, ${figureList.length} figures, ${tableList.length} tables, ${citeOrder.length} references cited, ~${words} words of prose`);
  const unused = Object.keys(REFS).filter((k) => !citeOrder.includes(k));
  if (unused.length) console.log("verified but not cited:", unused.join(", "));
});
