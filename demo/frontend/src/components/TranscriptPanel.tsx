import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Utterance } from '../types/protocol';
import { useI18n } from '../i18n';
import UserAvatar from './UserAvatar';

export default function TranscriptPanel({
  utterances,
  self,
  onCorrect,
  children,
  enabled = true,
  avatars = {},
  readingId = null,
}: {
  utterances: Utterance[];
  self: string;
  onCorrect: (u: Utterance, text: string) => Promise<void>;
  children?: ReactNode;
  enabled?: boolean;
  avatars?: Record<string, string>;
  readingId?: string | null;
}) {
  const { t, locale } = useI18n();
  const scroll = useRef<HTMLDivElement>(null),
    follow = useRef(true);
  const [unread, setUnread] = useState(false),
    [editing, setEditing] = useState<string | null>(null),
    [text, setText] = useState(''),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (follow.current && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
    else setUnread(true);
  }, [utterances]);
  return (
    <aside className="transcript-panel" id="transcript-panel" aria-label={t('文字おこし')}>
      <h2>{t('文字おこし')}</h2>
      <div className="transcript-history">
        <div
          className="transcript-scroll"
          ref={scroll}
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          onScroll={() => {
            const el = scroll.current!;
            follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 70;
            if (follow.current) setUnread(false);
          }}
        >
          {!utterances.length && (
            <p className="empty-transcript">
              {t(
                enabled
                  ? '会話がはじまると、ここに言葉が並びます。'
                  : '文字出力はOFFです。下の出力設定で文字を選択すると表示できます。',
              )}
            </p>
          )}
          {utterances.map((u) => (
            <article
              key={u.utterance_id}
              className={
                'utterance ' +
                (u.participant_id === self ? 'own' : 'other') +
                (readingId === u.utterance_id ? ' reading' : '')
              }
            >
              <header>
                {readingId === u.utterance_id && <span className="reading-label">{t('読み上げ中')}</span>}
                <UserAvatar avatar={avatars[u.participant_id]} name={u.display_name} size={26} />
                <b>{u.display_name}</b>
                <time dateTime={u.created_at}>
                  {new Date(u.created_at).toLocaleTimeString(locale === 'ja' ? 'ja-JP' : 'en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </time>
              </header>
              <div className="message-bubble">
                {editing === u.utterance_id ? (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      setBusy(true);
                      try {
                        await onCorrect(u, text);
                        setEditing(null);
                      } catch {
                        /* Keep the draft. */
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    <textarea
                      aria-label={t('発言の修正')}
                      autoFocus
                      value={text}
                      maxLength={500}
                      required
                      onChange={(e) => setText(e.target.value)}
                      disabled={busy}
                    />
                    <div className="edit-actions">
                      <button disabled={busy || !text.trim()} className="primary">
                        {t('修正を送信')}
                      </button>
                      <button
                        type="button"
                        className="text-button"
                        disabled={busy}
                        onClick={() => setEditing(null)}
                      >
                        {t('取消')}
                      </button>
                    </div>
                  </form>
                ) : (
                  <p>{u.text}</p>
                )}
                <footer>
                  {u.revision > 1 && <small>{t('修正済み')}</small>}
                  {u.participant_id === self && editing !== u.utterance_id && (
                    <button
                      className="text-button"
                      onClick={() => {
                        setEditing(u.utterance_id);
                        setText(u.text);
                      }}
                    >
                      {t('修正')}
                    </button>
                  )}
                </footer>
              </div>
            </article>
          ))}
        </div>
        {unread && (
          <button
            className="latest secondary"
            onClick={() => {
              follow.current = true;
              setUnread(false);
              if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
            }}
          >
            {t('最新へ ↓')}
          </button>
        )}
      </div>
      {children}
    </aside>
  );
}
