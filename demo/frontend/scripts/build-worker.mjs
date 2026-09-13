import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
await build({
  absWorkingDir: root,
  entryPoints: ['src/workers/vision.worker.ts'],
  outfile: 'public/workers/vision.js',
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: 'es2022',
  minify: true,
});
console.log('Classic vision worker built (MediaPipe WASM loader uses importScripts).');
