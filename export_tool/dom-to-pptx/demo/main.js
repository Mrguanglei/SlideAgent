const CDN =
  'https://cdn.jsdelivr.net/npm/dom-to-pptx@latest/dist/dom-to-pptx.bundle.js';
const LOCAL_ICONS = new URL('./icons', window.location.href).href;
const MATERIAL_ICON_ROOT = new URL(
  '../material-design-icons/symbols/web',
  window.location.href
).href;
const LOCAL_MODULE = new URL('./dom-to-pptx.local.js', window.location.href).href;
const LOCAL_VENDOR = new URL('./vendor/dom-to-pptx.bundle.js', window.location.href).href;
const LOCAL_DIST = new URL('../dist/dom-to-pptx.bundle.js', window.location.href).href;

const fileInput = document.querySelector('#htmlFile');
const convertBtn = document.querySelector('#convert');
const statusEl = document.querySelector('#status');
const previewHost = document.querySelector('#previewHost');

const DEFAULT_BLOCK_EXTERNAL = true;
const DEFAULT_ALLOW_SCRIPTS = true;
const DEFAULT_PPTX_NAME = 'export.pptx';

let currentIframe = null;
let currentPptxName = DEFAULT_PPTX_NAME;

function setStatus(message) {
  statusEl.textContent = message;
}

function stripScripts(doc) {
  doc.querySelectorAll('script').forEach((node) => node.remove());
  doc.querySelectorAll('link[rel="modulepreload"]').forEach((node) => node.remove());
  return doc;
}

