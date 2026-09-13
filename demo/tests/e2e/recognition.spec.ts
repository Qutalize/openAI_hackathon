import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

for (const kind of ['lipread', 'sign']) test(`the real MediaPipe worker exports ${kind} features only after consent`, async ({ page }) => {
  test.setTimeout(60000);
  page.on('console', message => { if(message.type()==='error')console.log(message.text()); });
  await page.goto('/training');
  await page.getByLabel('入力方式').selectOption(kind);
  await page.getByLabel('人物ID（氏名を使用しない）').fill('test-person');
  await page.getByLabel('クラスID').fill('unknown');
  await expect(page.getByRole('button', { name: 'カメラをON' })).toBeDisabled();
  await page.getByLabel('本人が収集・モデル学習への使用に同意しています').check();
  await page.getByRole('button', { name: 'カメラをON' }).click();
  await page.getByRole('button', { name: '撮影を開始' }).click();
  await expect(page.getByRole('status')).toContainText(/フレームを収集しました|特徴点モデルを開始できません/, { timeout: 45000 });
  await expect(page.getByRole('status')).toContainText('フレームを収集しました');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '特徴点を保存' }).click();
  const saved = await download;
  const data = JSON.parse(await readFile((await saved.path())!, 'utf8'));
  expect(data.modality).toBe(kind);
  expect(data.frames.length).toBeGreaterThan(1);
  expect(data.frames[0]).toHaveLength(kind === 'lipread' ? 40 : 100);
  expect(data.frames[0][0]).toHaveLength(4);
  expect(data).not.toHaveProperty('video');
  await page.getByLabel('本人が収集・モデル学習への使用に同意しています').uncheck();
  await expect(page.getByRole('status')).toContainText('未保存の特徴点を破棄しました');
});

test('speech output skips replays and replaces an unread correction', async ({ page }) => {
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const spoken: string[] = [];
    const pending: any[] = [];
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: class {
      constructor(public text: string) {}
    }});
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
      getVoices: () => [{ lang: 'ja-JP' }],
      speak: (u: any) => { spoken.push(u.text); pending.push(u); },
      cancel: () => {}, pause: () => {}, resume: () => {},
      addEventListener: () => {}, removeEventListener: () => {},
    }});
    const modulePath = '/src/services/speechOutput.ts';
    const { SpeechOutput } = await import(modulePath);
    const output = new SpeechOutput('self', { tts_lang: 'ja-JP', tts_rate: 1, tts_queue_limit: 10 }, () => {});
    const u = { utterance_id: 'first', participant_id: 'other', display_name: 'ユーザーB', source: 'text', text: '最初', revision: 1 };
    output.utterance(u, 'event-1');
    output.utterance(u, 'event-1');
    output.utterance({ ...u, utterance_id: 'queued', text: '古い候補' }, 'event-2');
    output.utterance({ ...u, utterance_id: 'queued', text: '修正後', revision: 2 }, 'event-3', true);
    output.utterance({ ...u, utterance_id: 'old', replayed: true }, 'event-4');
    output.utterance({ ...u, utterance_id: 'own', participant_id: 'self' }, 'event-5');
    output.utterance({ ...u, utterance_id: 'speech', source: 'speech' }, 'event-6');
    pending[0].onend();
    return spoken;
  });
  expect(result).toEqual(['ユーザーB。最初', 'ユーザーB。修正後']);
});
