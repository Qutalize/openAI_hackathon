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

type Item = { title: string; body: string };
type Section = { heading: string; items: Item[] };
type Guide = { title: string; lead: string; back: string; sections: Section[] };

// The guide's text lives here in both languages, since it is long prose rather than short UI labels.
const GUIDE: Record<'ja' | 'en', Guide> = {
  ja: {
    title: 'ことばリンクの使い方',
    lead: '声・口の動き・手話・文字のどれで話しても、相手には相手が選んだ形（字幕や読み上げ）で届くビデオ会話です。アプリのインストールは不要で、スマホやPCのブラウザで開くだけで使えます。',
    back: '入室画面へ戻る',
    sections: [
      {
        heading: '1. 会話を始める',
        items: [
          {
            title: 'ルームを作る',
            body: 'トップページで「新規ルームを作成」を選び、ルームID（半角英数字とハイフンで3〜32文字）とパスワード（8文字以上）を決めて「ルームを作成して参加」を押します。',
          },
          {
            title: '相手を招待する',
            body: '会話画面の「招待リンクをコピー」で相手にリンクを送り、パスワードは別に伝えます。1つのルームには4人まで入れます。',
          },
          {
            title: '招待されたとき',
            body: 'リンクを開くとルームIDが入った状態になります。「既存ルームに参加」でパスワードを入れ、「会話に参加」を押します。名前は空欄でもかまいません。',
          },
          {
            title: 'モードを選ぶ',
            body: '標準モード・視覚サポート（見えにくい方向け）・聴覚サポート（聞こえにくい方向け）から選びます。入室後も設定を変えられます。',
          },
        ],
      },
      {
        heading: '2. 話す（入力方法）',
        items: [
          {
            title: '声',
            body: 'マイクに向かって話すだけです。話している途中から、相手の画面に字幕が出ます。',
          },
          {
            title: '口の動き（読唇）',
            body: '口元を明るく正面から映し、「読唇の撮影を開始」を押してから声を出さずに口を動かします。AIが候補を出すので、確かめてから送ります。違っていたら別の候補を選ぶか、文字で直して送ります。日本語は決まった言葉（こんにちは、ありがとうなど10語）に対応し、英語に切り替えると自由な文を書き起こせます。',
          },
          {
            title: '手話',
            body: '両手と上半身が映る位置にカメラを置き、「手話の撮影を開始」を押してから手話をします。読唇と同じく、候補を確かめてから送ります。いまは英語の手話（ASL）で自由な文を書き起こせます。日本手話は学習中で、選べない間は「モデル未導入」と表示されます。',
          },
          {
            title: '文字',
            body: '入力欄に打って送ります。どの入力方法を選んでいても、いつでも文字で送れます。',
          },
        ],
      },
      {
        heading: '3. 受け取る',
        items: [
          { title: '字幕のみ', body: '相手の発言を字幕で読みます。' },
          {
            title: '字幕＋AI読み上げ',
            body: '相手の発言を、字幕と端末の合成音声の両方で受け取ります。',
          },
          {
            title: '字幕＋通常音声',
            body: '声の発言は相手の声のまま聞き、文字・読唇・手話の発言は合成音声で読み上げます。',
          },
        ],
      },
      {
        heading: '4. うまくいかないとき',
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
          {
            title: '読唇・手話の候補が違う',
            body: '読唇・手話の認識は、なめらかな文でも意味が違うことがあります。そのため自動では送らず、必ず本人が確かめてから送る仕組みにしています。',
          },
        ],
      },
    ],
  },
  en: {
    title: 'How to use Kotoba Link',
    lead: 'A video conversation where you can talk by voice, lip movement, sign or text, and the others receive it the way they chose (captions or reading aloud). No app to install: open it in a phone or PC browser.',
    back: 'Back to the join page',
    sections: [
      {
        heading: '1. Start a conversation',
        items: [
          {
            title: 'Create a room',
            body: 'On the top page choose "Create a room", set a room ID (3–32 letters, digits or hyphens) and a password (8 characters or more), and press "Create and join".',
          },
          {
            title: 'Invite others',
            body: 'In the conversation, use "Copy invite link" to send the link, and tell the password separately. A room holds up to 4 people.',
          },
          {
            title: 'When invited',
            body: 'The link fills in the room ID. Choose "Join a room", enter the password and press "Join conversation". The name is optional.',
          },
          {
            title: 'Choose a mode',
            body: 'Standard, Vision support (for people with low vision) or Hearing support (for people who are hard of hearing). You can change settings after joining.',
          },
        ],
      },
      {
        heading: '2. Speak (input)',
        items: [
          {
            title: 'Voice',
            body: 'Just talk. Captions appear on the other screens while you are still speaking.',
          },
          {
            title: 'Lip movement (lipreading)',
            body: 'Light your mouth from the front, press "Capture lip reading" and move your lips without voice. The AI shows candidates; check one before sending, pick another, or fix it as text. Japanese covers 10 set phrases; switch to English to transcribe free sentences.',
          },
          {
            title: 'Sign',
            body: 'Place the camera so both hands and your upper body are visible, press "Capture sign language" and sign. As with lipreading, check the candidate before sending. English sign (ASL) is transcribed as free sentences; Japanese Sign Language is still being trained and shows "Model not installed" until it is ready.',
          },
          { title: 'Text', body: 'Type and send. You can always send text, whatever input you chose.' },
        ],
      },
      {
        heading: '3. Receive',
        items: [
          { title: 'Captions only', body: 'Read what others say as captions.' },
          {
            title: 'Captions + AI voice',
            body: 'Get every message as captions and as the device’s synthesized voice.',
          },
          {
            title: 'Captions + original audio',
            body: 'Hear spoken messages in the speaker’s own voice; text, lipread and sign messages are read aloud.',
          },
        ],
      },
      {
        heading: '4. Troubleshooting',
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
          {
            title: 'Wrong lipreading or sign candidate',
            body: 'Recognition can produce a fluent sentence with the wrong meaning, so nothing is sent automatically: you always check it first.',
          },
        ],
      },
    ],
  },
};

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
      {g.sections.map((s) => (
        <section key={s.heading} className="guide-section">
          <h2>{s.heading}</h2>
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
        </section>
      ))}
      <SiteFooter onGuide />
    </main>
  );
}
