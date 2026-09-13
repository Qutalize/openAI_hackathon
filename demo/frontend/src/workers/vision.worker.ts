import { FaceLandmarker, HandLandmarker, PoseLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import { faceFeatures, signFeatures } from './features';

let face: FaceLandmarker | undefined, hands: HandLandmarker | undefined, pose: PoseLandmarker | undefined;
let kind: 'lipread' | 'sign' = 'lipread';
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
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
      const bitmap = data.bitmap as ImageBitmap;
      try {
        const f = face.detectForVideo(bitmap, data.timestamp).faceLandmarks;
        let features: number[][];
        if (kind === 'lipread') features = faceFeatures(f.length === 1 ? f[0] : []);
        else {
          const h = hands!.detectForVideo(bitmap, data.timestamp);
          const p = pose!.detectForVideo(bitmap, data.timestamp);
          features = signFeatures(
            f.length === 1 ? f[0] : [],
            p.landmarks[0] ?? [],
            h.landmarks,
            h.handedness.map((c) => c[0].categoryName),
          );
        }
        self.postMessage({ type: 'features', features, timestamp: data.timestamp });
      } finally {
        bitmap.close();
      }
    }
  } catch (error) {
    console.error('Vision worker initialization failed:', error);
    self.postMessage({
      type: 'error',
      message: '特徴点モデルを開始できません。モデル準備とカメラを確認してください',
    });
  }
};
