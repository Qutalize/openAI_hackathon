import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

export type Locale = 'ja' | 'en';
const english: Record<string, string> = {
  字幕のみ: 'Captions only',
  '字幕＋AI読み上げ': 'Captions + AI voice',
  '字幕＋通常音声': 'Captions + original audio',
  発話中: 'Speaking',
  認識中: 'Recognizing',
  読み上げ中: 'Reading aloud',
  読み上げ一時停止中: 'Reading paused',
  参加者と発話者の映像サイズ: 'Participant and speaker video size',
  '{name}のユーザーアイコン': 'Avatar of {name}',
  アイコン画像を選択: 'Choose avatar image',
  画像を選択: 'Choose image',
  アイコンを削除: 'Remove avatar',
  'PNG・JPEG・WebP / 5MBまで。中央を正方形に切り抜きます。':
    'PNG, JPEG or WebP, up to 5 MB. Cropped to a square from the center.',
  '5MB以下のPNG・JPEG・WebP画像を選択してください': 'Choose a PNG, JPEG or WebP image up to 5 MB.',
  '画像を読み込めません。別の画像を選択してください': 'Could not read the image. Choose another image.',
  'アイコン画像が不正です。画像を選び直してください': 'Invalid avatar image. Choose the image again.',
  認識接続を開始できません: 'Could not connect to recognition',
  '認識接続が混雑しています。区間をやり直してください': 'Recognition is busy. Please capture again.',
  '特徴点モデルを開始できません。モデル準備とカメラを確認してください':
    'Could not start the landmark model. Check the model setup and camera.',
  通話接続設定の更新に失敗しました: 'Could not refresh the call connection settings',
  '日本語の読み上げ音声を確認できません。OSの音声設定を確認するか「文字表示で参加」を選んでください':
    'A Japanese reading voice is unavailable. Check your system voice settings or choose Join with text.',
  '接続が切れました。再接続後に操作してください': 'Disconnected. Try again after reconnection.',
  接続の完了をお待ちください: 'Please wait for the connection',
  操作がタイムアウトしました: 'The operation timed out',
  会話を終了しました: 'The conversation ended',
  特徴点モデルの開始がタイムアウトしました: 'Loading the landmark model timed out',
  撮影を取り消しました: 'Capture cancelled',
  特徴点モデルを読み込めません: 'Could not load the landmark model',
  '試行回数が多いため、1分後に再試行してください': 'Too many attempts. Try again in one minute.',
  'セッションが切れました。再入室してください': 'Your session expired. Please rejoin.',
  このルームには参加していません: 'You have not joined this room',
  このモードでは利用できない入力方式です: 'This input method is unavailable in the selected mode',
  撮影区間が期限切れです: 'The capture session expired',
  '文字出力はOFFです。下の出力設定で文字を選択すると表示できます。':
    'Text output is off. Select Text in the output settings below to see the transcript.',
  '登録表現のみ対応：': 'Supported phrases: ',
  '。認識候補を確認して送信します。': '. Review recognition results before sending.',
  ことばリンク: 'Kotoba Link',
  会話中: 'In a meeting',
  表示言語: 'Display language',
  'それぞれの伝え方で、ひとつの会話を。': 'Different ways to express. One conversation.',
  '発声・読唇・手話に対応可能な会話アプリ': 'Connect through speech, lip reading, sign language and text',
  既存ルームに参加: 'Join a room',
  新規ルームを作成: 'Create a room',
  標準モード: 'Standard',
  視覚サポート: 'Vision support',
  聴覚サポート: 'Hearing support',
  発声: 'Speech',
  読唇: 'Lip reading',
  手話: 'Sign language',
  文字入力: 'Text input',
  入力: 'Input',
  出力: 'Output',
  入力方法: 'Input method',
  音声: 'Audio',
  文字: 'Text',
  '音声＋文字': 'Audio + text',
  '発声・読唇': 'Speech / lip reading',
  '音声・文字': 'Audio / text',
  ルームの操作: 'Room actions',
  利用モードを選択: 'Choose your mode',
  ルームID: 'Room ID',
  パスワード: 'Password',
  パスワードを表示: 'Show password',
  名前: 'Name',
  名前を変更: 'Change name',
  表示名: 'Display name',
  名前を保存: 'Save name',
  '任意・40文字まで': 'Optional, up to 40 characters',
  自分: 'You',
  ルーム: 'Room',
  会話に参加: 'Join conversation',
  ルームを作成して参加: 'Create and join',
  '接続中…': 'Connecting…',
  接続中: 'Connected',
  '再接続しています…': 'Reconnecting…',
  セッションが切れました: 'Session expired',
  モデル未導入: 'Model not installed',
  '（モデル未導入）': ' (model not installed)',
  '（未導入）': ' (unavailable)',
  '文字入力で参加できます。': 'You can join using text.',
  '音声または特徴点をサーバーで認識します。': 'Speech or landmarks are processed on the server.',
  '自分のカメラは会話中にこの端末内で録画されます。':
    'Your camera is recorded locally on this device during the conversation.',
  登録表現のみ対応: 'Supported phrases only',
  '認識候補を確認して送信します。': 'Review recognition results before sending.',
  '作成済みのルームIDとパスワードを入力してください。': 'Enter the ID and password of an existing room.',
  'ルームIDは半角英数字・ハイフンの3〜32文字、パスワードは8〜128文字で設定してください。作成後、そのまま参加します。':
    'Use 3–32 letters, numbers or hyphens for the room ID and 8–128 characters for the password. You will join after creation.',
  '相手も同じルームIDとパスワードで参加できます。作成した方から相手に伝えてください。':
    'Share the room ID and password with the other participants.',
  'ルーム「{room}」を作成しました。有効期限：{date}。参加できない場合は、同じIDとパスワードで再試行してください。':
    'Room “{room}” was created. Expires: {date}. If joining fails, retry with the same ID and password.',
  もうすぐ会話がはじまります: 'You are almost ready',
  カメラと音声を確認: 'Check your camera and audio',
  自分のカメラプレビュー: 'Your camera preview',
  カメラはOFFです: 'Camera is off',
  カメラ: 'Camera',
  マイク: 'Mic',
  カメラをON: 'Turn camera ON',
  カメラをOFF: 'Turn camera OFF',
  マイクをON: 'Turn microphone ON',
  マイクをOFF: 'Turn microphone OFF',
  '機器をONにすると、ブラウザから利用許可を求められます。':
    'Your browser will request permission when you turn on a device.',
  会話を開始: 'Start conversation',
  文字表示で参加: 'Join with text',
  参加を中止: 'Cancel joining',
  '会話開始後、カメラがONの間は自分の映像だけを録画します。カメラOFFで録画を停止し、会話終了時に端末へ保存します。':
    'After joining, only your own camera video is recorded while it is on. Recording stops when the camera is off and is saved to this device when you leave.',
  会話画面: 'Conversation',
  会話の操作: 'Meeting controls',
  参加者: 'People',
  '{count}人': '{count}',
  会話終了: 'Leave',
  入室画面へ戻る: 'Back to joining',
  閉じる: 'Close',
  取消: 'Cancel',
  '保存中…': 'Saving…',
  通知を閉じる: 'Dismiss notification',
  この入力方式ではマイクを使用しません: 'The microphone is not used for this input method',
  参加者の映像: 'Participant videos',
  '{name}の映像を固定': 'Pin {name}',
  '{name}のカメラ': 'Camera of {name}',
  発話者映像: 'Speaker video',
  '{name}の発話者映像': 'Speaker video of {name}',
  会話の準備ができました: 'Ready to talk',
  参加者を待っています: 'Waiting for participants',
  固定表示: 'Pinned',
  自動表示へ: 'Unpin',
  ユーザーアイコン: 'User avatar',
  文字おこし: 'Transcript',
  '会話がはじまると、ここに言葉が並びます。': 'Your conversation will appear here.',
  発言の修正: 'Edit your message',
  修正を送信: 'Save correction',
  修正済み: 'Edited',
  修正: 'Edit',
  '最新へ ↓': 'Latest ↓',
  発言入力: 'Message input',
  文字で伝える: 'Type a message',
  '伝えたいことを入力…': 'Type your message…',
  送信中: 'Sending',
  送信: 'Send',
  '認識結果を確認・修正': 'Review recognition result',
  文字入力として送信する: 'Send as typed text',
  '口元を明るく、正面から映してください。': 'Face the camera with your mouth well lit.',
  '両手と上半身が映る位置にカメラを置いてください。': 'Keep both hands and your upper body in view.',
  撮影を終了して認識: 'Finish capture',
  '認識しています…': 'Recognizing…',
  読唇の撮影を開始: 'Capture lip reading',
  手話の撮影を開始: 'Capture sign language',
  対応する登録表現: 'Supported phrases',
  '候補の期限が切れました。文字入力として送信できます。':
    'This suggestion expired. You can still send it as text.',
  候補を確認して送信してください: 'Review the suggestion before sending',
  認識できませんでした: 'Could not recognize this input',
  音声を開始: 'Start audio',
  読み上げ停止: 'Stop reading',
  未読を再生: 'Read unread',
  '音声・操作の設定': 'Audio and controls',
  '参加・接続の通知を読み上げる': 'Read participant and connection notifications',
  ショートカットを有効にする: 'Enable keyboard shortcuts',
  映像と文字おこしのサイズ: 'Video and transcript size',
  映像の幅: 'Video width',
  録画待機: 'Recording ready',
  自分のカメラを録画中: 'Recording your camera',
  録画を保存: 'Save recording',
  録画を保存しました: 'Recording saved',
  '録画を開始できません。このブラウザは録画に対応していません。':
    'This browser does not support camera recording.',
  '録画できませんでした。会話は続けられます。': 'Recording failed. You can continue the conversation.',
  録画を保存できませんでした: 'Could not save the recording',
  録画を保存して退出: 'Save recording and leave',
  '会話の準備をしています…': 'Preparing your conversation…',
  サーバーに接続できません: 'Cannot connect to the server',
  再試行: 'Retry',
  待機中: 'Ready',
  停止: 'Stopped',
  取消しました: 'Cancelled',
  混雑しています: 'Busy',
  認識しています: 'Recognizing',
  '撮影中。終わったら終了ボタンを押してください': 'Capturing. Press finish when ready.',
  会話から退出しました: 'You left the conversation',
  'デバイスを停止しました。接続終了後60秒で参加枠が解放されます。':
    'Devices stopped. Your place in the room will be released in 60 seconds.',
  入力内容またはサーバー接続を確認してください: 'Check your input or server connection',
  'その名前は参加者が使用しています。別の名前を入力してください':
    'That name is already in use. Choose another name.',
  '名前は制御文字を含まない1〜40文字で入力してください':
    'Use 1–40 characters without control characters for your name.',
  ルームIDまたはパスワードを確認してください: 'Check the room ID and password',
  'このルームIDは既に使われています。別のIDで作成するか、既存ルームに参加してください':
    'This room ID is already in use. Choose another ID or join the existing room.',
  ルームが満員です: 'This room is full',
  '選択したモデルは未導入です。文字入力を選択してください':
    'The selected model is not installed. Choose text input.',
  '発声入力にはマイクが必要です。マイクをONにするか文字入力で参加してください':
    'Speech input requires a microphone. Turn it on or join with text.',
  選択した入力にはカメラが必要です: 'The selected input requires a camera',
  カメラをONにしてください: 'Turn your camera on',
  '権限が許可されていません。ブラウザ設定を確認するか、文字入力をご利用ください':
    'Permission was denied. Check browser settings or use text input.',
  カメラまたはマイクが見つかりません: 'No camera or microphone was found',
  'カメラ・マイクにはHTTPSまたはlocalhostが必要です': 'Camera and microphone require HTTPS or localhost',
  '機器が切断されました。再度ONにしてください': 'A device was disconnected. Turn it on again.',
  '音声を再生できません。「音声を開始」を押してください': 'Audio could not play. Press Start audio.',
  '日本語の読み上げ音声がありません。文字表示をご利用ください':
    'A Japanese voice is unavailable. Use text output.',
  '未読があります。「未読を再生」を押してください': 'Some messages are unread. Press Read unread.',
  音声再生を開始できません: 'Could not start audio playback',
  音声の準備ができました: 'Audio is ready',
  '認識接続が切れました。再接続します': 'Recognition disconnected. Reconnecting.',
  '映像・音声の再接続を試みています。字幕は利用できます':
    'Reconnecting video and audio. Captions remain available.',
  映像接続を確立できませんでした: 'Could not establish video connection',
  '映像接続が不安定です。接続を確認してください': 'Video connection is unstable. Check your connection.',
  '学習データ収集 · 会話とは別の操作です': 'Training data collection · separate from conversations',
  登録表現の特徴点を収集: 'Collect landmarks for supported phrases',
  '映像は保存・送信しません。顔・手・姿勢の特徴点を端末に保存します。本人の同意がある収録だけ行ってください。':
    'Video is not saved or sent here. Face, hand and pose landmarks are saved to this device. Only collect with the participant’s consent.',
  入力方式: 'Input method',
  日本手話: 'Japanese sign language',
  '人物ID（氏名を使用しない）': 'Subject ID (not a real name)',
  クラスID: 'Class ID',
  '本人が収集・モデル学習への使用に同意しています':
    'The participant consents to collection and model training',
  学習データ収集のプレビュー: 'Training capture preview',
  'カメラ OFF': 'Camera OFF',
  'モデルを準備中…': 'Loading model…',
  撮影を開始: 'Start capture',
  撮影を終了: 'Finish capture',
  特徴点を保存: 'Save landmarks',
  会話の入室画面へ: 'Back to joining',
  カメラを準備しました: 'Camera ready',
  'カメラを利用できません。権限を確認してください': 'Camera unavailable. Check permissions.',
  登録表現を1回行ってください: 'Perform one supported phrase',
  先に撮影してください: 'Capture first',
  '収集を停止し、未保存の特徴点を破棄しました': 'Collection stopped and unsaved landmarks discarded',
  'クラスIDはconfig/vocabulary.ja.jsonと一致させます。対象外の動作はunknownとして収集します。':
    'Class IDs must match config/vocabulary.ja.json. Use unknown for unsupported movements.',
};

