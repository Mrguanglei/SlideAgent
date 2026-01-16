const fs = require("node:fs");
const path = require("node:path");
const fg = require("fast-glob");
const minimist = require("minimist");
const pptxgen = require("pptxgenjs");
const html2pptx = require("./html2pptx");

const LAYOUT_MAP = {
  widescreen: "LAYOUT_WIDE",
  normal: "LAYOUT_4x3",
};

const A1_LAYOUT = {
  name: "A1",
  width: 23.39,
  height: 33.11,
};

async function run() {
  const args = minimist(process.argv.slice(2));
  const layout = args.layout || "widescreen";
  const outputFile = args.output;
  const validateOnly = Boolean(args.validate);
  const htmlDir = args.html_dir || args["html-dir"];
  let htmlFiles = [];

  if (args.html) {
    htmlFiles = Array.isArray(args.html) ? args.html : String(args.html).split(",");
    htmlFiles = htmlFiles.map((file) => path.resolve(file.trim())).filter(Boolean);
  }

  if (htmlDir && htmlFiles.length) {
    console.error("Use either --html_dir or --html, not both.");
    process.exit(1);
  }

  if (htmlDir) {
    if (!fs.existsSync(htmlDir) || !fs.statSync(htmlDir).isDirectory()) {
      console.error(`HTML directory not found: ${htmlDir}`);
      process.exit(1);
    }
    htmlFiles = fg.sync("*.html", { cwd: htmlDir, absolute: true }).sort();
  }

  if (!htmlFiles.length) {
    console.error(
      "Usage: node html2pptx_cli.js --html_dir <dir> | --html <file> [--html <file2>] --output <file.pptx> --layout <widescreen|normal|A1> [--validate]"
    );
    process.exit(1);
  }

  if (!validateOnly && !outputFile) {
    console.error("Missing --output for PPTX generation.");
    process.exit(1);
  }

  const pptx = new pptxgen();
  if (layout === "A1") {
    pptx.defineLayout(A1_LAYOUT);
    pptx.layout = "A1";
  } else if (LAYOUT_MAP[layout]) {
    pptx.layout = LAYOUT_MAP[layout];
  } else {
    console.error(`Unsupported layout: ${layout}`);
    process.exit(1);
  }

  for (const htmlFile of htmlFiles) {
    await html2pptx(htmlFile, pptx);
  }

  if (!validateOnly) {
    const outputPath = path.resolve(outputFile);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    await pptx.writeFile({ fileName: outputPath });
  }
}

run().catch((err) => {
  console.error(err?.stack || err?.message || String(err));
  process.exit(1);
});
