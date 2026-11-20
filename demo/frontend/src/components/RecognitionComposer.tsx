import { useEffect, useRef, useState } from 'react';
import type { Candidate, InputKind, PublicConfig, VisionLanguage } from '../types/protocol';
import { capability, languages } from '../services/capabilities';
import { useI18n } from '../i18n';

export default function RecognitionComposer({
  input,
  language,
  onLanguage,
  candidate,
  capturing,
  watching,
  onWatch,
  processing,
  connected,
  config,
  onStart,
  onEnd,
  onSubmit,
  onCancel,
}: {
  input: InputKind;
  language: VisionLanguage;
  onLanguage: (language: VisionLanguage) => Promise<void>;
  candidate: Candidate | null;
  capturing: boolean;
  watching: boolean;
  onWatch: (on: boolean) => Promise<void>;
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
  const candidateRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // The composer can be taller than its panel on a phone; bring a new suggestion into view.
    if (candidate) candidateRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [candidate]);
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
  const cap = capability(config, input, language);
  const choices = languages(config, input);
  const instant = cap.transport === 'features';
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!processing) return;
    setElapsed(0);
    const since = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - since) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [processing]);
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
      {/* While a suggestion waits, it and the send box come first: they are what the speaker acts on next. */}
      {candidate ? (
        <>
          {candidate && (
            <div className="candidate-box" ref={candidateRef}>
              <p>
                {expired ? t('候補の期限が切れました。文字入力として送信できます。') : t(candidate.message)}
              </p>
              {candidate.candidates.length > 1 && (
                <div className="candidate-options">
                  {candidate.candidates.map((c) => (
                    <button
                      className="secondary"
                      key={c.label}
                      aria-pressed={text === c.text}
                      onClick={() => {
                        setText(c.text);
                        setUseCandidate(true);
                      }}
                    >
                      {c.text}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <form onSubmit={submit}>
            <label htmlFor="message-input">
              {useCandidate ? t('認識結果を確認・修正') : t('文字で伝える')}
            </label>
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
          {vision && (
            <div className="capture-controls">
              {choices.length > 1 && (
                <div className="capture-setting">
                  <span className="capture-setting-label" id="recognition-language">
                    {t('言語')}
                  </span>
                  <div className="segmented" role="group" aria-labelledby="recognition-language">
                    {choices.map((x) => (
                      <button
                        key={x}
                        type="button"
                        aria-pressed={x === language}
                        disabled={capturing || processing || watching}
                        onClick={() => void onLanguage(x)}
                      >
                        {t(x === 'ja' ? '日本語（定型句）' : '英語（自由文）')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {instant && (
                <div className="capture-setting">
                  <span className="capture-setting-label" id="recognition-trigger">
                    {t('撮り方')}
                  </span>
                  <div className="segmented" role="group" aria-labelledby="recognition-trigger">
                    <button
                      type="button"
                      aria-pressed={!watching}
                      disabled={!connected || capturing || (processing && !watching)}
                      onClick={() => watching && void onWatch(false)}
                    >
                      {t('ボタンで撮る')}
                    </button>
                    <button
                      type="button"
                      aria-pressed={watching}
                      disabled={!connected || capturing || (processing && !watching)}
                      onClick={() => !watching && void onWatch(true)}
                    >
                      {t('自動で認識')}
                    </button>
                  </div>
                </div>
              )}
              <p>
                {input === 'lipread'
                  ? t('口元を明るく、正面から映してください。')
                  : t('両手と上半身が映る位置にカメラを置いてください。')}
              </p>
              {watching ? (
                <p className="watch-status" role="status">
                  <span className="watch-dot" aria-hidden="true" />
                  {t(
                    input === 'lipread'
                      ? '自動で認識しています。口を動かしてください'
                      : '自動で認識しています。手話をしてください',
                  )}
                </p>
              ) : (
                <button
                  className={'primary capture-main' + (capturing ? ' recording' : '')}
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
              )}
              {(capturing || processing) && (
                <button className="secondary" onClick={onCancel}>
                  {t('取消')}
                </button>
              )}
              {processing && (
                <p className="capture-wait">
                  <span role="status">
                    {t(
                      instant
                        ? '登録表現の中から候補を探しています。'
                        : input === 'lipread'
                          ? '読唇の認識は数秒かかります。'
                          : '手話の認識は数秒から十数秒かかります。',
                    )}
                  </span>
                  <span aria-hidden="true">{t('{seconds}秒経過', { seconds: elapsed })}</span>
                </p>
              )}
              <details>
                <summary>{t(cap.language_note ? '対象言語と制約' : '対応する登録表現')}</summary>
                <p>
                  {cap.language_note
                    ? t(cap.language_note)
                    : cap.vocabulary.map((x) => x.text).join('、') || t('モデル未導入')}
                </p>
              </details>
            </div>
          )}
        </>
      ) : (
        <>
          {vision && (
            <div className="capture-controls">
              {choices.length > 1 && (
                <div className="capture-setting">
                  <span className="capture-setting-label" id="recognition-language">
                    {t('言語')}
                  </span>
                  <div className="segmented" role="group" aria-labelledby="recognition-language">
                    {choices.map((x) => (
                      <button
                        key={x}
                        type="button"
                        aria-pressed={x === language}
                        disabled={capturing || processing || watching}
                        onClick={() => void onLanguage(x)}
                      >
                        {t(x === 'ja' ? '日本語（定型句）' : '英語（自由文）')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {instant && (
                <div className="capture-setting">
                  <span className="capture-setting-label" id="recognition-trigger">
                    {t('撮り方')}
                  </span>
                  <div className="segmented" role="group" aria-labelledby="recognition-trigger">
                    <button
                      type="button"
                      aria-pressed={!watching}
                      disabled={!connected || capturing || (processing && !watching)}
                      onClick={() => watching && void onWatch(false)}
                    >
                      {t('ボタンで撮る')}
                    </button>
                    <button
                      type="button"
                      aria-pressed={watching}
                      disabled={!connected || capturing || (processing && !watching)}
                      onClick={() => !watching && void onWatch(true)}
                    >
                      {t('自動で認識')}
                    </button>
                  </div>
                </div>
              )}
              <p>
                {input === 'lipread'
                  ? t('口元を明るく、正面から映してください。')
                  : t('両手と上半身が映る位置にカメラを置いてください。')}
              </p>
              {watching ? (
                <p className="watch-status" role="status">
                  <span className="watch-dot" aria-hidden="true" />
                  {t(
                    input === 'lipread'
                      ? '自動で認識しています。口を動かしてください'
                      : '自動で認識しています。手話をしてください',
                  )}
                </p>
              ) : (
                <button
                  className={'primary capture-main' + (capturing ? ' recording' : '')}
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
              )}
              {(capturing || processing) && (
                <button className="secondary" onClick={onCancel}>
                  {t('取消')}
                </button>
              )}
              {processing && (
                <p className="capture-wait">
                  <span role="status">
                    {t(
                      instant
                        ? '登録表現の中から候補を探しています。'
                        : input === 'lipread'
                          ? '読唇の認識は数秒かかります。'
                          : '手話の認識は数秒から十数秒かかります。',
                    )}
                  </span>
                  <span aria-hidden="true">{t('{seconds}秒経過', { seconds: elapsed })}</span>
                </p>
              )}
              <details>
                <summary>{t(cap.language_note ? '対象言語と制約' : '対応する登録表現')}</summary>
                <p>
                  {cap.language_note
                    ? t(cap.language_note)
                    : cap.vocabulary.map((x) => x.text).join('、') || t('モデル未導入')}
                </p>
              </details>
            </div>
          )}
          <form onSubmit={submit}>
            <label htmlFor="message-input">
              {useCandidate ? t('認識結果を確認・修正') : t('文字で伝える')}
            </label>
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
        </>
      )}
    </section>
  );
}
