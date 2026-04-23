import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const backendRoot = path.join(root, 'backend');
const frontendRoot = path.join(root, 'frontend');

const children = [
  spawn(process.execPath, ['src/scan-server.mjs'], {
    cwd: backendRoot,
    stdio: 'inherit',
    shell: false,
  }),
  process.platform === 'win32'
    ? spawn('cmd.exe', ['/d', '/s', '/c', 'npx vite'], {
        cwd: frontendRoot,
        stdio: 'inherit',
        shell: false,
      })
    : spawn('npx', ['vite'], {
        cwd: frontendRoot,
        stdio: 'inherit',
        shell: false,
      }),
];

for (const child of children) {
  child.on('exit', (code) => {
    if (code && code !== 0) {
      process.exitCode = code;
    }
    shutdown();
  });
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

function shutdown() {
  for (const child of children) {
    if (!child.killed) {
      child.kill();
    }
  }
}
