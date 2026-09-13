import { useEffect, useRef, useState } from 'react';
import { VisionCapture } from '../services/visionCapture';
import Video from '../components/Video';
import { LanguageSelect, useI18n } from '../i18n';

export default function TrainingPage() {
  const { t } = useI18n();
  const [kind, setKind] = useState<'lipread' | 'sign'>('lipread'),
    [subject, setSubject] = useState(''),
    [label, setLabel] = useState('greeting');
  const [consent, setConsent] = useState(false),
    [stream, setStream] = useState<MediaStream>(),
    [status, setStatus] = useState(''),
    [busy, setBusy] = useState(false),
    [capturing, setCapturing] = useState(false);
  const refs = useRef({
    vision: new VisionCapture(),
    stream: undefined as MediaStream | undefined,
    frames: [] as number[][][],
    times: [] as number[],
    timer: undefined as ReturnType<typeof setTimeout> | undefined,
    active: false,
    startedAt: 0,
  });
  const r = refs.current;
  useEffect(
    () => () => {
      r.vision.stop();
      r.stream?.getTracks().forEach((t) => t.stop());
      clearTimeout(r.timer);
    },
    [r],
  );
  async function prepare() {
    setBusy(true);
    try {
      r.stream?.getTracks().forEach((t) => t.stop());
      r.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: false,
      });
      setStream(r.stream);
      setStatus('カメラを準備しました');
    } catch {
      setStatus('カメラを利用できません。権限を確認してください');
    } finally {
      setBusy(false);
    }
  }
  function finish() {
    if (!r.active) return;
    r.active = false;
    r.vision.stop();
    clearTimeout(r.timer);
    setCapturing(false);
    setBusy(false);
    setStatus(`${r.frames.length}フレームを収集しました。「特徴点を保存」でローカルに保存できます。`);
  }
  async function capture() {
    setBusy(true);
    r.frames = [];
    r.times = [];
    try {
      if (!r.stream) throw new Error('カメラをONにしてください');
      await r.vision.start(
        r.stream,
        kind,
        (f, t) => {
          if (!r.active) return;
          r.frames.push(f);
          r.times.push(t);
          if (r.frames.length >= (kind === 'lipread' ? 64 : 96)) finish();
        },
        setStatus,
      );
      r.active = true;
      r.startedAt = Date.now();
      setCapturing(true);
      setBusy(false);
      setStatus('登録表現を1回行ってください');
      r.timer = setTimeout(finish, kind === 'lipread' ? 3200 : 4800);
    } catch (e) {
      setStatus((e as Error).message);
      setBusy(false);
    }
  }
  function save() {
    if (r.frames.length < 2) {
      setStatus('先に撮影してください');
      return;
    }
    const data = {
      version: 1,
      subject_id: subject,
      label,
      modality: kind,
      consent: true,
      created_at: new Date(r.startedAt).toISOString(),
      preprocessing_version: 'landmarks-v1',
      mediapipe_version: '0.10.32',
      frames: r.frames,
      timestamps: r.times,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `${kind}-${subject}-${label}-${r.startedAt}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <main className="device-setup">
      <div className="page-language">
        <LanguageSelect />
      </div>
      <p className="eyebrow">{t('学習データ収集 · 会話とは別の操作です')}</p>
      <h1>{t('登録表現の特徴点を収集')}</h1>
      <p>
        {t(
          '映像は保存・送信しません。顔・手・姿勢の特徴点を端末に保存します。本人の同意がある収録だけ行ってください。',
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void capture();
        }}
      >
        <div className="training-fields">
          <label>
            {t('入力方式')}
            <select
              value={kind}
              disabled={capturing || busy}
              onChange={(e) => setKind(e.target.value as 'lipread' | 'sign')}
            >
              <option value="lipread">{t('読唇')}</option>
              <option value="sign">{t('日本手話')}</option>
            </select>
          </label>
          <label>
            {t('人物ID（氏名を使用しない）')}
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              pattern={'[a-zA-Z0-9_\\-]{2,40}'}
              required
              disabled={capturing || busy}
            />
          </label>
          <label>
            {t('クラスID')}
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              pattern={'[a-zA-Z0-9_\\-]{1,40}'}
              required
              disabled={capturing || busy}
            />
          </label>
        </div>
        <label className="setting-check">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => {
              setConsent(e.target.checked);
              if (!e.target.checked) {
                finish();
                r.vision.stop();
                r.stream?.getTracks().forEach((t) => t.stop());
                r.stream = undefined;
                setStream(undefined);
                r.frames = [];
                r.times = [];
                setStatus('収集を停止し、未保存の特徴点を破棄しました');
              }
            }}
          />
          {t('本人が収集・モデル学習への使用に同意しています')}
        </label>
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
            disabled={!consent || busy || capturing}
            onClick={() => void prepare()}
          >
            {t('カメラをON')}
          </button>
          <button className="primary" disabled={!consent || !stream || busy || capturing}>
            {busy ? t('モデルを準備中…') : t('撮影を開始')}
          </button>
          <button type="button" className="secondary" disabled={!capturing} onClick={finish}>
            {t('撮影を終了')}
          </button>
          <button type="button" className="secondary" disabled={capturing || busy || !consent} onClick={save}>
            {t('特徴点を保存')}
          </button>
        </div>
      </form>
      <p>{t('クラスIDはconfig/vocabulary.ja.jsonと一致させます。対象外の動作はunknownとして収集します。')}</p>
      <a href="/">{t('会話の入室画面へ')}</a>
    </main>
  );
}
