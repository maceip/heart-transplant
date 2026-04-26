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
const wasmOutput = path.join(outputDir, 'g3mark-engine.wasm');

await mkdir(outputDir, { recursive: true });

if (!(await canAccess(emcc))) {
  await compileWithClang();
  await writeWasmRuntimeLoader(output, path.basename(wasmOutput));
  await validateWasmRuntime();
  console.warn(`[build-wasm] Emscripten compiler not found at ${emcc}; built WASI-free wasm with clang.`);
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


async function compileWithClang() {
  const clang = process.env.CLANG || 'clang';
  const sysroot = process.env.WASI_SYSROOT || '/usr';
  const args = [
    '--target=wasm32-wasi',
    `--sysroot=${sysroot}`,
    '-O3',
    '-DG3MARK_WASI_BUILD',
    '-mexec-model=reactor',
    '-Wl,--no-entry',
    '-Wl,--export=malloc',
    '-Wl,--export=free',
    '-Wl,--export=render_markdown',
    '-Wl,--export=render_diff',
    '-Wl,--export=render_diff_stats',
    '-Wl,--allow-undefined',
    input,
    '-o',
    wasmOutput,
  ];

  await run(clang, args, root);
}

async function writeWasmRuntimeLoader(target, wasmFileName) {
  await writeFile(
    target,
    `const decoder = new TextDecoder('utf-8');
const encoder = new TextEncoder();

async function instantiateWasm(wasmUrl, imports) {
  if (wasmUrl.protocol === 'file:') {
    const { readFile } = await import('node:fs/promises');
    const bytes = await readFile(wasmUrl);
    return WebAssembly.instantiate(bytes, imports);
  }

  return WebAssembly.instantiateStreaming(fetch(wasmUrl), imports).catch(async () => {
    const response = await fetch(wasmUrl);
    return WebAssembly.instantiate(await response.arrayBuffer(), imports);
  });
}

export default async function initG3markEngine() {
  const wasmUrl = new URL('./${wasmFileName}', import.meta.url);
  const imports = {
    env: {},
    wasi_snapshot_preview1: {
      fd_close: () => 0,
      fd_seek: (_fd, _offset, _whence, resultPointer) => {
        const view = new DataView(instanceExports.memory.buffer);
        view.setBigUint64(resultPointer, 0n, true);
        return 0;
      },
      fd_write: (_fd, _iovs, _iovsLen, bytesWrittenPointer) => {
        new DataView(instanceExports.memory.buffer).setUint32(bytesWrittenPointer, 0, true);
        return 0;
      },
    },
  };
  let instanceExports;
  const result = await instantiateWasm(wasmUrl, imports);
  const instance = result.instance;
  const exports = instance.exports;
  instanceExports = exports;

  function memory() {
    return exports.memory;
  }

  function writeString(value) {
    const bytes = encoder.encode(String(value));
    const pointer = exports.malloc(bytes.length + 1);
    const view = new Uint8Array(memory().buffer, pointer, bytes.length + 1);
    view.set(bytes);
    view[bytes.length] = 0;
    return pointer;
  }

  function readString(pointer) {
    const view = new Uint8Array(memory().buffer);
    let end = pointer;
    while (view[end] !== 0) end += 1;
    return decoder.decode(view.subarray(pointer, end));
  }

  function wrapStringFunction(name) {
    const fn = exports[name];
    return (...values) => {
      const pointers = values.map(writeString);
      try {
        return fn(...pointers);
      } finally {
        for (const pointer of pointers) exports.free(pointer);
      }
    };
  }

  return {
    UTF8ToString: readString,
    _free(pointer) {
      exports.free(pointer);
    },
    cwrap(name) {
      if (name === 'render_markdown' || name === 'render_diff' || name === 'render_diff_stats') {
        return wrapStringFunction(name);
      }
      return exports[name];
    },
  };
}
`,
    'utf8',
  );
}

async function validateWasmRuntime() {
  const { default: initG3markEngine } = await import(`${output}?cache=${Date.now()}`);
  const module = await initG3markEngine();
  const renderStats = module.cwrap('render_diff_stats', 'number', ['string', 'string']);
  const pointer = renderStats('same\nold', 'same\nnew\nadded');
  const stats = JSON.parse(module.UTF8ToString(pointer));
  module._free(pointer);

  if (stats.shared !== 1 || stats.changed !== 1 || stats.added !== 1 || stats.removed !== 0) {
    throw new Error(`WASM runtime validation failed: ${JSON.stringify(stats)}`);
  }
}
