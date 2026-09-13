import { useEffect, useState } from 'react';
import type { PublicConfig, Session } from './types/protocol';
import { api } from './services/api';
import JoinPage from './pages/JoinPage';
import TalkPage from './pages/TalkPage';
import TrainingPage from './pages/TrainingPage';
import { LanguageSelect, useI18n } from './i18n';

export default function App() {
  const { t } = useI18n();
  const [config, setConfig] = useState<PublicConfig | null>(null),
    [session, setSession] = useState<Session | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(''),
    [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const c = await api<PublicConfig>('/api/config');
        if (!active) return;
        setConfig(c);
        try {
          const s = await api<Session>('/api/session');
          if (active) setSession(s);
        } catch {}
      } catch (e) {
        if (active) setError((e as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    document.title = config ? `${t(config.name)}${session ? ' · ' + t('会話中') : ''}` : t('ことばリンク');
  }, [config, session, t]);
  function join(s: Session) {
    history.replaceState(null, '', `/rooms/${encodeURIComponent(s.room_id)}`);
    setSession(s);
  }
  function leave(message: string) {
    setSession(null);
    setNotice(message);
    history.replaceState(null, '', '/');
    void api<PublicConfig>('/api/config')
      .then(setConfig)
      .catch(() => {});
  }
  if (loading)
    return (
      <main className="loading" role="status">
        <LanguageSelect />
        {t('会話の準備をしています…')}
      </main>
    );
  if (error || !config)
    return (
      <main className="loading">
        <LanguageSelect />
        <h1>{t('サーバーに接続できません')}</h1>
        <p role="alert">{t(error)}</p>
        <button className="primary" onClick={() => location.reload()}>
          {t('再試行')}
        </button>
      </main>
    );
  if (location.pathname === '/training' && !session) return <TrainingPage />;
  return session ? (
    <TalkPage config={config} session={session} onLeave={leave} />
  ) : (
    <JoinPage config={config} onJoin={join} notice={notice} />
  );
}
