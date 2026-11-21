import { useI18n } from '../i18n';

// The footer under the join and guide pages: a link to the guide (or back to the top) and the copyright.
export default function SiteFooter({ onGuide = false }: { onGuide?: boolean }) {
  const { t } = useI18n();
  return (
    <footer className="site-footer">
      {onGuide ? <a href="/">{t('トップページ')}</a> : <a href="/guide">{t('使い方')}</a>}
      <span>© 2026 {t('ひとくち')}</span>
    </footer>
  );
}
