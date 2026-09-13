export const LIP_INDICES = [
  61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78, 191,
  80, 81, 82, 13, 312, 311, 310, 415, 409, 270, 269, 267, 0, 37, 39, 40, 185,
];
export const FACE_INDICES = [
  1, 4, 33, 133, 263, 362, 61, 291, 13, 14, 17, 0, 70, 63, 105, 66, 107, 336, 296, 334, 293, 300, 152, 234,
  454,
];
export interface Landmark {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}
export function faceFeatures(face: Landmark[], indices = LIP_INDICES) {
  if (!face.length) return Array.from({ length: indices.length }, () => [0, 0, 0, 0]);
  const left = face[234],
    right = face[454];
  const dx = right.x - left.x,
    dy = right.y - left.y,
    scale = Math.hypot(dx, dy);
  if (scale < 0.001) return Array.from({ length: indices.length }, () => [0, 0, 0, 0]);
  const cx = (left.x + right.x) / 2,
    cy = (left.y + right.y) / 2,
    cz = (left.z + right.z) / 2;
  return indices.map((i) => {
    const p = face[i],
      x = p.x - cx,
      y = p.y - cy;
    return [(x * dx + y * dy) / (scale * scale), (y * dx - x * dy) / (scale * scale), (p.z - cz) / scale, 1];
  });
}
export function signFeatures(face: Landmark[], pose: Landmark[], hands: Landmark[][], handedness: string[]) {
  const zero = () => [0, 0, 0, 0];
  if (!pose.length || (pose[11].visibility ?? 0) < 0.5 || (pose[12].visibility ?? 0) < 0.5)
    return Array.from({ length: 100 }, zero);
  const l = pose[11],
    r = pose[12],
    cx = (l.x + r.x) / 2,
    cy = (l.y + r.y) / 2,
    scale = Math.hypot(l.x - r.x, l.y - r.y);
  if (scale < 0.001) return Array.from({ length: 100 }, zero);
  const normalize = (p: Landmark, z0: number) =>
    (p.visibility ?? 1) < 0.5 ? zero() : [(p.x - cx) / scale, (p.y - cy) / scale, (p.z - z0) / scale, 1];
  const results: number[][] = [];
  for (const side of ['Left', 'Right']) {
    const matches = handedness.map((s, i) => (s === side ? i : -1)).filter((i) => i >= 0);
    const hand = matches.length === 1 ? hands[matches[0]] : undefined;
    results.push(...(hand ? hand.map((p) => normalize(p, hand[0].z)) : Array.from({ length: 21 }, zero)));
  }
  results.push(...pose.map((p) => normalize(p, (pose[23].z + pose[24].z) / 2)));
  results.push(
    ...(face.length
      ? FACE_INDICES.map((i) => normalize(face[i], face[1].z))
      : Array.from({ length: 25 }, zero)),
  );
  return results;
}
