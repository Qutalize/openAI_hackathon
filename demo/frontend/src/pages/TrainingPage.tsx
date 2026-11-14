import { useEffect, useRef, useState } from 'react';
import { VisionCapture } from '../services/visionCapture';
import { api } from '../services/api';
import Video from '../components/Video';
import { LanguageSelect, useI18n } from '../i18n';

type Kind = 'lipread' | 'sign';
type Phrase = { id: string; text: string };
type Status = Record<Kind, { labels: Record<string, number>; subjects: number; vocabulary: Phrase[] }>;

const DURATION = { lipread: 3200, sign: 4800 };
const MAX_FRAMES = { lipread: 64, sign: 96 };
const COUNTDOWN = 3;
const UNKNOWN_HINT = {
  lipread: '対象外の動き：語彙にない言葉を話すか、口を閉じたままにしてください',
  sign: '対象外の動き：手を下ろす、頭をかくなど、語彙にない動きをしてください',
};
const CODE_KEY = 'kotoba-training-code';

function readCode() {
  try {
    return localStorage.getItem(CODE_KEY) ?? '';
  } catch {
    return '';
  }
}

function shuffle<T>(items: T[]) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function TrainingPage() {
  const { t } = useI18n();
  const [kind, setKind] = useState<Kind>('lipread'),
    [subject, setSubject] = useState(''),
    [code, setCode] = useState(readCode),
    [repetitions, setRepetitions] = useState(5),
    [consent, setConsent] = useState(false),
    [stream, setStream] = useState<MediaStream>(),
    [status, setStatus] = useState(''),
    [counts, setCounts] = useState<Status>(),
    [running, setRunning] = useState(false),
    [prompt, setPrompt] = useState<{
      text: string;
      hint?: string;
      phase: string;
      done: number;
      total: number;
    }>(),
    [confirmDelete, setConfirmDelete] = useState(false);
  const refs = useRef({
    vision: new VisionCapture(),
    stream: undefined as MediaStream | undefined,
    frames: [] as number[][][],
    times: [] as number[],
    recording: false,
    cancelled: false,
  });
  const r = refs.current;
  useEffect(
    () => () => {
      r.cancelled = true;
      r.vision.stop();
      r.stream?.getTracks().forEach((track) => track.stop());
    },
    [r],
  );
  const headers = { 'X-Training-Code': code };
  const vocabulary = counts?.[kind].vocabulary ?? [];
  const subjectValid = /^[a-zA-Z0-9_-]{2,40}$/.test(subject);

  async function refresh() {
    if (!code || !subjectValid) return;
    try {
      setCounts(
        await api<Status>(`/api/training/status?subject=${encodeURIComponent(subject)}`, { headers }),
      );
      try {
        localStorage.setItem(CODE_KEY, code);
      } catch {
        // Remembering the code is only a convenience.
      }
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  async function prepare() {
    try {
      r.stream?.getTracks().forEach((track) => track.stop());
      r.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: false,
      });
      setStream(r.stream);
      setStatus('カメラを準備しました');
      await refresh();
    } catch {
      setStatus('カメラを利用できません。権限を確認してください');
    }
  }

  function stopAll(message: string) {
    r.cancelled = true;
    r.recording = false;
    r.vision.stop();
    setRunning(false);
    setPrompt(undefined);
    setStatus(message);
  }

  async function record(): Promise<{ frames: number[][][]; times: number[] }> {
    r.frames = [];
    r.times = [];
    r.recording = true;
    const started = Date.now();
    while (r.recording && !r.cancelled && Date.now() - started < DURATION[kind]) {
      if (r.frames.length >= MAX_FRAMES[kind]) break;
      await wait(50);
    }
    r.recording = false;
    return { frames: r.frames, times: r.times };
  }

  async function upload(label: string, frames: number[][][], times: number[]) {
    return api<{ valid_ratio: number }>('/api/training/samples', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        version: 1,
        subject_id: subject,
        label,
        modality: kind,
        consent: true,
        created_at: new Date().toISOString(),
        preprocessing_version: 'landmarks-v1',
        mediapipe_version: '0.10.32',
        frames,
        timestamps: times,
      }),
    });
  }

  async function run() {
    if (!r.stream || !vocabulary.length) return;
    r.cancelled = false;
    setRunning(true);
    setStatus('特徴点モデルを準備しています');
    try {
      await r.vision.start(
        r.stream,
        kind,
        (features, timestamp) => {
          if (!r.recording) return;
          r.frames.push(features);
          r.times.push(timestamp);
        },
        setStatus,
      );
    } catch (e) {
      stopAll((e as Error).message);
      return;
    }
    const phrases: Phrase[] = [...vocabulary, { id: 'unknown', text: '（対象外の動き）' }];
    const queue = Array.from({ length: repetitions }, () => shuffle(phrases)).flat();
    let done = 0;
    for (const phrase of queue) {
      let saved = false;
      for (let attempt = 0; attempt < 3 && !saved && !r.cancelled; attempt++) {
        const hint = phrase.id === 'unknown' ? UNKNOWN_HINT[kind] : undefined;
        for (let n = COUNTDOWN; n > 0 && !r.cancelled; n--) {
          setPrompt({ text: phrase.text, hint, phase: `${n}`, done, total: queue.length });
          await wait(700);
        }
        if (r.cancelled) break;
        setPrompt({ text: phrase.text, hint, phase: '撮影中', done, total: queue.length });
        const { frames, times } = await record();
        if (r.cancelled) break;
        try {
          if (frames.length < 10) throw new Error('顔や手が映っていません。カメラの位置を確認してください');
          await upload(phrase.id, frames, times);
          saved = true;
          setStatus('');
        } catch (e) {
          setStatus((e as Error).message);
          const code = (e as { status?: number }).status;
          if (code === 403 || code === 404 || code === 429) {
            stopAll((e as Error).message);
            return;
          }
        }
      }
      if (r.cancelled) return;
      done++;
      if (done % phrases.length === 0) void refresh();
    }
    r.vision.stop();
    setRunning(false);
    setPrompt(undefined);
    setStatus(`${done}件を保存しました。ご協力ありがとうございます`);
    void refresh();
  }

  async function deleteMine() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setConfirmDelete(false);
    try {
      await api(`/api/training/subjects/${encodeURIComponent(subject)}`, { method: 'DELETE', headers });
      setStatus('この人物IDの収録をすべて削除しました');
      void refresh();
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  const mine = counts?.[kind].labels ?? {};
  return (
    <main className="device-setup">
      <div className="page-language">
        <LanguageSelect />
      </div>
      <p className="eyebrow">{t('学習データ収集 · 会話とは別の操作です')}</p>
      <h1>{t('日本語の読唇・手話の学習データを集める')}</h1>
      <p>
        {t(
          '画面に出る表現を、合図に合わせて1回ずつ行ってください。映像は送信しません。顔・手・姿勢の特徴点だけを、本人の同意がある場合にサーバーへ保存します。',
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <div className="training-fields">
          <label>
            {t('入力方式')}
            <select value={kind} disabled={running} onChange={(e) => setKind(e.target.value as Kind)}>
              <option value="lipread">{t('読唇（声を出さずに口を動かす）')}</option>
              <option value="sign">{t('日本手話')}</option>
            </select>
          </label>
          <label>
            {t('人物ID（氏名を使用しない）')}
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              onBlur={() => void refresh()}
              pattern={'[a-zA-Z0-9_\\-]{2,40}'}
              placeholder="person01"
              required
              disabled={running}
            />
          </label>
          <label>
            {t('収集コード')}
            <input
              type="password"
              value={code}
              autoComplete="off"
              onChange={(e) => setCode(e.target.value)}
              onBlur={() => void refresh()}
              required
              disabled={running}
            />
          </label>
          <label>
            {t('1表現あたりの回数')}
            <select
              value={repetitions}
              disabled={running}
              onChange={(e) => setRepetitions(Number(e.target.value))}
            >
              {[1, 3, 5, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="setting-check">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => {
              setConsent(e.target.checked);
              if (!e.target.checked) {
                stopAll('収集を停止しました');
                r.stream?.getTracks().forEach((track) => track.stop());
                r.stream = undefined;
                setStream(undefined);
              }
            }}
          />
          {t('本人が収集・モデル学習への使用に同意しています')}
        </label>
        {prompt && (
          <div className="training-prompt" aria-live="assertive">
            <span className="training-progress">
              {prompt.done + 1} / {prompt.total}
            </span>
            <strong>{t(prompt.text)}</strong>
            {prompt.hint && <small>{t(prompt.hint)}</small>}
            <span className={prompt.phase === '撮影中' ? 'training-phase recording' : 'training-phase'}>
              {t(prompt.phase)}
            </span>
          </div>
        )}
        <div className="setup-preview">
          {stream ? (
            <Video stream={stream} local label={t('学習データ収集のプレビュー')} />
          ) : (
            <p>{t('カメラ OFF')}</p>
          )}
        </div>
        <p role="status">{t(status)}</p>
        <div className="setup-buttons">
          <button
            type="button"
            className="secondary"
            disabled={!consent || running}
            onClick={() => void prepare()}
          >
            {t('カメラをON')}
          </button>
          <button
            className="primary"
            disabled={!consent || !stream || running || !subjectValid || !code || !vocabulary.length}
          >
            {t('連続撮影を開始')}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={!running}
            onClick={() => stopAll('中断しました')}
          >
            {t('中断')}
          </button>
        </div>
      </form>
      {counts && (
        <section className="training-counts" aria-label={t('収録数')}>
          <h2>
            {t('この人物IDの収録数')}（{t('全体で{n}人', { n: counts[kind].subjects })}）
          </h2>
          <ul>
            {[...vocabulary, { id: 'unknown', text: '対象外の動き' }].map((p) => (
              <li key={p.id}>
                <span>{t(p.text)}</span>
                <b>{mine[p.id] ?? 0}</b>
              </li>
            ))}
          </ul>
          <button type="button" className="secondary" disabled={running} onClick={() => void deleteMine()}>
            {confirmDelete ? t('もう一度押すと削除します') : t('この人物IDの収録を削除')}
          </button>
        </section>
      )}
      <a href="/">{t('会話の入室画面へ')}</a>
    </main>
  );
}
