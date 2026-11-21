import { Fragment } from 'react';
import { loadDefaultJapaneseParser } from 'budoux';
import { LanguageSelect, useI18n } from '../i18n';
import SiteFooter from '../components/SiteFooter';

// Japanese has no spaces, so the page keeps words whole (keep-all) and offers a break between phrases.
const parser = loadDefaultJapaneseParser();
function Phrases({ text }: { text: string }) {
  return (
    <>
      {parser.parse(text).map((chunk, i) => (
        <Fragment key={i}>
          {i > 0 && <wbr />}
          {chunk}
        </Fragment>
      ))}
    </>
  );
}

// A screenshot of the real screen with numbered outlines; steps[i] explains number i + 1.
type Figure = {
  src: string;
  width: number;
  height: number;
  title: string;
  steps: string[];
  phone?: boolean;
  side?: boolean;
};
type Item = { title: string; body: string };
type Section = { heading: string; intro?: string; figures?: Figure[]; items?: Item[]; note?: string };
type Guide = { title: string; lead: string; back: string; shots: string; sections: Section[] };

const IMG = {
  start: { src: '/guide/start.webp', width: 1600, height: 864 },
  device: { src: '/guide/device.webp', width: 1600, height: 1153 },
  room: { src: '/guide/room.webp', width: 1600, height: 1153 },
  candidate: { src: '/guide/candidate.webp', width: 1152, height: 1660, side: true },
  phoneJoin: { src: '/guide/phone-join.webp', width: 940, height: 1848, phone: true },
  phoneRoom: { src: '/guide/phone-room.webp', width: 940, height: 1848, phone: true },
};

