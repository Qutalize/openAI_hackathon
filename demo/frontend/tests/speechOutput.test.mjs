import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/services/speechOutput.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText;
const { SpeechOutput } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
let spoken, readings, statuses, output, engine;
const msg = (id, source = 'text', revision = 1, text = id) => ({
  utterance_id: id,
  participant_id: 'other',
  display_name: '相手',
  source,
  revision,
  text,
});
beforeEach(() => {
  spoken = [];
  readings = [];
  statuses = [];
  globalThis.window = globalThis;
  globalThis.SpeechSynthesisUtterance = class {
    constructor(text) {
      this.text = text;
    }
  };
  engine = globalThis.speechSynthesis = {
    getVoices: () => [{ lang: 'ja-JP' }],
    speak: (u) => spoken.push(u),
    cancel: () => spoken.at(-1)?.onerror?.({ error: 'canceled' }),
    pause: () => {},
    resume: () => {},
  };
  output = new SpeechOutput(
    'self',
    { tts_lang: 'ja-JP', tts_rate: 1, tts_queue_limit: 10 },
    (s) => statuses.push(s),
    (id) => readings.push(id),
  );
});

test('original audio skips speech but reads other input methods in order', () => {
  output.utterance(msg('voice', 'speech'), 'v');
  for (const kind of ['text', 'sign', 'lipread']) output.utterance(msg(kind, kind), kind);
  assert.equal(spoken.length, 1);
  spoken[0].onstart();
  spoken[0].onend();
  spoken[1].onend();
  assert.deepEqual(
    spoken.map((u) => u.text),
    ['相手。text', '相手。sign', '相手。lipread'],
  );
  assert.deepEqual(readings.slice(0, 2), ['text', null]);
});
test('AI voice includes speech, ignores own/replayed/duplicate messages, and highlights only on start', () => {
  output.setMode('ai');
  output.utterance(msg('a', 'speech'), 'a');
  output.utterance(msg('a', 'speech'), 'a-again');
  output.utterance({ ...msg('own'), participant_id: 'self' }, 'own');
  output.utterance({ ...msg('replay'), replayed: true }, 'replay');
  assert.equal(spoken.length, 1);
  assert.equal(readings.at(-1), null);
  spoken[0].onstart();
  assert.equal(readings.at(-1), 'a');
  spoken[0].onend();
  assert.equal(readings.at(-1), null);
});
test('captions and switching modes cancel all audio and ignore stale callbacks', () => {
  output.setMode('ai');
  output.utterance(msg('first'), '1');
  spoken[0].onstart();
  output.utterance(msg('queued'), '2');
  const old = spoken[0];
  output.setMode('captions');
  old.onend();
  old.onstart();
  old.onerror();
  output.speak('notification');
  output.replayUnread();
  output.utterance(msg('silent'), '3');
  assert.equal(spoken.length, 1);
  assert.equal(readings.at(-1), null);
  output.setMode('ai');
  output.utterance(msg('silent'), '4');
  assert.equal(spoken.length, 1);
});
test('corrections replace queued text and stop an obsolete active revision', () => {
  output.setMode('ai');
  output.utterance(msg('a'), 'a');
  spoken[0].onstart();
  output.utterance(msg('b'), 'b');
  output.utterance(msg('b', 'text', 2, 'new b'), 'b2', true);
  spoken[0].onend();
  assert.equal(spoken[1].text, '相手。new b');
  spoken[1].onstart();
  output.utterance(msg('b', 'text', 3, 'newest b'), 'b3', true);
  assert.equal(spoken[2].text, '訂正。相手。newest b');
  spoken[1].onend();
  spoken[2].onstart();
  assert.equal(readings.at(-1), 'b');
  output.utterance(msg('b', 'text', 2, 'stale'), 'stale', true);
  assert.equal(spoken.length, 3);
});
test('live speaking pauses original mode but does not block AI mode', () => {
  output.pauseWhileSpeaking(true);
  output.utterance(msg('a'), 'a');
  assert.equal(spoken.length, 0);
  output.pauseWhileSpeaking(false);
  spoken[0].onstart();
  assert.equal(readings.at(-1), 'a');
  output.pauseWhileSpeaking(true);
  assert.equal(readings.at(-1), null);
  output.pauseWhileSpeaking(false);
  assert.equal(readings.at(-1), 'a');
  output.setMode('ai');
  output.pauseWhileSpeaking(true);
  output.utterance(msg('b', 'speech'), 'b');
  assert.equal(spoken.length, 2);
});
test('unavailable voice and playback errors leave no reading indicator and can retry unread', () => {
  engine.getVoices = () => [];
  output.utterance(msg('a'), 'a');
  assert.equal(spoken.length, 0);
  assert.match(statuses.at(-1), /音声がありません/);
  engine.getVoices = () => [{ lang: 'ja-JP' }];
  output.utterance(msg('b'), 'b');
  spoken[0].onstart();
  spoken[0].onerror();
  assert.equal(readings.at(-1), null);
  assert.match(statuses.at(-1), /音声を再生できません/);
  output.replayUnread();
  assert.equal(spoken.length, 2);
  assert.equal(spoken[1].text, '相手。b');
});
