import { defineConfig } from '@playwright/test';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..');
const python =
  process.platform === 'win32'
    ? path.join(root, 'backend/.venv/Scripts/python.exe')
    : path.join(root, 'backend/.venv/bin/python');
export default defineConfig({
  testDir: '../tests/e2e',
  tsconfig: '../tests/e2e/tsconfig.json',
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  outputDir: '../.cache/test-results',
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    viewport: { width: 1600, height: 1000 },
    permissions: ['camera', 'microphone'],
    channel: process.env.PLAYWRIGHT_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined),
    launchOptions: {
      args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--disable-gpu'],
    },
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${python}" "${path.join(root, 'tests/e2e/server.py')}"`,
      url: 'http://127.0.0.1:8000/health/live',
      timeout: 180000,
      reuseExistingServer: false,
    },
    { command: 'npm run dev', url: 'http://localhost:5173', timeout: 60000, reuseExistingServer: false },
  ],
});
