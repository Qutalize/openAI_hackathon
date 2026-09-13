import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  Candidate,
  InputKind,
  PlaybackMode,
  Participant,
  PublicConfig,
  ServerEvent,
  Session,
  Snapshot,
  StreamInfo,
  Utterance,
} from '../types/protocol';
import { api } from '../services/api';
import { ControlSocket } from '../services/controlSocket';
import { MediaSocket } from '../services/mediaSocket';
import { Peers } from '../services/peers';
import { AudioCapture } from '../services/audioCapture';
import { VisionCapture } from '../services/visionCapture';
import { SpeechOutput } from '../services/speechOutput';
import { useDevices } from './useDevices';
import { LocalRecording } from '../services/localRecording';
import { initialPlayback, outputPreferences } from '../services/playback';

export function useConversation(config: PublicConfig, session: Session, onLeave: (message: string) => void) {
  const [error, setError] = useState(''),
    [state, setState] = useState('setup'),
    [started, setStarted] = useState(false);
  const [participants, setParticipants] = useState<Participant[]>([]),
    [utterances, setUtterances] = useState<Utterance[]>([]);
  const [remoteStreams, setRemoteStreams] = useState<Record<string, MediaStream>>({}),
    [speaker, setSpeaker] = useState<string | null>(null);
  const [input, setInput] = useState<InputKind>(session.input);
  const [playback, setPlayback] = useState<PlaybackMode>(() => initialPlayback(session.mode));
  const [readingId, setReadingId] = useState<string | null>(null);
  const [recognition, setRecognition] = useState('待機中');
  const [displayName, setDisplayName] = useState(session.display_name);
  const [recordingStatus, setRecordingStatus] = useState('録画待機');
  const [ttsStatus, setTtsStatus] = useState('待機中'),
    [candidate, setCandidate] = useState<Candidate | null>(null);
  const [capturing, setCapturing] = useState(false),
    [processing, setProcessing] = useState(false),
    [operating, setOperating] = useState(false);
  const [avatars, setAvatars] = useState<Record<string, string>>({
    [session.participant_id]: session.avatar ?? '',
  });
  const devices = useDevices(config, setError);
  const refs = useRef({
    control: null as ControlSocket | null,
    media: null as MediaSocket | null,
    peers: null as Peers | null,
    audio: new AudioCapture(),
    vision: new VisionCapture(),
    tts: null as SpeechOutput | null,
    participants: [] as Participant[],
    input: session.input,
    playback,
    segment: null as string | null,
    captureGeneration: 0,
    frames: 0,
    captureTimer: undefined as ReturnType<typeof setTimeout> | undefined,
    iceTimer: undefined as ReturnType<typeof setTimeout> | undefined,
    closed: false,
    signals: [] as ServerEvent[],
    seen: new Set<string>(),
    speechNotifications: session.mode === 'vision_support',
    recording: null as LocalRecording | null,
  });
  const r = refs.current;
  if (!r.tts) r.tts = new SpeechOutput(session.participant_id, config.output, setTtsStatus, setReadingId);
  useEffect(() => {
    r.tts!.setMode(r.playback);
  }, [r]);
  if (!r.recording) r.recording = new LocalRecording(setRecordingStatus, setError);
  useEffect(() => {
    if (started) void r.recording?.update(devices.stream);
  }, [started, devices.stream, r]);
  useEffect(() => {
    if (!started) return;
    const warn = (event: BeforeUnloadEvent) => {
      if (r.recording?.hasUnsavedRecording) {
        event.preventDefault();
        event.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [started, r]);
  const setStream = useCallback(
    (info: StreamInfo) => {
      r.media?.reset(info);
      r.input = info.input;
      setInput(info.input);
    },
    [r],
  );
  const stopCapture = useCallback(() => {
    r.captureGeneration++;
    clearTimeout(r.captureTimer);
    r.vision.stop();
    r.segment = null;
    setCapturing(false);
  }, [r]);
  const stopResources = useCallback(() => {
    r.closed = true;
    r.control?.close();
    r.media?.close();
    r.peers?.close();
    void r.audio.stop();
    r.vision.stop();
    r.tts?.cancel();
    void r.recording?.finish();
    clearTimeout(r.captureTimer);
    clearTimeout(r.iceTimer);
    devices.streamRef.current.getTracks().forEach((t) => t.stop());
  }, [r, devices.streamRef]);
  useEffect(() => () => stopResources(), [stopResources]);

  async function startAudio() {
    await r.audio.stop();
    if (
      r.input === 'speech' &&
      devices.streamRef.current.getAudioTracks().length &&
      r.media?.socket?.readyState === WebSocket.OPEN
    ) {
      await r.audio.start(devices.streamRef.current, (buffer) => {
        try {
          r.media?.send('audio.pcm', buffer);
        } catch (e) {
          setError((e as Error).message);
          void r.audio.stop();
          void cancelRecognition();
        }
      });
    }
  }
  async function updateDevices() {
    const local = devices.streamRef.current;
    const info = await r.control!.request<StreamInfo>('device.update', {
      microphone: local.getAudioTracks().some((t) => t.readyState === 'live'),
      camera: local.getVideoTracks().some((t) => t.readyState === 'live'),
    });
    setStream(info);
    await r.peers?.updateLocal(local);
    await startAudio();
  }
  useEffect(() => {
    if (!started || state !== 'connected' || operating) return;
    const me = participants.find((p) => p.id === session.participant_id);
    const microphone = devices.stream.getAudioTracks().some((t) => t.readyState === 'live');
    const camera = devices.stream.getVideoTracks().some((t) => t.readyState === 'live');
    if (me && (me.devices.microphone !== microphone || me.devices.camera !== camera))
      void updateDevices().catch((e) => setError(e.message));
  }, [devices.stream, participants, started, state, operating]);
  async function refreshIce() {
    const ice = await api<RTCConfiguration & { expires_at: number | null }>('/api/rtc-config');
    r.peers?.updateConfig(ice);
    if (ice.expires_at && !r.closed)
      r.iceTimer = setTimeout(
        () => {
          refreshIce().catch(() => setError('通話接続設定の更新に失敗しました'));
        },
        Math.max(10000, ice.expires_at * 1000 - Date.now() - 60000),
      );
    return ice;
  }
  function onEvent(e: ServerEvent) {
    if (e.event_id) {
      if (r.seen.has(e.event_id)) return;
      r.seen.add(e.event_id);
      if (r.seen.size > 2000) r.seen.delete(r.seen.values().next().value!);
    }
    const p = e.payload;
    if (e.type === 'room.snapshot') {
      const snap = p as Snapshot;
      r.participants = snap.participants;
      r.tts?.pauseWhileSpeaking(
        snap.participants.some((p) => p.speaking && p.connection_state === 'connected'),
      );
      setParticipants(snap.participants);
      setAvatars({
        ...snap.avatars,
        ...Object.fromEntries(snap.participants.map((p) => [p.id, p.avatar ?? ''])),
      });
      setUtterances(snap.utterances);
      setDisplayName(snap.self.display_name);
      setSpeaker(snap.speaker_id);
      for (const part of snap.participants)
        if (part.id !== session.participant_id && part.connection_state === 'connected')
          r.peers?.ensure(part.id);
    } else if (e.type === 'participant.activity') {
      if (p.replayed) return;
      r.participants = r.participants.map((part) =>
        part.id === p.id ? { ...part, speaking: p.speaking, recognizing: p.recognizing } : part,
      );
      setParticipants([...r.participants]);
      r.tts?.pauseWhileSpeaking(
        r.participants.some((part) => part.speaking && part.connection_state === 'connected'),
      );
    } else if (e.type === 'participant.joined' || e.type === 'participant.updated') {
      const exists = r.participants.some((x) => x.id === p.id);
      r.participants = exists ? r.participants.map((x) => (x.id === p.id ? p : x)) : [...r.participants, p];
      setParticipants([...r.participants]);
      r.tts?.pauseWhileSpeaking(
        r.participants.some((part) => part.speaking && part.connection_state === 'connected'),
      );
      setAvatars((old) => ({ ...old, [p.id]: p.avatar ?? '' }));
      if (p.id === session.participant_id) setDisplayName(p.display_name);
      setUtterances((list) =>
        list.map((u) => (u.participant_id === p.id ? { ...u, display_name: p.display_name } : u)),
      );
      if (p.id !== session.participant_id && p.connection_state === 'connected') r.peers?.ensure(p.id);
      if (p.connection_state !== 'connected') r.peers?.remove(p.id);
      if (!exists && p.id !== session.participant_id && r.speechNotifications && !p.replayed)
        r.tts?.speak(`${p.display_name}が参加しました`);
    } else if (e.type === 'participant.left') {
      r.participants = r.participants.filter((x) => x.id !== p.participant_id);
      setParticipants([...r.participants]);
      r.peers?.remove(p.participant_id);
      r.tts?.pauseWhileSpeaking(
        r.participants.some((part) => part.speaking && part.connection_state === 'connected'),
      );
      if (r.speechNotifications && !p.replayed) r.tts?.speak(`${p.display_name}が退出しました`);
    } else if (e.type.startsWith('rtc.')) {
      if (r.peers) void r.peers.receive(e.type, p);
      else r.signals.push(e);
    } else if (e.type === 'utterance.final' || e.type === 'utterance.corrected') {
      setUtterances((list) => {
        const existing = list.find((x) => x.utterance_id === p.utterance_id);
        if (existing && existing.revision >= p.revision) return list;
        return (existing ? list.map((x) => (x.utterance_id === p.utterance_id ? p : x)) : [...list, p]).slice(
          -500,
        );
      });
      r.tts?.utterance(p, e.event_id!, e.type === 'utterance.corrected');
    } else if (e.type === 'speaker.changed') {
      setSpeaker(p.participant_id);
    } else if (e.type === 'recognition.candidate') {
      setCandidate(p);
      setProcessing(false);
      setRecognition(p.message);
    } else if (e.type === 'recognition.state') {
      setProcessing(p.state === 'processing');
      setRecognition(p.message ?? (p.state === 'processing' ? '認識しています' : '待機中'));
      if (p.stream_id) {
        setStream(p);
        void r.audio.stop();
        stopCapture();
      }
    } else if (e.type === 'recognition.busy') {
      setError(p.message);
      setProcessing(false);
      setRecognition('混雑しています');
    }
  }
  async function startConversation(textFallback = false) {
    if (operating) return;
    setOperating(true);
    setError('');
    try {
      if (textFallback) {
        r.input = 'text';
        setInput('text');
        await devices.update('audio', false);
        r.speechNotifications = false;
        setPlayback('captions');
        r.playback = 'captions';
      }
      r.tts!.setMode(r.playback);
      if (r.playback !== 'captions' && !(await r.tts!.prepare()))
        setTtsStatus('日本語の読み上げ音声がありません。文字表示をご利用ください');
      if (r.input === 'speech' && !devices.streamRef.current.getAudioTracks().length)
        throw new Error('発声入力にはマイクが必要です。マイクをONにするか文字入力で参加してください');
      if (['lipread', 'sign'].includes(r.input) && !devices.streamRef.current.getVideoTracks().length)
        throw new Error('選択した入力にはカメラが必要です');
      r.closed = false;
      if (r.speechNotifications) r.tts!.speak('会話に参加します');
      const control = (r.control = new ControlSocket(
        session.room_id,
        onEvent,
        (s) => {
          setState(s);
          if (s === 'reconnecting' || s === 'expired') {
            r.participants = r.participants.map((part) => ({ ...part, speaking: false, recognizing: false }));
            setParticipants([...r.participants]);
            r.tts?.cancel();
            r.media?.close();
            void r.audio.stop();
            stopCapture();
            setProcessing(false);
            if (r.speechNotifications) r.tts?.speak('接続が切れました。再接続しています');
          }
        },
        async () => {
          r.media?.close();
          r.peers?.close();
          const media = (r.media = new MediaSocket(session.room_id, () => {
            if (!r.closed) {
              setError('認識接続が切れました。再接続します');
              r.control?.socket?.close();
            }
          }));
          await media.connect();
          setStream(await control.request<StreamInfo>('input.update', { input: r.input }));
          const ice = await refreshIce();
          r.peers = new Peers(
            session.participant_id,
            ice,
            (t, p) => control.request(t, p),
            (id, stream) =>
              setRemoteStreams((old) => {
                const next = { ...old };
                if (stream) next[id] = stream;
                else delete next[id];
                return next;
              }),
            setError,
            devices.streamRef.current,
          );
          for (const p of r.participants)
            if (p.id !== session.participant_id && p.connection_state === 'connected') r.peers.ensure(p.id);
          for (const e of r.signals.splice(0)) await r.peers.receive(e.type, e.payload);
          await updateDevices();
          await control.request('preferences.update', { output: outputPreferences(r.playback) });
        },
        config.heartbeat_seconds,
        config.reconnect_grace_seconds,
      ));
      setStarted(true);
      control.connect();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOperating(false);
    }
  }
  async function toggleDevice(kind: 'audio' | 'video') {
    setError('');
    setOperating(true);
    stopCapture();
    await r.audio.stop();
    try {
      const enabled = !devices.streamRef.current
        .getTracks()
        .some((t) => t.kind === kind && t.readyState === 'live');
      await devices.update(kind, enabled);
      if (started) await updateDevices();
    } catch (e) {
      setError((e as Error).message);
      if (started) await updateDevices().catch(() => {});
    } finally {
      setOperating(false);
    }
  }
  async function changeInput(selected: InputKind) {
    setOperating(true);
    setError('');
    stopCapture();
    await r.audio.stop();
    setCandidate(null);
    setProcessing(false);
    try {
      if (selected !== 'speech') await devices.update('audio', false);
      if (started) {
        setStream(await r.control!.request('input.update', { input: selected }));
        await updateDevices();
      } else {
        r.input = selected;
        setInput(selected);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOperating(false);
    }
  }
  async function changeOutput(next: PlaybackMode) {
    r.playback = next;
    setPlayback(next);
    r.tts!.setMode(next);
    r.tts!.pauseWhileSpeaking(
      r.participants.some((part) => part.speaking && part.connection_state === 'connected'),
    );
    document.querySelectorAll('audio').forEach((a) => {
      a.muted = next !== 'original';
      if (next !== 'original') a.pause();
    });
    try {
      localStorage.setItem('playback-' + session.mode, next);
    } catch {
      /* Optional storage. */
    }
    if (started)
      await r
        .control!.request('preferences.update', { output: outputPreferences(next) })
        .catch((e) => setError(e.message));
  }
  async function endCapture() {
    const id = r.segment;
    if (!id) return;
    stopCapture();
    setProcessing(true);
    try {
      await r.control!.request('segment.end', { segment_id: id, last_media_seq: r.media!.seq });
    } catch (e) {
      setError((e as Error).message);
      setProcessing(false);
    }
  }
  async function beginCapture() {
    const generation = ++r.captureGeneration;
    setError('');
    setProcessing(true);
    setCandidate(null);
    r.frames = 0;
    try {
      if (!devices.streamRef.current.getVideoTracks().length) throw new Error('カメラをONにしてください');
      if (r.input !== 'lipread' && r.input !== 'sign') return;
      const kind = r.input,
        max = config.recognition[kind].max_frames;
      await r.vision.start(
        devices.streamRef.current,
        kind,
        (features, timestamp) => {
          if (!r.segment) return;
          try {
            const floats = new Float32Array(features.flat());
            r.media?.send(
              'vision.features',
              floats.buffer,
              {
                segment_id: r.segment,
                schema: kind === 'lipread' ? 'lip40_v1' : 'sign100_v1',
                shape: [1, features.length, 4],
                frame_timestamps_ms: [timestamp],
              },
              timestamp,
            );
            if (++r.frames >= max) void endCapture();
          } catch (e) {
            setError((e as Error).message);
            void cancelRecognition();
          }
        },
        setError,
      );
      const id = crypto.randomUUID();
      if (generation !== r.captureGeneration || r.closed) return;
      await r.control!.request('segment.start', { segment_id: id });
      if (generation !== r.captureGeneration || r.closed) return;
      r.segment = id;
      setCapturing(true);
      setProcessing(false);
      setRecognition('撮影中。終わったら終了ボタンを押してください');
      r.captureTimer = setTimeout(() => void endCapture(), max * 50);
    } catch (e) {
      if (generation === r.captureGeneration) {
        stopCapture();
        setProcessing(false);
        setError((e as Error).message);
      }
    }
  }
  async function cancelRecognition() {
    stopCapture();
    setProcessing(false);
    setCandidate(null);
    await r.audio.stop();
    try {
      if (r.control?.socket?.readyState === WebSocket.OPEN)
        setStream(await r.control.request('segment.cancel', {}));
    } catch {}
    setRecognition('取消しました');
  }
  async function submit(text: string, candidateId?: string) {
    try {
      await r.control!.request('utterance.submit', {
        text,
        ...(candidateId ? { candidate_id: candidateId } : {}),
      });
      setCandidate(null);
    } catch (e) {
      setError((e as Error).message);
      throw e;
    }
  }
  async function correct(u: Utterance, text: string) {
    try {
      await r.control!.request('utterance.correct', {
        utterance_id: u.utterance_id,
        revision: u.revision,
        text,
      });
    } catch (e) {
      setError((e as Error).message);
      throw e;
    }
  }
  async function leave() {
    setOperating(true);
    try {
      await r.recording?.save(session.room_id);
    } catch {
      setError('録画を保存できませんでした');
      setOperating(false);
      return;
    }
    stopResources();
    devices.stop();
    try {
      await api('/api/session', { method: 'DELETE', headers: { 'X-CSRF-Token': session.csrf_token } });
      onLeave('会話から退出しました');
    } catch {
      onLeave('デバイスを停止しました。接続終了後60秒で参加枠が解放されます。');
    }
  }
  async function rename(name: string) {
    try {
      const result = await api<{ display_name: string }>('/api/session', {
        method: 'PATCH',
        headers: { 'X-CSRF-Token': session.csrf_token },
        body: JSON.stringify({ display_name: name }),
      });
      setDisplayName(result.display_name);
      try {
        localStorage.setItem('display-name', result.display_name);
      } catch {
        /* Optional preference storage. */
      }
    } catch (error) {
      setError((error as Error).message);
      throw error;
    }
  }
  return {
    error,
    setError,
    state,
    started,
    participants,
    utterances,
    speaker,
    input,
    playback,
    readingId,
    displayName,
    rename,
    recordingStatus,
    recognition,
    ttsStatus,
    candidate,
    capturing,
    processing,
    operating,
    devices,
    streams: { ...remoteStreams, [session.participant_id]: devices.stream },
    startConversation,
    toggleDevice,
    changeInput,
    changeOutput,
    beginCapture,
    endCapture,
    cancelRecognition,
    submit,
    correct,
    leave,
    avatars,
    stopSpeech: () => r.tts!.cancel(),
    replayUnread: () => r.tts!.replayUnread(),
    startSound: async () => {
      const requested = r.playback;
      if (requested === 'captions') return;
      void r.audio.resume();
      if (requested === 'original')
        document.querySelectorAll('audio').forEach((a) => {
          if (!a.muted) void a.play().catch(() => setError('音声再生を開始できません'));
        });
      const available = await r.tts!.prepare();
      if (r.playback !== requested || r.closed) return;
      if (!available) {
        setTtsStatus('日本語の読み上げ音声がありません。文字表示をご利用ください');
        return;
      }
      r.tts!.replayUnread();
      r.tts!.speak('音声の準備ができました');
    },
  };
}
export type Conversation = ReturnType<typeof useConversation>;
