import type { PlaybackMode, PublicConfig, Utterance } from '../types/protocol';
type ReadingItem = { text: string; key: string; id: string | null };
export class SpeechOutput {
  enabled = true;
  speaking = false;
  private mode: PlaybackMode = 'original';
  private queue: ReadingItem[] = [];
  private seen = new Set<string>();
  private spoken = new Set<string>();
  private revisions = new Map<string, number>();
  private actuallyRead = new Set<string>();
  private pausedForSpeech = false;
  private backlog: ReadingItem[] = [];
  private generation = 0;
  private current: ReadingItem | null = null;
  private started = false;
  constructor(
    private self: string,
    private config: PublicConfig['output'],
    private onStatus: (text: string) => void,
    private onReading: (id: string | null) => void = () => {},
  ) {}
  setMode(mode: PlaybackMode) {
    this.cancel();
    this.mode = mode;
    this.enabled = mode !== 'captions';
  }
  voices() {
    return 'speechSynthesis' in window
      ? speechSynthesis.getVoices().filter((v) => v.lang.startsWith(this.config.tts_lang.split('-')[0]))
      : [];
  }
  available() {
    return this.voices().length > 0;
  }
  async prepare() {
    if (this.available() || !('speechSynthesis' in window)) return this.available();
    return new Promise<boolean>((resolve) => {
      const finish = () => {
        clearTimeout(timer);
        speechSynthesis.removeEventListener('voiceschanged', changed);
        resolve(this.available());
      };
      const changed = () => {
        if (this.available()) finish();
      };
      const timer = setTimeout(finish, 2000);
      speechSynthesis.addEventListener('voiceschanged', changed);
    });
  }
  utterance(u: Utterance, eventId: string, correction = false) {
    if (u.replayed || u.participant_id === this.self || this.seen.has(eventId)) return;
    this.seen.add(eventId);
    if (this.seen.size > 2000) this.seen.delete(this.seen.values().next().value!);
    if ((this.revisions.get(u.utterance_id) ?? 0) >= u.revision) return;
    this.revisions.set(u.utterance_id, u.revision);
    if (this.revisions.size > 2000) this.revisions.delete(this.revisions.keys().next().value!);
    if (!this.enabled || (this.mode === 'original' && u.source === 'speech' && !correction)) return;
    if (correction) {
      this.queue = this.queue.filter((item) => item.id !== u.utterance_id);
      this.backlog = this.backlog.filter((item) => item.id !== u.utterance_id);
      if (this.current?.id === u.utterance_id) this.stopCurrent();
    }
    const sayCorrection =
      correction &&
      ((this.mode === 'original' && u.source === 'speech') || this.actuallyRead.has(u.utterance_id));
    this.speak(
      `${sayCorrection ? '訂正。' : ''}${u.display_name}。${u.text}`,
      `${u.utterance_id}:${u.revision}`,
      u.utterance_id,
    );
  }
  speak(text: string, key: string = crypto.randomUUID(), id: string | null = null) {
    if (!this.enabled || this.spoken.has(key)) return;
    if (!this.available()) {
      this.onStatus('日本語の読み上げ音声がありません。文字表示をご利用ください');
      return;
    }
    this.spoken.add(key);
    if (this.spoken.size > 2000) this.spoken.delete(this.spoken.values().next().value!);
    const item = { text, key, id };
    if (this.queue.length >= this.config.tts_queue_limit || this.backlog.length) {
      this.backlog.push(item);
      this.backlog = this.backlog.slice(-100);
      this.onStatus('未読があります。「未読を再生」を押してください');
      return;
    }
    this.queue.push(item);
    this.next();
  }
  private next() {
    if (this.speaking || this.pausedForSpeech || !this.enabled || !this.queue.length) return;
    const item = this.queue.shift()!;
    const generation = ++this.generation;
    this.current = item;
    this.started = false;
    const u = new SpeechSynthesisUtterance(item.text);
    u.lang = this.config.tts_lang;
    u.rate = this.config.tts_rate;
    u.voice = this.voices()[0] ?? null;
    this.speaking = true;
    u.onstart = () => {
      if (generation !== this.generation) return;
      this.started = true;
      if (item.id) {
        this.actuallyRead.add(item.id);
        if (this.actuallyRead.size > 2000) this.actuallyRead.delete(this.actuallyRead.values().next().value!);
      }
      this.onReading(this.pausedForSpeech ? null : item.id);
      this.onStatus(this.pausedForSpeech ? '読み上げ一時停止中' : '読み上げ中');
    };
    u.onend = () => {
      if (generation !== this.generation) return;
      this.current = null;
      this.started = false;
      this.speaking = false;
      this.onReading(null);
      this.onStatus('待機中');
      this.next();
    };
    const failed = () => {
      if (generation !== this.generation) return;
      this.backlog = [item, ...this.queue, ...this.backlog].slice(0, 100);
      this.queue = [];
      this.stopCurrent();
      this.onStatus('音声を再生できません。「音声を開始」を押してください');
    };
    u.onerror = failed;
    try {
      speechSynthesis.speak(u);
    } catch {
      failed();
    }
  }
  pauseWhileSpeaking(active: boolean) {
    this.pausedForSpeech = this.mode === 'original' && active;
    if ('speechSynthesis' in window) {
      if (this.pausedForSpeech) speechSynthesis.pause();
      else speechSynthesis.resume();
    }
    if (this.current && this.started) {
      this.onReading(this.pausedForSpeech ? null : this.current.id);
      this.onStatus(this.pausedForSpeech ? '読み上げ一時停止中' : '読み上げ中');
    }
    if (!this.pausedForSpeech) this.next();
  }
  replayUnread() {
    if (!this.enabled) return;
    this.queue.push(...this.backlog.splice(0, Math.max(0, this.config.tts_queue_limit - this.queue.length)));
    this.next();
  }
  private stopCurrent() {
    this.generation++;
    this.current = null;
    this.started = false;
    this.speaking = false;
    this.onReading(null);
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  }
  cancel() {
    this.queue = [];
    this.backlog = [];
    this.pausedForSpeech = false;
    this.stopCurrent();
    if ('speechSynthesis' in window) speechSynthesis.resume();
    this.onStatus('停止');
  }
}
