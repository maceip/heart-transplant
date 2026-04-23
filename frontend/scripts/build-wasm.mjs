import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const emsdkRoot = path.join(root, '.tools', 'emsdk');
const emcc = path.join(emsdkRoot, 'upstream', 'emscripten', 'emcc.bat');
const input = path.join(root, 'wasm', 'g3mark_engine.c');
const outputDir = path.join(root, 'src', 'wasm', 'generated');
const output = path.join(outputDir, 'g3mark-engine.js');

await mkdir(outputDir, { recursive: true });

if (!(await canAccess(emcc))) {
  throw new Error(
    'Emscripten toolchain not found at frontend/.tools/emsdk. Set up a local emsdk checkout before running build:wasm.',
  );
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
