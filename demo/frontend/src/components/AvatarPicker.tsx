import { useRef, useState } from 'react';
import { useI18n } from '../i18n';
import UserAvatar from './UserAvatar';

export default function AvatarPicker({
  value,
  onChange,
  disabled,
  onBusy,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  onBusy: (busy: boolean) => void;
}) {
  const { t } = useI18n();
  const fileInput = useRef<HTMLInputElement>(null);
  const [error, setError] = useState('');
  async function select(file?: File) {
    if (!file) return;
    setError('');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError('5MB以下のPNG・JPEG・WebP画像を選択してください');
      return;
    }
    onBusy(true);
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 96;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error();
      const side = Math.min(img.naturalWidth, img.naturalHeight);
      ctx.drawImage(
        img,
        (img.naturalWidth - side) / 2,
        (img.naturalHeight - side) / 2,
        side,
        side,
        0,
        0,
        96,
        96,
      );
      const data = canvas.toDataURL('image/png');
      if (data.length > 65536) throw new Error();
      onChange(data);
    } catch {
      setError('画像を読み込めません。別の画像を選択してください');
    } finally {
      URL.revokeObjectURL(url);
      onBusy(false);
    }
  }
  return (
    <div className="avatar-picker">
      <UserAvatar avatar={value} size={52} />
      <div className="avatar-picker-actions">
        <span>{t('ユーザーアイコン')}</span>
        <div>
          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            disabled={disabled}
            aria-label={t('アイコン画像を選択')}
            onChange={(e) => {
              void select(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
          <button
            type="button"
            className="secondary"
            disabled={disabled}
            onClick={() => fileInput.current?.click()}
          >
            {t('画像を選択')}
          </button>
          {value && (
            <button
              type="button"
              className="text-button"
              disabled={disabled}
              onClick={() => {
                onChange('');
                setError('');
              }}
            >
              {t('アイコンを削除')}
            </button>
          )}
        </div>
        <small>{t('PNG・JPEG・WebP / 5MBまで。中央を正方形に切り抜きます。')}</small>
      </div>
      {error && (
        <p className="avatar-error" role="alert">
          {t(error)}
        </p>
      )}
    </div>
  );
}
