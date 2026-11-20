import { FaceLandmarker, HandLandmarker, PoseLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import { FACE_INDICES, LIP_INDICES, faceFeatures, signFeatures, type Landmark } from './features';

// Image-space positions (0–1) of the landmarks the features are built from, for drawing over the preview.
type Points = { lips?: number[][]; hands?: number[][][]; pose?: (number[] | null)[]; face?: number[][] };
const xy = (p: Landmark) => [p.x, p.y];

let face: FaceLandmarker | undefined, hands: HandLandmarker | undefined, pose: PoseLandmarker | undefined;
let kind: 'lipread' | 'sign' = 'lipread';
let stage: 'init' | 'frame' = 'init';
let failedFrames = 0;
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
      stage = 'init';
      kind = data.kind;
      const files = await FilesetResolver.forVisionTasks('/models/mediapipe/wasm');
      face = await FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: '/models/mediapipe/face_landmarker.task' },
        runningMode: 'VIDEO',
        numFaces: 2,
      });
      if (kind === 'sign') {
        hands = await HandLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: '/models/mediapipe/hand_landmarker.task' },
          runningMode: 'VIDEO',
          numHands: 2,
        });
        pose = await PoseLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: '/models/mediapipe/pose_landmarker.task' },
          runningMode: 'VIDEO',
          numPoses: 1,
        });
      }
      self.postMessage({ type: 'ready' });
    } else if (data.type === 'frame' && face) {
      stage = 'frame';
      const bitmap = data.bitmap as ImageBitmap;
      try {
        const f = face.detectForVideo(bitmap, data.timestamp).faceLandmarks;
        let features: number[][];
        let points: Points;
        if (kind === 'lipread') {
          features = faceFeatures(f.length === 1 ? f[0] : []);
          points = { lips: f.length === 1 ? LIP_INDICES.map((i) => xy(f[0][i])) : [] };
        } else {
          const h = hands!.detectForVideo(bitmap, data.timestamp);
          const p = pose!.detectForVideo(bitmap, data.timestamp);
          const handedness = h.handedness.map((c) => c[0].categoryName);
          features = signFeatures(f.length === 1 ? f[0] : [], p.landmarks[0] ?? [], h.landmarks, handedness);
          points = {
            hands: h.landmarks.map((hand) => hand.map(xy)),
            pose: (p.landmarks[0] ?? []).map((q) => ((q.visibility ?? 1) >= 0.5 ? xy(q) : null)),
            face: f.length === 1 ? FACE_INDICES.map((i) => xy(f[0][i])) : [],
          };
        }
        // Everything zero means the frame was rejected (no single face, or shoulders out of view).
        const valid = features.some((x) => x[3] > 0);
        self.postMessage({
          type: 'features',
          features,
          timestamp: data.timestamp,
          points: { ...points, valid, width: bitmap.width, height: bitmap.height },
        });
        failedFrames = 0;
      } finally {
        bitmap.close();
      }
    }
  } catch (error) {
    const detail = String((error as Error)?.message ?? error).slice(0, 120);
    console.error(`Vision worker ${stage} failed:`, error);
    // One bad frame should not end the capture; give up only when frames keep failing.
    if (stage === 'frame' && ++failedFrames < 20) {
      self.postMessage({ type: 'skipped' });
      return;
    }
    self.postMessage({
      type: 'error',
      message:
        stage === 'init'
          ? `特徴点モデルを開始できません（${detail}）`
          : `カメラの映像から特徴点を取れません（${detail}）`,
    });
  }
};
