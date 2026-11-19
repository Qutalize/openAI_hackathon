import type { FeaturePoints } from '../services/visionCapture';

const HAND = [
  [0, 1, 2, 3, 4],
  [0, 5, 6, 7, 8],
  [5, 9, 10, 11, 12],
  [9, 13, 14, 15, 16],
  [13, 17, 18, 19, 20],
  [0, 17],
];
// Upper body only: the sign features are centred on the shoulders.
const POSE = [
  [15, 13, 11, 12, 14, 16],
  [11, 23, 24, 12],
];

/** Draws the landmarks the features are built from over a preview shown with object-fit: contain. */
export function drawLandmarks(canvas: HTMLCanvasElement, points?: FeaturePoints) {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth,
    H = canvas.clientHeight;
  if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
  }
  const g = canvas.getContext('2d');
  if (!g) return;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  if (!points?.width) return;
  const s = Math.min(W / points.width, H / points.height),
    ox = (W - points.width * s) / 2,
    oy = (H - points.height * s) / 2;
  const at = (p: number[]) => [ox + p[0] * points.width * s, oy + p[1] * points.height * s];
  const color = points.valid ? '#35e0a1' : '#ff5c5c';
  g.lineWidth = 2;
  const line = (ps: (number[] | null | undefined)[], chains: number[][], stroke: string) => {
    g.strokeStyle = stroke;
    for (const chain of chains) {
      g.beginPath();
      let drawing = false;
      for (const i of chain) {
        const p = ps[i];
        if (!p) {
          drawing = false;
          continue;
        }
        const [x, y] = at(p);
        if (drawing) g.lineTo(x, y);
        else g.moveTo(x, y);
        drawing = true;
      }
      g.stroke();
    }
  };
  const dots = (ps: (number[] | null | undefined)[], fill: string, r = 2.5) => {
    g.fillStyle = fill;
    for (const p of ps) {
      if (!p) continue;
      const [x, y] = at(p);
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    }
  };
  if (points.pose?.length) {
    line(points.pose, POSE, color);
    dots(points.pose.slice(0, 25), color, 3);
  }
  for (const hand of points.hands ?? []) {
    line(hand, HAND, '#ffd166');
    dots(hand, '#ffd166');
  }
  if (points.face) dots(points.face, '#7cc4ff');
  if (points.lips?.length) {
    line(points.lips, [[...Array(11).keys()]], color);
    dots(points.lips, color, 2);
  }
}
