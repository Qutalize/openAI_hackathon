// Only the local camera is drawn. Remote tracks and microphone audio never enter this recorder.
export class LocalRecording {
  private recorder?: MediaRecorder;
  private canvas?: HTMLCanvasElement;
  private video?: HTMLVideoElement;
  private output?: MediaStream;
  private timer?: ReturnType<typeof setInterval>;
  private chunks: Blob[] = [];
  private generation = 0;
  private finishing?: Promise<Blob | null>;
  private closed = false;
  private failed = false;
  private saved = false;
  get hasUnsavedRecording() {
    return !!this.recorder && !this.saved;
  }
  constructor(
    private onStatus: (value: string) => void,
    private onError: (value: string) => void,
  ) {}

  async update(stream: MediaStream) {
    const generation = ++this.generation;
    if (this.closed || this.failed) return;
    const track = stream.getVideoTracks().find((t) => t.readyState === 'live');
    if (!track) {
      if (this.recorder?.state === 'recording') this.recorder.pause();
      if (this.video) this.video.srcObject = null;
      this.onStatus('録画待機');
      return;
    }
    if (!('MediaRecorder' in window) || !HTMLCanvasElement.prototype.captureStream) {
      this.failed = true;
      this.onError('録画を開始できません。このブラウザは録画に対応していません。');
      return;
    }
    try {
      const video = (this.video ??= document.createElement('video'));
      video.muted = true;
      video.playsInline = true;
      video.srcObject = new MediaStream([track]);
      await video.play();
      if (this.closed || generation !== this.generation) return;
      if (!this.recorder) {
        const canvas = (this.canvas = document.createElement('canvas'));
        canvas.width = Math.min(video.videoWidth || 1280, 1280);
        canvas.height = Math.round((canvas.width * (video.videoHeight || 720)) / (video.videoWidth || 1280));
        const context = canvas.getContext('2d');
        if (!context) throw new Error('Canvas unavailable');
        const paint = () => {
          if (video.srcObject && video.readyState >= 2)
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
        };
        paint();
        this.timer = setInterval(paint, 1000 / 15);
        this.output = canvas.captureStream(15);
        const mimeType = ['video/webm;codecs=vp8', 'video/webm', 'video/mp4'].find((type) =>
          MediaRecorder.isTypeSupported(type),
        );
        this.recorder = new MediaRecorder(this.output, {
          ...(mimeType ? { mimeType } : {}),
          videoBitsPerSecond: 1500000,
        });
        this.recorder.ondataavailable = (event) => {
          if (event.data.size) this.chunks.push(event.data);
        };
        this.recorder.onerror = () => {
          this.failed = true;
          this.onError('録画できませんでした。会話は続けられます。');
        };
        this.recorder.start(1000);
      } else if (this.recorder.state === 'paused') this.recorder.resume();
      this.onStatus('自分のカメラを録画中');
    } catch {
      if (!this.closed && generation === this.generation) {
        this.failed = true;
        this.onError('録画できませんでした。会話は続けられます。');
      }
    }
  }
  finish(): Promise<Blob | null> {
    if (this.finishing) return this.finishing;
    this.closed = true;
    this.generation++;
    const recorder = this.recorder;
    this.finishing = new Promise((resolve) => {
      const complete = () => {
        clearInterval(this.timer);
        this.video?.pause();
        if (this.video) this.video.srcObject = null;
        this.output?.getTracks().forEach((track) => track.stop());
        const blob = this.chunks.length
          ? new Blob(this.chunks, { type: recorder?.mimeType || 'video/webm' })
          : null;
        this.chunks = [];
        resolve(blob);
      };
      if (recorder && recorder.state !== 'inactive') {
        recorder.onstop = complete;
        recorder.stop();
      } else complete();
    });
    return this.finishing;
  }
  async save(room: string) {
    const blob = await this.finish();
    if (this.saved || !blob?.size) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kotoba-${room}-${new Date().toISOString().replace(/[:.]/g, '-')}.${blob.type.includes('mp4') ? 'mp4' : 'webm'}`;
    document.body.append(link);
    link.click();
    link.remove();
    this.saved = true;
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    this.onStatus('録画を保存しました');
  }
}