function stripExternalStyles(doc) {
  doc.querySelectorAll('link[rel="stylesheet"]').forEach((link) => {
    const href = link.getAttribute('href') || '';
    if (/^(https?:)?\/\//i.test(href)) link.remove();
  });

  doc.querySelectorAll('style').forEach((style) => {
    const text = style.textContent || '';
    const cleaned = text.replace(/@import[^;]*;/gi, '');
    if (cleaned !== text) style.textContent = cleaned;
  });
}

function normalizeHtml(htmlText) {
  const doctypeCount = (htmlText.match(/<!doctype\\s+html/gi) || []).length;
  const multiDoc = doctypeCount > 1;

  const firstDoc = multiDoc ? htmlText.split(/<!doctype\\s+html/gi)[1] : htmlText;
  const parser = new DOMParser();
  const doc = parser.parseFromString(firstDoc, 'text/html');
  if (!DEFAULT_ALLOW_SCRIPTS) stripScripts(doc);
  if (DEFAULT_BLOCK_EXTERNAL) stripExternalStyles(doc);
  if (!doc.head.querySelector('meta[charset]')) {
    const meta = doc.createElement('meta');
    meta.setAttribute('charset', 'utf-8');
    doc.head.prepend(meta);
  }
  if (!doc.body) {
    const body = doc.createElement('body');
    doc.documentElement.appendChild(body);
  }
  return {
    html: '<!doctype html>\n' + doc.documentElement.outerHTML,
    multiDoc
  };
}

function createPreview(htmlText) {
  previewHost.innerHTML = '';
  const iframe = document.createElement('iframe');
  iframe.className = 'preview-frame';
  iframe.srcdoc = htmlText;
  previewHost.appendChild(iframe);
  currentIframe = iframe;
  return new Promise((resolve) => {
    iframe.onload = () => resolve(iframe);
  });
}

async function loadScript(win, src, type = 'text/javascript') {
  await new Promise((resolve, reject) => {
    const script = win.document.createElement('script');
    if (type) script.type = type;
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    win.document.head.appendChild(script);
  });
}

async function ensureDomToPptx(win) {
  if (win.domToPptx && win.domToPptx.exportToPptx) return;

  const sources = [
    { src: LOCAL_DIST, type: 'text/javascript' },
    { src: LOCAL_MODULE, type: 'module' },
    { src: LOCAL_VENDOR, type: 'text/javascript' },
    { src: CDN, type: 'text/javascript' },
  ];
  let lastError = null;
  for (const { src, type } of sources) {
    try {
      await loadScript(win, src, type);
      if (win.domToPptx && win.domToPptx.exportToPptx) return;
    } catch (error) {
      lastError = error;
      console.warn(error);
    }
  }

  throw new Error(
    '无法加载 dom-to-pptx。请先在项目根目录执行 pnpm install && pnpm build，' +
      '然后用根目录启动服务（python3 -m http.server 5173），访问 /demo/。' +
      '或者把 dist/dom-to-pptx.bundle.js 复制到 demo/vendor/。'
  );
}

async function waitForAssets(doc) {
  if (doc.fonts && doc.fonts.ready) {
    try {
      await doc.fonts.ready;
    } catch {
      // Ignore font loading errors
    }
  }
  const images = Array.from(doc.images || []);
  if (!images.length) return;
  await Promise.all(
    images.map((img) =>
      img.complete
        ? Promise.resolve()
        : new Promise((resolve) => {
            img.onload = resolve;
            img.onerror = resolve;
          })
    )
  );
}

async function waitForCharts(doc) {
  const canvases = Array.from(doc.querySelectorAll('canvas'));
  if (!canvases.length) return;
  const win = doc.defaultView || window;
  await new Promise((resolve) => win.requestAnimationFrame(resolve));
  await new Promise((resolve) => win.requestAnimationFrame(resolve));
}

function getTargetNodes(doc) {
  const autoMulti = doc.querySelectorAll('.slide, [data-slide]');
  if (autoMulti.length) {
    return Array.from(autoMulti);
  }

  const autoSingle = doc.querySelector('#slide-container');
  if (autoSingle) return [autoSingle];

  return [doc.body];
}

function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name || 'export.pptx';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

fileInput.addEventListener('change', async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  convertBtn.disabled = true;
  setStatus('Reading HTML...');

  const htmlText = await file.text();
  const { html: safeHtml, multiDoc } = normalizeHtml(htmlText);
  await createPreview(safeHtml);

  const baseName = file.name.replace(/\.(html|htm)$/i, '');
  currentPptxName = baseName ? `${baseName}.pptx` : DEFAULT_PPTX_NAME;
  convertBtn.disabled = false;
  setStatus(
    multiDoc
      ? 'Preview ready. Detected multiple HTML docs; only the first is used.'
      : 'Preview ready. Click convert to export.'
  );
});

convertBtn.addEventListener('click', async () => {
  if (!currentIframe) {
    setStatus('Load an HTML file first.');
    return;
  }

  const iframe = currentIframe;
  const doc = iframe.contentDocument;
  const win = iframe.contentWindow;
  if (!doc || !win) {
    setStatus('Preview is not ready yet.');
    return;
  }

  const targets = getTargetNodes(doc);
  if (!targets.length) {
    setStatus('No matching elements found in the document.');
    return;
  }

  try {
    convertBtn.disabled = true;
    setStatus('Loading converter...');
    await ensureDomToPptx(win);
    setStatus('Waiting for assets...');
    await waitForAssets(doc);
    await waitForCharts(doc);
    setStatus('Generating PPTX...');

    const blob = await win.domToPptx.exportToPptx(targets, {
      fileName: currentPptxName || DEFAULT_PPTX_NAME,
      skipDownload: true,
      autoEmbedFonts: false,
      iconMode: 'image',
      iconBaseUrl: MATERIAL_ICON_ROOT,
      iconPathTemplate: '{base}/{name}/materialsymbolsoutlined/{name}_24px.svg'
    });

    downloadBlob(blob, currentPptxName || DEFAULT_PPTX_NAME);
    setStatus('Done. PPTX downloaded.');
  } catch (error) {
    setStatus(error.message || 'Export failed. Check the console for details.');
    console.error(error);
  } finally {
    convertBtn.disabled = false;
  }
});
