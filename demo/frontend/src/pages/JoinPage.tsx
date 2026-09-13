import { useState } from 'react';
import type { InputKind, Mode, PublicConfig, Session } from '../types/protocol';
import { inputNames } from '../types/protocol';
import { api } from '../services/api';
import ModeCard from '../components/ModeCard';
import AvatarPicker from '../components/AvatarPicker';
import { LanguageSelect, useI18n } from '../i18n';

export default function JoinPage({
  config,
  onJoin,
  notice,
}: {
  config: PublicConfig;
  onJoin: (s: Session) => void;
  notice: string;
}) {
  const { t, locale } = useI18n();
  const [avatar, setAvatar] = useState(() => {
    try {
      return localStorage.getItem('user-avatar') ?? '';
    } catch {
      return '';
    }
  });
  const [avatarBusy, setAvatarBusy] = useState(false);
  function changeAvatar(value: string) {
    setAvatar(value);
    try {
      if (value) localStorage.setItem('user-avatar', value);
      else localStorage.removeItem('user-avatar');
    } catch {
      /* Optional storage. */
    }
  }
  const [displayName, setDisplayName] = useState(() => {
    try {
      return localStorage.getItem('display-name') ?? '';
    } catch {
      return '';
    }
  });
  const [mode, setMode] = useState<Mode>('standard');
  const [input, setInput] = useState<InputKind>(config.capabilities.speech.available ? 'speech' : 'text');
  const [room, setRoom] = useState(sessionStorage.getItem('last-room') ?? '');
  const [action, setAction] = useState<'join' | 'create'>('join');
  const [created, setCreated] = useState<{ room: string; expires: number } | null>(null);
  const [password, setPassword] = useState(''),
    [show, setShow] = useState(false),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  function chooseMode(m: Mode) {
    setMode(m);
    const preferred = config.modes[m].input;
    setInput(preferred === 'text' || config.capabilities[preferred].available ? preferred : 'text');
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || avatarBusy) return;
    setError('');
    setBusy(true);
    try {
      const id = room.trim().toLowerCase();
      if (action === 'create') {
        const createdRoom = await api<{ room_id: string; expires_at: number }>('/api/rooms', {
          method: 'POST',
          body: JSON.stringify({ room_id: id, password }),
        });
        setCreated({ room: createdRoom.room_id, expires: createdRoom.expires_at });
        // Keep creation success even if the subsequent join request fails.
        setAction('join');
        sessionStorage.setItem('last-room', id);
      }
      const result = await api<Session>(`/api/rooms/${encodeURIComponent(id)}/join`, {
        method: 'POST',
        body: JSON.stringify({ password, mode, input, display_name: displayName.trim(), avatar }),
      });
      sessionStorage.setItem('last-room', id);
      setPassword('');
      try {
        localStorage.setItem('display-name', displayName.trim());
      } catch {
        /* Storage is optional. */
      }
      onJoin(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="join-page">
      <div className="page-language">
        <LanguageSelect />
      </div>
      <header className="join-heading">
        <p className="eyebrow">{t('それぞれの伝え方で、ひとつの会話を。')}</p>
        <h1>{t(config.name)}</h1>
        <p>{t('発声・読唇・手話に対応可能な会話アプリ')}</p>
      </header>
      {notice && (
        <p className="notice" role="status">
          {t(notice)}
        </p>
      )}
      <form onSubmit={submit}>
        <div className="room-actions" role="group" aria-label={t('ルームの操作')}>
          {(['join', 'create'] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={action === value ? 'primary' : 'secondary'}
              aria-pressed={action === value}
              disabled={busy}
              onClick={() => {
                setAction(value);
                setError('');
                setCreated(null);
              }}
            >
              {value === 'join' ? t('既存ルームに参加') : t('新規ルームを作成')}
            </button>
          ))}
        </div>
        <fieldset className="mode-grid" disabled={busy}>
          <legend className="sr-only">{t('利用モードを選択')}</legend>
          {(['standard', 'vision_support', 'hearing_support'] as Mode[]).map((m) => (
            <ModeCard key={m} mode={m} selected={mode === m} onSelect={() => chooseMode(m)} />
          ))}
        </fieldset>
        <div className="join-profile">
          <AvatarPicker
            value={avatar}
            onChange={changeAvatar}
            disabled={busy || avatarBusy}
            onBusy={setAvatarBusy}
          />
          <label className="join-name">
            {t('名前')}
            <input
              aria-label={t('表示名')}
              maxLength={40}
              value={displayName}
              disabled={busy}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t('任意・40文字まで')}
            />
          </label>
        </div>
        <div className="join-options">
          <label>
            {t('入力方法')}
            <select
              aria-label={t('入力方法')}
              value={input}
              disabled={busy}
              onChange={(e) => setInput(e.target.value as InputKind)}
            >
              {config.modes[mode].allowed_inputs.map((k) => (
                <option key={k} value={k} disabled={k !== 'text' && !config.capabilities[k].available}>
                  {t(inputNames[k])}
                  {k !== 'text' && !config.capabilities[k].available ? t('（モデル未導入）') : ''}
                </option>
              ))}
            </select>
          </label>
          <p>
            {t('音声または特徴点をサーバーで認識します。')}
            {t('自分のカメラは会話中にこの端末内で録画されます。')}
          </p>
        </div>
        {input === 'text' && (
          <p className="availability">
            {t('文字入力で参加できます。')}
            {config.modes[mode].allowed_inputs
              .filter((k) => k !== 'text' && !config.capabilities[k].available)
              .map((k) => (
                <span key={k}>
                  {' '}
                  {t(inputNames[k])}: {t(config.capabilities[k as 'speech'].reason)}。
                </span>
              ))}
          </p>
        )}
        {(input === 'lipread' || input === 'sign') && (
          <p className="availability">
            {t('登録表現のみ対応：')}
            {config.capabilities[input].vocabulary.map((x) => x.text).join('、')}
            {t('。認識候補を確認して送信します。')}
          </p>
        )}
        <div className="credentials">
          <label>
            <span>
              ID <small>{t('ルームID')}</small>
            </span>
            <input
              name="room"
              aria-label={t('ルームID')}
              value={room}
              onChange={(e) => setRoom(e.target.value)}
              required
              disabled={busy}
              minLength={3}
              maxLength={32}
              pattern={'[a-zA-Z0-9\\-]{3,32}'}
              autoComplete="off"
              placeholder="demo-room"
              aria-describedby="room-guidance"
            />
          </label>
          <label>
            <span>{t('パスワード')}</span>
            <input
              name="password"
              aria-label={t('パスワード')}
              type={show ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={busy}
              minLength={action === 'create' ? 8 : 1}
              maxLength={128}
              autoComplete={action === 'create' ? 'new-password' : 'current-password'}
              aria-describedby="room-guidance"
            />
          </label>
        </div>
        <p className="join-footnote" id="room-guidance">
          {action === 'create'
            ? t(
                'ルームIDは半角英数字・ハイフンの3〜32文字、パスワードは8〜128文字で設定してください。作成後、そのまま参加します。',
              )
            : t('作成済みのルームIDとパスワードを入力してください。')}
        </p>
        <label className="show-password">
          <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
          {t('パスワードを表示')}
        </label>
        {created && (
          <p className="notice" role="status">
            {t(
              'ルーム「{room}」を作成しました。有効期限：{date}。参加できない場合は、同じIDとパスワードで再試行してください。',
              {
                room: created.room,
                date: new Date(created.expires * 1000).toLocaleString(locale === 'ja' ? 'ja-JP' : 'en-US'),
              },
            )}
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <button className="join-button primary" disabled={busy || avatarBusy}>
          {busy ? t('接続中…') : action === 'create' ? t('ルームを作成して参加') : t('会話に参加')}{' '}
          <span aria-hidden="true">→</span>
        </button>
        <p className="join-footnote">
          {t('相手も同じルームIDとパスワードで参加できます。作成した方から相手に伝えてください。')}
        </p>
      </form>
    </main>
  );
}
