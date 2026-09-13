export type InputKind = 'speech' | 'lipread' | 'sign' | 'text';
export type Mode = 'standard' | 'vision_support' | 'hearing_support';
export type OutputKind = 'audio' | 'text';
export type PlaybackMode = 'captions' | 'ai' | 'original';
export const playbackNames: Record<PlaybackMode, string> = {
  captions: '字幕のみ',
  ai: '字幕＋AI読み上げ',
  original: '字幕＋通常音声',
};
export const inputNames: Record<InputKind, string> = {
  speech: '発声',
  lipread: '読唇',
  sign: '手話',
  text: '文字入力',
};
export const modeNames: Record<Mode, string> = {
  standard: '標準モード',
  vision_support: '視覚サポート',
  hearing_support: '聴覚サポート',
};
export interface StreamInfo {
  input: InputKind;
  input_epoch: number;
  stream_id: string;
}
export interface Session extends StreamInfo {
  avatar?: string;
  participant_id: string;
  display_name: string;
  room_id: string;
  mode: Mode;
  csrf_token: string;
  expires_at: number;
}
export interface Participant {
  speaking?: boolean;
  recognizing?: boolean;
  avatar?: string;
  id: string;
  display_name: string;
  mode: Mode;
  input: InputKind;
  devices: { microphone: boolean; camera: boolean };
  connection_state: string;
}
export interface Utterance {
  utterance_id: string;
  participant_id: string;
  display_name: string;
  revision: number;
  source: InputKind;
  text: string;
  created_at: string;
  replayed?: boolean;
}
export interface Snapshot {
  avatars?: Record<string, string>;
  participants: Participant[];
  utterances: Utterance[];
  last_server_seq: number;
  speaker_id: string | null;
  self: Participant & StreamInfo & { output: OutputKind[] };
}
export interface PublicConfig {
  name: string;
  locale: string;
  modes: Record<
    Mode,
    {
      input: InputKind;
      allowed_inputs: InputKind[];
      output: OutputKind[];
      camera_on: boolean;
      microphone_on: boolean;
      layout: string;
    }
  >;
  capabilities: Record<
    'speech' | 'lipread' | 'sign',
    { available: boolean; reason: string; vocabulary: { id: string; text: string }[] }
  >;
  media: {
    video_width: number;
    video_height: number;
    video_fps: number;
    echo_cancellation: boolean;
    noise_suppression: boolean;
    vision_fps: number;
  };
  output: { tts_lang: string; tts_rate: number; tts_queue_limit: number };
  max_text_chars: number;
  heartbeat_seconds: number;
  reconnect_grace_seconds: number;
  recognition: { lipread: { max_frames: number }; sign: { max_frames: number } };
}
export interface ServerEvent {
  version: number;
  type: string;
  request_id?: string;
  event_id?: string;
  server_seq?: number;
  payload: any;
}
export interface Candidate {
  candidate_id: string;
  candidates: { label: string; text: string }[];
  input: InputKind;
  message: string;
  expires_in: number;
}