export function translate(text: string, locale: Locale, values: Record<string, string | number> = {}) {
  let result = locale === 'en' ? (english[text] ?? text) : text;
  if (locale === 'en') {
    result = result.replace(/^ユーザー([A-D])$/, 'User $1');
    result = result.replace(
      /^(\d+)フレームを収集しました。「特徴点を保存」でローカルに保存できます。$/,
      '$1 frames collected. Use Save landmarks to save them locally.',
    );
  }
  return result.replace(/\{(\w+)\}/g, (match, key) => String(values[key] ?? match));
}
type I18n = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (text: string, values?: Record<string, string | number>) => string;
};
const Context = createContext<I18n>({ locale: 'ja', setLocale: () => {}, t: (text) => text });
export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    try {
      return localStorage.getItem('ui-language') === 'en' ? 'en' : 'ja';
    } catch {
      return 'ja';
    }
  });
  useEffect(() => {
    document.documentElement.lang = locale;
    try {
      localStorage.setItem('ui-language', locale);
    } catch {
      /* Private storage may be unavailable. */
    }
  }, [locale]);
  const t = useCallback(
    (text: string, values?: Record<string, string | number>) => translate(text, locale, values),
    [locale],
  );
  return <Context.Provider value={{ locale, setLocale, t }}>{children}</Context.Provider>;
}
export const useI18n = () => useContext(Context);
export function LanguageSelect() {
  const { locale, setLocale, t } = useI18n();
  return (
    <label className="language-select">
      <span className="sr-only">{t('表示言語')}</span>
      <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
        <option value="ja">日本語</option>
        <option value="en">English</option>
      </select>
    </label>
  );
}
