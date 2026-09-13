import { useEffect, useState } from 'react';
import ControlIcon from './ControlIcon';
import { useI18n } from '../i18n';

export default function UserAvatar({
  avatar,
  name,
  size = 28,
}: {
  avatar?: string;
  name?: string;
  size?: number;
}) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [avatar]);
  const label = name ? t('{name}のユーザーアイコン', { name }) : t('ユーザーアイコン');
  return (
    <span className="profile-avatar" style={{ width: size, height: size }} role="img" aria-label={label}>
      {avatar?.startsWith('data:image/png;base64,') && !failed ? (
        <img src={avatar} alt="" onError={() => setFailed(true)} />
      ) : (
        <ControlIcon kind="user" size={Math.round(size * 0.7)} />
      )}
    </span>
  );
}
