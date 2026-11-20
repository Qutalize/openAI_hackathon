import { useEffect, useRef, useState } from 'react';
import { VisionCapture } from '../services/visionCapture';
import { api } from '../services/api';
import Video from '../components/Video';
import { drawLandmarks } from '../components/landmarkOverlay';
import { LanguageSelect, useI18n } from '../i18n';

type Kind = 'lipread' | 'sign';
// A video showing the phrase; start and end (seconds) frame the one clear, front-facing performance.
type Reference = { url: string; source: string; start?: number; end?: number };
type Phrase = { id: string; text: string; hint?: string; reference?: Reference };
type ModelInfo = {
  available: boolean;
  model_version?: string;
  method?: string;
  macro_f1_known?: number;
  unknown_false_accept_rate?: number;
  people?: number;
  recordings?: number;
};
type Run = {
  at: string;
  modality: Kind;
  version?: string;
  registered: boolean;
  accepted: boolean;
  people?: number;
  recordings?: number;
  macro_f1_known?: number;
  unknown_false_accept_rate?: number;
  failed: boolean;
};
type Status = Record<Kind, { labels: Record<string, number>; subjects: number; vocabulary: Phrase[] }> & {
  models?: Record<Kind, ModelInfo>;
  runs?: Run[];
};
// A muted player that plays the reference's segment once from its start.
function youtubeEmbed({ url, start, end }: Reference) {
  const id = new URL(url).searchParams.get('v') ?? url.match(/youtube\.com\/shorts\/([\w-]+)/)?.[1];
  if (!id) return undefined;
  const range = `${start != null ? `&start=${start}` : ''}${end != null ? `&end=${end}` : ''}`;
  return `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&playsinline=1&rel=0${range}`;
}
// How long the pre-recording example takes: the segment plus time for the player to load.
const EXAMPLE_LOAD_MS = 1500;
const exampleMs = (r: Reference) => (r.end != null ? (r.end - (r.start ?? 0)) * 1000 + EXAMPLE_LOAD_MS : 0);
const percent = (x?: number) => (x == null ? '—' : `${Math.round(x * 100)}%`);

