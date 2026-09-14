/** Records only the local camera track for an isolated inference request. */
export class VideoClipCapture {
  private recorder?: MediaRecorder;
  private chunks: Blob[] = [];

  async start(stream: MediaStream) {
    this.cancel();
    if (!('MediaRecorder' in window)) throw new Error('このブラウザは動画認識に対応していません');
    const track = stream.getVideoTracks().find((item) => item.readyState === 'live');
    if (!track) throw new Error('カメラをONにしてください');
    const mimeType = ['video/webm;codecs=vp8', 'video/webm', 'video/mp4'].find((type) =>
      MediaRecorder.isTypeSupported(type),
    );
    const recorder = new MediaRecorder(new MediaStream([track]), {
      ...(mimeType ? { mimeType } : {}),
      videoBitsPerSecond: 1_500_000,
    });
    this.chunks = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size) this.chunks.push(event.data);
    };
    this.recorder = recorder;
    recorder.start(250);
  }

  finish() {
    const recorder = this.recorder;
    if (!recorder || recorder.state === 'inactive') return Promise.reject(new Error('撮影動画がありません'));
    return new Promise<Blob>((resolve, reject) => {
      recorder.onerror = () => reject(new Error('撮影動画を作成できませんでした'));
      recorder.onstop = () => {
        const type = recorder.mimeType.split(';', 1)[0] || 'video/webm';
        const video = new Blob(this.chunks, { type });
        this.recorder = undefined;
        this.chunks = [];
        if (!video.size) reject(new Error('撮影動画が空です'));
        else resolve(video);
      };
      recorder.stop();
    });
  }

  cancel() {
    if (this.recorder && this.recorder.state !== 'inactive') {
      this.recorder.ondataavailable = null;
      this.recorder.onstop = null;
      this.recorder.stop();
    }
    this.recorder = undefined;
    this.chunks = [];
  }
}
