import { cp, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
await mkdir(`${root}/public/models/mediapipe/wasm`, { recursive: true });
await cp(`${root}/node_modules/@mediapipe/tasks-vision/wasm`, `${root}/public/models/mediapipe/wasm`, { recursive: true });
console.log('Pinned MediaPipe WASM copied into public/models/mediapipe/wasm');