// The guide's text lives here in both languages, since it is long prose rather than short UI labels.
const GUIDE: Record<'ja' | 'en', Guide> = {
  ja: {
    title: 'ことばリンクの使い方',
    lead: '声・口の動き・手話・文字のどれで話しても、相手には相手が選んだ形（字幕や読み上げ）で届くビデオ会話です。アプリのインストールは不要で、スマホやPCのブラウザで開くだけで使えます。',
    back: '入室画面へ戻る',
    shots: '画像は実際の画面です。番号は下の説明に対応しています。',
    sections: [
      {
        heading: '1. ルームを作る・入る',
        figures: [
          {
            ...IMG.start,
            title: 'トップページ',
            steps: [
              '「新規ルームを作成」か「既存ルームに参加」を選びます。',
              'モードを選びます。標準モード・視覚サポート（見えにくい方向け）・聴覚サポート（聞こえにくい方向け）があります。',
              '話し方（入力方法）を選びます。発声・読唇・手話・文字入力から選べ、入室後も変えられます。',
              'ルームIDとパスワードを入れます。作るときは、IDを半角英数字とハイフンで3〜32文字、パスワードを8文字以上にします。',
              '「ルームを作成して参加」（参加するときは「会話に参加」）を押します。',
            ],
          },
          {
            ...IMG.device,
            title: 'カメラと音声を確認',
            steps: [
              'カメラ（声で話すときはマイク）をONにします。ブラウザが許可を求めたら「許可」を選びます。',
              '相手の発言の受け取り方（出力）を選びます。',
              '「会話を開始」を押します。',
              'カメラやマイクを使わないときは「文字表示で参加」を押します。',
            ],
          },
        ],
      },
      {
        heading: '2. 会話の画面',
        figures: [
          {
            ...IMG.room,
            title: '会話の画面（PC）',
            steps: [
              '「招待リンクをコピー」で相手にリンクを送ります。パスワードは別に伝えます。1つのルームには4人まで入れます。',
              '文字おこし：全員の発言が字幕として並びます。声の発言は、話している途中から表示されます。',
              '読唇・手話は「撮影を開始」を押してから、声を出さずに口を動かすか、手話をします。上の「言語」で日本語（決まった10語）と英語（自由な文）を切り替えられます。',
              '文字で伝える：打って「送信」を押します。どの入力方法でも、いつでも文字で送れます。',
              '入力：話し方を途中で変えられます。',
              '出力：受け取り方を「字幕のみ」「字幕＋AI読み上げ」「字幕＋通常音声」から選べます。',
            ],
          },
        ],
      },
      {
        heading: '3. 読唇・手話は、候補を確かめてから送る',
        intro:
          '読唇や手話の認識は、なめらかな文でも意味が違うことがあります。そのため自動では送らず、必ず本人が確かめてから送ります。',
        figures: [
          {
            ...IMG.candidate,
            title: '認識の候補',
            steps: [
              'AIが読み取った候補です。違っていたら、別の候補を押して選びます。',
              '下の欄で確かめてから「送信」を押します。欄の中の文字を直してから送ることもできます。',
            ],
          },
        ],
        note: '日本手話は学習中で、選べない間は「モデル未導入」と表示されます。英語の手話（ASL）は自由な文を書き起こせます。',
      },
      {
        heading: '4. スマホで参加する',
        intro: '招待リンクをスマホで開くだけで参加できます。アプリのインストールはいりません。',
        figures: [
          {
            ...IMG.phoneJoin,
            title: '招待リンクを開いたところ',
            steps: [
              'ルームIDは入っています。聞いたパスワードを入れます。',
              '「会話に参加」を押します。名前は空欄でもかまいません。',
            ],
          },
          {
            ...IMG.phoneRoom,
            title: 'スマホの会話の画面',
            steps: [
              '文字おこし：相手の発言が字幕で並びます。',
              '文字で伝える：打って「送信」を押します。',
              '入力：話し方を変えられます。',
              '出力：受け取り方を変えられます。',
            ],
          },
        ],
      },
      {
        heading: '5. うまくいかないとき',
        items: [
          {
            title: 'カメラ・マイクが使えない',
            body: 'ブラウザの設定でカメラとマイクを許可してください。許可しない場合でも、文字で会話に参加できます。',
          },
          {
            title: '「機器が切断されました」と出る',
            body: 'スマホの画面が消えたり、別のアプリに切り替えたりすると、ブラウザがカメラやマイクを止めます。会話画面に戻り、もう一度ONにしてください。会話中は画面の自動ロックを切っておくと安心です。',
          },
          {
            title: '読み上げが聞こえない',
            body: 'iPhoneではマナーモードだと鳴らないことがあります。端末に日本語の音声が入っていない場合は、字幕をご利用ください。',
          },
        ],
      },
    ],
  },
  en: {
    title: 'How to use Kotoba Link',
    lead: 'A video conversation where you can talk by voice, lip movement, sign or text, and the others receive it the way they chose (captions or reading aloud). No app to install: open it in a phone or PC browser.',
    back: 'Back to the join page',
    shots: 'The pictures are the real screens (shown in Japanese). The numbers match the steps below them.',
    sections: [
      {
        heading: '1. Create or join a room',
        figures: [
          {
            ...IMG.start,
            title: 'Top page',
            steps: [
              'Choose "Create a room" or "Join a room".',
              'Choose a mode: Standard, Vision support (for people with low vision) or Hearing support (for people who are hard of hearing).',
              'Choose how you speak (input): voice, lipreading, sign or text. You can change it after joining.',
              'Enter the room ID and password. To create a room, use 3–32 letters, digits or hyphens for the ID and 8 characters or more for the password.',
              'Press "Create and join" (or "Join conversation" when joining).',
            ],
          },
          {
            ...IMG.device,
            title: 'Check your camera and audio',
            steps: [
              'Turn on the camera (and the microphone to speak by voice). Allow it when the browser asks.',
              'Choose how you receive what others say (output).',
              'Press "Start conversation".',
              'To join without camera or microphone, press "Join with text".',
            ],
          },
        ],
      },
      {
        heading: '2. The conversation screen',
        figures: [
          {
            ...IMG.room,
            title: 'Conversation (PC)',
            steps: [
              '"Copy invite link" and send it; tell the password separately. A room holds up to 4 people.',
              'Transcript: everyone’s messages appear as captions; spoken ones appear while the person is still talking.',
              'For lipreading or sign, press "Capture lip reading" / "Capture sign language", then move your lips without voice or sign. Switch between Japanese (10 set phrases) and English (free sentences) above it.',
              'Text: type and press "Send". You can always send text, whatever input you chose.',
              'Input: change how you speak at any time.',
              'Output: choose Captions only, Captions + AI voice or Captions + original audio.',
            ],
          },
        ],
      },
      {
        heading: '3. Check lipreading and sign before sending',
        intro:
          'Recognition can produce a fluent sentence with the wrong meaning, so nothing is sent automatically: you always check it first.',
        figures: [
          {
            ...IMG.candidate,
            title: 'Recognition candidates',
            steps: [
              'The candidates the AI read. If the first is wrong, press another one.',
              'Check the text below, fix it if needed, and press "Send".',
            ],
          },
        ],
        note: 'Japanese Sign Language is still being trained and shows "Model not installed" until it is ready. English sign (ASL) is transcribed as free sentences.',
      },
      {
        heading: '4. Join from a phone',
        intro: 'Just open the invite link on the phone. There is no app to install.',
        figures: [
          {
            ...IMG.phoneJoin,
            title: 'After opening the invite link',
            steps: [
              'The room ID is filled in. Enter the password you were told.',
              'Press "Join conversation". The name is optional.',
            ],
          },
          {
            ...IMG.phoneRoom,
            title: 'Conversation on a phone',
            steps: [
              'Transcript: the others’ messages as captions.',
              'Text: type and press "Send".',
              'Input: change how you speak.',
              'Output: change how you receive.',
            ],
          },
        ],
      },
      {
        heading: '5. Troubleshooting',
        items: [
          {
            title: 'Camera or microphone does not work',
            body: 'Allow the camera and microphone in the browser settings. Without them you can still join by text.',
          },
          {
            title: '"A device was disconnected"',
            body: 'Phones stop the camera and microphone when the screen turns off or you switch apps. Return to the conversation and turn them on again; turning off auto-lock helps.',
          },
          {
            title: 'No reading aloud',
            body: 'On iPhone, silent mode can mute it. If the device has no voice for the language, use captions.',
          },
        ],
      },
    ],
  },
};

