import ReactDOM from 'react-dom/client';
import App from './App';
import { I18nProvider } from './i18n';
import './styles/tokens.css';
import './styles/layout.css';
import './styles/accessibility.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <I18nProvider>
    <App />
  </I18nProvider>,
);
