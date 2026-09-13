import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import ControlIcon from './ControlIcon';
import UserAvatar from './UserAvatar';

export default function NameEditor({
  name,
  onSave,
  avatar,
}: {
  name: string;
  onSave: (name: string) => Promise<void>;
  avatar?: string;
}) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(name),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!editing) setDraft(name);
  }, [name, editing]);
  return editing ? (
    <form
      className="name-editor"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await onSave(draft.trim());
          setEditing(false);
        } catch {
          /* Controller shows the error. */
        } finally {
          setBusy(false);
        }
      }}
    >
      <input
        aria-label={t('表示名')}
        autoFocus
        required
        maxLength={40}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        disabled={busy}
      />
      <button className="primary" disabled={busy || !draft.trim()}>
        {t('名前を保存')}
      </button>
      <button type="button" className="text-button" disabled={busy} onClick={() => setEditing(false)}>
        {t('取消')}
      </button>
    </form>
  ) : (
    <button className="text-button name-button" aria-label={t('名前を変更')} onClick={() => setEditing(true)}>
      <UserAvatar avatar={avatar} name={name} size={22} />
      <span>{name}</span>
      <ControlIcon kind="edit" size={14} />
    </button>
  );
}
