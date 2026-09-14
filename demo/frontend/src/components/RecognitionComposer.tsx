import { useEffect, useState } from 'react';
import type { Candidate, InputKind, PublicConfig } from '../types/protocol';
import { useI18n } from '../i18n';

export default function RecognitionComposer({
  input,
  candidate,
  capturing,
  processing,
  connected,
  config,
  onStart,
  onEnd,
  onSubmit,
  onCancel,
}: {
  input: InputKind;
  candidate: Candidate | null;
  capturing: boolean;
  processing: boolean;
  connected: boolean;
  config: PublicConfig;
  onStart: () => Promise<void>;
  onEnd: () => Promise<void>;
  onSubmit: (text: string, candidateId?: string) => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const [text, setText] = useState(''),
    [busy, setBusy] = useState(false),
    [useCandidate, setUseCandidate] = useState(false),
    [expired, setExpired] = useState(false);
  useEffect(() => {
    if (candidate) {
      setText(candidate.candidates[0]?.text ?? '');
      setUseCandidate(true);
      setExpired(false);
      const timer = setTimeout(() => setExpired(true), candidate.expires_in * 1000);
      return () => clearTimeout(timer);
    }
  }, [candidate]);
  const vision = input === 'lipread' || input === 'sign';
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await onSubmit(text, useCandidate && !expired ? candidate?.candidate_id : undefined);
      setText('');
      setUseCandidate(false);
    } catch {
      /* The session controller displays the error; preserve the draft. */
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="composer" aria-label={t('発言入力')}>
      {vision && (
        <div className="capture-controls">
          <p>
            {input === 'lipread'
              ? t('口元を明るく、正面から映してください。')
              : t('両手と上半身が映る位置にカメラを置いてください。')}
          </p>
          <button
            className="primary"
            disabled={!connected || processing}
            onClick={() => {
              void (capturing ? onEnd() : onStart());
            }}
          >
            {capturing
              ? t('撮影を終了して認識')
              : processing
                ? t('認識しています…')
                : t(input === 'lipread' ? '読唇の撮影を開始' : '手話の撮影を開始')}
          </button>
          {(capturing || processing) && (
            <button className="secondary" onClick={onCancel}>
              {t('取消')}
            </button>
          )}
          <details>
            <summary>
              {t(config.capabilities[input].language_note ? '対象言語と制約' : '対応する登録表現')}
            </summary>
            <p>
              {config.capabilities[input].language_note
                ? t(config.capabilities[input].language_note)
                : config.capabilities[input].vocabulary.map((x) => x.text).join('、') || t('モデル未導入')}
            </p>
          </details>
        </div>
      )}
      {candidate && (
        <div className="candidate-box">
          <p>{expired ? t('候補の期限が切れました。文字入力として送信できます。') : t(candidate.message)}</p>
          <div className="candidate-options">
            {candidate.candidates.map((c) => (
              <button
                className="secondary"
                key={c.label}
                onClick={() => {
                  setText(c.text);
                  setUseCandidate(true);
                }}
              >
                {c.text}
              </button>
            ))}
          </div>
        </div>
      )}
      <form onSubmit={submit}>
        <label htmlFor="message-input">{useCandidate ? t('認識結果を確認・修正') : t('文字で伝える')}</label>
        <div className="compose-row">
          <textarea
            id="message-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t('伝えたいことを入力…')}
            maxLength={config.max_text_chars}
            required
            rows={2}
          />
          <button className="primary" disabled={!connected || busy || !text.trim()}>
            {busy ? t('送信中') : t('送信')}
          </button>
        </div>
        {useCandidate && (
          <button type="button" className="text-button" onClick={() => setUseCandidate(false)}>
            {t('文字入力として送信する')}
          </button>
        )}
      </form>
    </section>
  );
}