const DURATION = { lipread: 3200, sign: 4800 };
const MAX_FRAMES = { lipread: 64, sign: 96 };
const COUNTDOWN = 3;
// "Other movements" vary far more than any phrase, so each round asks for three different kinds.
const UNKNOWN_HINTS = {
  lipread: [
    '語彙にない言葉を、声を出さずに口だけ動かしてください（例：おはよう、さようなら、自分の名前）',
    '口を閉じたまま、まばたきや首をかしげるなど、話す以外の動きをしてください',
    '笑う・あくびをする・唇をなめるなど、話す以外の口の動きをしてください',
  ],
  sign: [
    '腕を組む、胸の前で手を組むなど、手を画面に映したまま止めてください',
    '頭をかく、髪を触るなど、手話ではない手の動きをしてください',
    '語彙にない手話や身ぶりをしてください',
  ],
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
    [shown, setShown] = useState<string>(),
    [plays, setPlays] = useState(0),
    [playExample, setPlayExample] = useState(true),
    [showPoints, setShowPoints] = useState(false),
    [prompt, setPrompt] = useState<{
      id: string;
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
    // The landmark model currently running, so recording can reuse the one started for the overlay.
    visionKind: undefined as Kind | undefined,
  });
  const r = refs.current;
  const overlay = useRef<HTMLCanvasElement>(null);
  useEffect(
    () => () => {
      r.cancelled = true;
      r.vision.stop();
      r.stream?.getTracks().forEach((track) => track.stop());
    },
    [r],
  );

  async function startVision() {
    if (r.visionKind === kind) return;
    r.visionKind = undefined;
    await r.vision.start(
      r.stream!,
      kind,
      (features, timestamp) => {
        if (!r.recording) return;
        r.frames.push(features);
        r.times.push(timestamp);
      },
      setStatus,
    );
    r.visionKind = kind;
  }
  function stopVision() {
    r.vision.stop();
    r.visionKind = undefined;
  }

  // The overlay shows the landmarks that become features; outside recording it runs the model just for the preview.
  useEffect(() => {
    const canvas = overlay.current;
    r.vision.onPoints = showPoints && canvas ? (points) => drawLandmarks(canvas, points) : undefined;
    if (canvas) drawLandmarks(canvas);
    if (running || !stream) return;
    if (showPoints) startVision().catch(() => undefined);
    else stopVision();
    // startVision reads the current kind and stream; re-running on those is what restarts it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showPoints, stream, running, kind]);
  const headers = { 'X-Training-Code': code };
  const vocabulary = counts?.[kind].vocabulary ?? [];
  const subjectValid = /^[a-zA-Z0-9_-]{2,40}$/.test(subject);
  // While recording, the example follows the phrase being asked for; otherwise the one picked from the list.
  const exampleOf = (id?: string) => {
    const p = vocabulary.find((x) => x.id === id && x.reference);
    return p?.reference && { id: p.id, text: p.text, ...p.reference, embed: youtubeEmbed(p.reference) };
  };
  const example = running
    ? exampleOf(prompt?.id)
    : exampleOf(shown) || exampleOf(vocabulary.find((x) => x.reference)?.id);

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
    stopVision();
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
      await startVision();
    } catch (e) {
      stopAll((e as Error).message);
      return;
    }
    const phrases: Phrase[] = [
      ...vocabulary,
      ...UNKNOWN_HINTS[kind].map((hint) => ({
        id: 'unknown',
        text: '（対象外の動き）',
        hint: `対象外の動き：${hint}`,
      })),
    ];
    const queue = Array.from({ length: repetitions }, () => shuffle(phrases)).flat();
    let done = 0;
    for (const phrase of queue) {
      let saved = false;
      for (let attempt = 0; attempt < 3 && !saved && !r.cancelled; attempt++) {
        const hint = phrase.hint;
        // Play the phrase's example right before the countdown, so the movement is fresh when recording starts.
        if (playExample && phrase.reference && exampleMs(phrase.reference)) {
          setPrompt({ id: phrase.id, text: phrase.text, hint, phase: '見本', done, total: queue.length });
          setPlays((n) => n + 1);
          await wait(exampleMs(phrase.reference));
        }
        for (let n = COUNTDOWN; n > 0 && !r.cancelled; n--) {
          setPrompt({ id: phrase.id, text: phrase.text, hint, phase: `${n}`, done, total: queue.length });
          await wait(700);
        }
        if (r.cancelled) break;
        setPrompt({ id: phrase.id, text: phrase.text, hint, phase: '撮影中', done, total: queue.length });
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
    <main className="device-setup training-page">
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
        <label className="setting-check">
          <input type="checkbox" checked={showPoints} onChange={(e) => setShowPoints(e.target.checked)} />
          {t('特徴点を表示（緑は学習に使われる映像、赤は使われない映像）')}
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
        <div className={example ? 'training-stage with-example' : 'training-stage'}>
          <div className="setup-preview">
            {stream ? (
              <Video stream={stream} local label={t('学習データ収集のプレビュー')} />
            ) : (
              <p>{t('カメラ OFF')}</p>
            )}
            <canvas ref={overlay} className="landmark-overlay mirrored" aria-hidden="true" />
          </div>
          {example && (
            <figure className="training-example">
              {example.embed ? (
                <iframe
                  key={`${example.embed}#${plays}`}
                  src={example.embed}
                  title={t('見本：{text}', { text: t(example.text) })}
                  allow="autoplay; encrypted-media; picture-in-picture"
                  referrerPolicy="strict-origin-when-cross-origin"
                />
              ) : (
                <p>{t('この表現は、見本のリンク先で動きを確認してください')}</p>
              )}
              <figcaption>
                {t('見本：{text}', { text: t(example.text) })}（
                <a href={example.url} target="_blank" rel="noopener noreferrer">
                  {example.source}
                </a>
                ）
              </figcaption>
            </figure>
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
      {vocabulary.some((p) => p.reference) && (
        <section className="training-counts" aria-label={t('見本の動画')}>
          <h2>{t('見本の動画')}</h2>
          <p>{t('撮影の前に動きを1つに決め、毎回同じ動きで撮影してください。')}</p>
          <label className="setting-check">
            <input
              type="checkbox"
              checked={playExample}
              disabled={running}
              onChange={(e) => setPlayExample(e.target.checked)}
            />
            {t('連続撮影で、毎回の撮影の前に見本を流す')}
          </label>
          <ul className="training-references">
            {vocabulary.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className={p.id === example?.id ? 'primary' : 'secondary'}
                  aria-pressed={p.id === example?.id}
                  disabled={running || !p.reference}
                  onClick={() => {
                    setShown(p.id);
                    setPlays((n) => n + 1);
                  }}
                >
                  {t(p.text)}
                </button>
                <span>{p.reference?.source ?? '—'}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
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
      {counts?.models && (
        <section className="training-counts" aria-label={t('学習と配備')}>
          <h2>{t('いま会話で使っているモデル')}</h2>
          {counts.models[kind].available ? (
            <p>
              {counts.models[kind].model_version}・
              {t('{people}人・{recordings}件で学習', {
                people: counts.models[kind].people ?? '—',
                recordings: counts.models[kind].recordings ?? '—',
              })}
              ・{t('正解率の目安（F1）')} {percent(counts.models[kind].macro_f1_known)}・{t('対象外の誤受理')}{' '}
              {percent(counts.models[kind].unknown_false_accept_rate)}
              {counts.models[kind].method === 'within-subject-holdout' && <>（{t('1人分のデータで評価')}）</>}
            </p>
          ) : (
            <p>{t('まだありません。データが集まると自動で学習し、評価に合格したモデルを会話で使います。')}</p>
          )}
          {!!counts.runs?.filter((x) => x.modality === kind).length && (
            <>
              <h2>{t('最近の学習')}</h2>
              <ul className="training-runs">
                {counts.runs
                  .filter((x) => x.modality === kind)
                  .map((x) => (
                    <li key={x.at + (x.version ?? '')}>
                      <span>{new Date(x.at).toLocaleString()}</span>
                      <span>
                        {x.failed
                          ? t('データ不足で学習せず')
                          : `${t('{people}人・{recordings}件', { people: x.people ?? '—', recordings: x.recordings ?? '—' })} F1 ${percent(x.macro_f1_known)}`}
                      </span>
                      <b>{x.registered ? t('配備') : x.failed ? '—' : t('不合格')}</b>
                    </li>
                  ))}
              </ul>
            </>
          )}
        </section>
      )}
      <a href="/">{t('会話の入室画面へ')}</a>
    </main>
  );
}
