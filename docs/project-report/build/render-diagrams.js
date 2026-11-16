// Renders every diagrams/*.mmd to diagrams/png/*.png with mermaid-cli and the local Chrome.
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const dir = path.join(__dirname, "..", "diagrams");
const out = path.join(dir, "png");
fs.mkdirSync(out, { recursive: true });
const cli = path.join(__dirname, "node_modules", "@mermaid-js", "mermaid-cli", "src", "cli.js");
for (const file of fs.readdirSync(dir).filter((f) => f.endsWith(".mmd"))) {
  const target = path.join(out, file.replace(/\.mmd$/, ".png"));
  execFileSync(process.execPath, [cli, "-i", path.join(dir, file), "-o", target, "-b", "white", "-s", "2",
    "-p", path.join(__dirname, "puppeteer.json"),
    "-c", path.join(__dirname, "mermaid-config.json")], { stdio: "inherit" });
  console.log("rendered", path.basename(target));
}
