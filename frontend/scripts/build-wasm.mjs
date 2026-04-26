import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const emsdkRoot = path.join(root, '.tools', 'emsdk');
const localEmcc = path.join(
  emsdkRoot,
  'upstream',
  'emscripten',
  process.platform === 'win32' ? 'emcc.bat' : 'emcc',
);
const emcc = process.env.EMCC || localEmcc;
const input = path.join(root, 'wasm', 'g3mark_engine.c');
const outputDir = path.join(root, 'src', 'wasm', 'generated');
const output = path.join(outputDir, 'g3mark-engine.js');

await mkdir(outputDir, { recursive: true });

if (!(await canAccess(emcc))) {
  await writeFallbackRuntime(output);
  console.warn(
    `[build-wasm] Emscripten compiler not found at ${emcc}; wrote JS fallback runtime to ${path.relative(root, output)}.`,
  );
  process.exit(0);
}

const args = [
  input,
  '-O3',
  '-sMODULARIZE=1',
  '-sEXPORT_ES6=1',
  '-sENVIRONMENT=web',
  '-sFILESYSTEM=0',
  '-sALLOW_MEMORY_GROWTH=1',
  '-sEXPORTED_FUNCTIONS=["_malloc","_free","_render_markdown","_render_diff","_render_diff_stats"]',
  '-sEXPORTED_RUNTIME_METHODS=["UTF8ToString","cwrap"]',
  '-o',
  output,
];

await run(emcc, args, root);

async function canAccess(target) {
  try {
    await import('node:fs/promises').then(({ access }) => access(target));
    return true;
  } catch {
    return false;
  }
}

function run(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      stdio: 'inherit',
      shell: process.platform === 'win32',
    });

    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`WASM build failed with exit code ${code ?? 'unknown'}`));
    });

    child.on('error', (error) => reject(error));
  });
}

async function writeFallbackRuntime(target) {
  await writeFile(
    target,
    `const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

function renderMarkdown(content) {
  const blocks = String(content).split(/\\n{2,}/).filter(Boolean);
  const html = blocks.map((block) => {
    if (/^#\\s+/.test(block)) return '<h1>' + escapeHtml(block.replace(/^#\\s+/, '')) + '</h1>';
    if (/^##\\s+/.test(block)) return '<h2>' + escapeHtml(block.replace(/^##\\s+/, '')) + '</h2>';
    if (/^\\\`\\\`\\\`/.test(block)) {
      return '<pre class="g3mark-code-block"><code>' + escapeHtml(block.replace(/^\\\`\\\`\\\`\\w*\\n?/, '').replace(/\\\`\\\`\\\`$/, '')) + '</code></pre>';
    }
    return '<p>' + escapeHtml(block).replace(/\\n/g, '<br />') + '</p>';
  }).join('');
  return '<div class="g3mark-document">' + html + '</div>';
}

function diffLines(original, modified) {
  const left = String(original).split('\\n');
  const right = String(modified).split('\\n');
  const rows = [];
  const max = Math.max(left.length, right.length);
  for (let index = 0; index < max; index += 1) {
    const before = left[index] ?? '';
    const after = right[index] ?? '';
    if (before === after) rows.push({ type: 'shared', before, after });
    else if (before && after) rows.push({ type: 'changed', before, after });
    else if (before) rows.push({ type: 'removed', before, after: '' });
    else rows.push({ type: 'added', before: '', after });
  }
  return rows;
}

function renderDiff(original, modified) {
  const rows = diffLines(original, modified).map((row) =>
    '<div class="g3mark-diff-line g3mark-diff-line--' + row.type + '">' +
      '<span class="g3mark-diff-marker">' + markerFor(row.type) + '</span>' +
      '<span class="g3mark-diff-original">' + escapeHtml(row.before) + '</span>' +
      '<span class="g3mark-diff-arrow">-></span>' +
      '<span class="g3mark-diff-modified">' + escapeHtml(row.after) + '</span>' +
    '</div>'
  ).join('');
  return '<div class="g3mark-diff">' + rows + '</div>';
}

function markerFor(type) {
  if (type === 'added') return '+';
  if (type === 'removed') return '-';
  if (type === 'changed') return '~';
  return ' ';
}

function renderDiffStats(original, modified) {
  return JSON.stringify(diffLines(original, modified).reduce((stats, row) => {
    stats[row.type] += 1;
    return stats;
  }, { added: 0, removed: 0, changed: 0, shared: 0 }));
}

export default async function initG3markEngine() {
  let nextPointer = 1;
  const heap = new Map();
  const store = (value) => {
    const pointer = nextPointer;
    nextPointer += 1;
    heap.set(pointer, value);
    return pointer;
  };

  const functions = {
    render_markdown: (content) => store(renderMarkdown(content)),
    render_diff: (original, modified) => store(renderDiff(original, modified)),
    render_diff_stats: (original, modified) => store(renderDiffStats(original, modified)),
  };

  return {
    UTF8ToString(pointer) {
      return heap.get(pointer) ?? '';
    },
    _free(pointer) {
      heap.delete(pointer);
    },
    cwrap(name) {
      return functions[name];
    },
  };
}
`,
    'utf8',
  );
}