function Shot({ figure }: { figure: Figure }) {
  return (
    <figure className={`guide-figure${figure.phone ? ' phone' : ''}${figure.side ? ' side' : ''}`}>
      <figcaption>
        <Phrases text={figure.title} />
      </figcaption>
      <a href={figure.src} target="_blank" rel="noopener">
        <img src={figure.src} width={figure.width} height={figure.height} alt={figure.title} loading="lazy" />
      </a>
      <ol className="guide-steps">
        {figure.steps.map((step, i) => (
          <li key={i}>
            <span className="guide-step-number" aria-hidden="true">
              {i + 1}
            </span>
            <span>
              <Phrases text={step} />
            </span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

export default function GuidePage() {
  const { locale } = useI18n();
  const g = GUIDE[locale === 'en' ? 'en' : 'ja'];
  return (
    <main className="guide-page">
      <div className="training-topbar">
        <a className="back-button" href="/">
          <span aria-hidden="true">←</span> {g.back}
        </a>
        <div className="page-language">
          <LanguageSelect />
        </div>
      </div>
      <h1>
        <Phrases text={g.title} />
      </h1>
      <p className="guide-lead">
        <Phrases text={g.lead} />
      </p>
      <p className="guide-lead">
        <Phrases text={g.shots} />
      </p>
      {g.sections.map((s) => (
        <section key={s.heading} className="guide-section">
          <h2>
            <Phrases text={s.heading} />
          </h2>
          {s.intro && (
            <p>
              <Phrases text={s.intro} />
            </p>
          )}
          {s.figures && (
            <div className={s.figures.every((f) => f.phone) ? 'guide-figures phones' : 'guide-figures'}>
              {s.figures.map((f) => (
                <Shot key={f.src} figure={f} />
              ))}
            </div>
          )}
          {s.note && (
            <p className="guide-note">
              <Phrases text={s.note} />
            </p>
          )}
          {s.items && (
            <dl>
              {s.items.map((item) => (
                <div key={item.title}>
                  <dt>
                    <Phrases text={item.title} />
                  </dt>
                  <dd>
                    <Phrases text={item.body} />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      ))}
      <SiteFooter onGuide />
    </main>
  );
}
