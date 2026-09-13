export class VisionCapture {
  private worker?: Worker;
  private timer?: ReturnType<typeof setTimeout>;
  private video?: HTMLVideoElement;
  private stopped = true;
  private busy = false;
  private cancelLoading?: () => void;
  async start(
    stream: MediaStream,
    kind: 'lipread' | 'sign',
    onFrame: (features: number[][], timestamp: number) => void,
    onError: (s: string) => void,
  ) {
    this.stop();
    this.stopped = false;
    const video = (this.video = document.createElement('video'));
    video.srcObject = stream;
    video.muted = true;
    video.playsInline = true;
    await video.play();
    if (this.stopped) return;
    const worker = (this.worker = new Worker('/workers/vision.js'));
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('特徴点モデルの開始がタイムアウトしました'));
        this.stop();
      }, 30000);
      this.cancelLoading = () => {
        clearTimeout(timeout);
        reject(new Error('撮影を取り消しました'));
      };
      worker.onerror = () => {
        clearTimeout(timeout);
        reject(new Error('特徴点モデルを読み込めません'));
        this.stop();
      };
      worker.onmessage = ({ data }) => {
        if (data.type === 'ready') {
          clearTimeout(timeout);
          this.cancelLoading = undefined;
          resolve();
          this.tick();
        } else if (data.type === 'features') {
          this.busy = false;
          if (!this.stopped) onFrame(data.features, data.timestamp);
        } else if (data.type === 'error') {
          clearTimeout(timeout);
          reject(new Error(data.message));
          onError(data.message);
          this.stop();
        }
      };
      worker.postMessage({ type: 'init', kind });
    });
  }
  private tick = async () => {
    if (this.stopped) return;
    if (!this.busy && this.video && this.video.readyState >= 2) {
      this.busy = true;
      const timestamp = performance.now();
      try {
        const bitmap = await createImageBitmap(this.video);
        if (this.stopped) bitmap.close();
        else this.worker?.postMessage({ type: 'frame', bitmap, timestamp }, [bitmap]);
      } catch {
        this.busy = false;
      }
    }
    this.timer = setTimeout(this.tick, 50);
  };
  stop() {
    this.cancelLoading?.();
    this.cancelLoading = undefined;
    this.stopped = true;
    this.busy = false;
    clearTimeout(this.timer);
    this.worker?.terminate();
    this.worker = undefined;
    if (this.video) {
      this.video.pause();
      this.video.srcObject = null;
    }
    this.video = undefined;
  }
}
