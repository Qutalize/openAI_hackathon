"""NumPyのみでCTCの系列確率と単調forced alignmentを計算する。

GTをtarget_idsへ指定した結果は、そのGTを必ず出力するという拘束の下で
最も高いスコアになる仮説であり、真の発話時刻（時間GT）ではない。
encoderが時間方向の文脈を混合する場合、tokenのframeも局所的な口形の
因果的根拠を意味しない。入力は自然対数のlog_probs[T, V]。
"""

from __future__ import annotations

import numpy as np


def _prepare(log_probs, target_ids, blank):
    scores = np.asarray(log_probs, dtype=np.float64)
    if scores.ndim != 2 or scores.shape[1] == 0:
        raise ValueError("log_probs must have shape [T, V] with V > 0")
    if np.isnan(scores).any() or np.isposinf(scores).any():
        raise ValueError("log_probs must not contain NaN or positive infinity")
    if not isinstance(blank, (int, np.integer)) or not 0 <= blank < scores.shape[1]:
        raise ValueError("blank must be a valid vocabulary index")
    targets = list(target_ids)
    if any(not isinstance(token, (int, np.integer)) for token in targets):
        raise ValueError("target_ids must contain integer token IDs")
    if any(token < 0 or token >= scores.shape[1] or token == blank for token in targets):
        raise ValueError("target IDs must be valid non-blank vocabulary indices")
    states = np.full(2 * len(targets) + 1, blank, dtype=np.int64)
    states[1::2] = targets
    # 2状態先への遷移は、blankでも直前と同じtokenでもない場合のみ許す。
    can_skip = np.zeros(len(states), dtype=bool)
    can_skip[2:] = (states[2:] != blank) & (states[2:] != states[:-2])
    return scores, targets, states, can_skip


def ctc_log_probability(log_probs, target_ids, blank=0) -> float:
    """targetにcollapseする全CTC経路の確率の和を自然対数で返す。

    空系列の確率も定義する。到達不能なら-inf。系列長の異なる値は
    長さの影響を受けるため、認識正答率や校正済み信頼度とは扱わない。
    """
    scores, targets, states, can_skip = _prepare(log_probs, target_ids, blank)
    if len(scores) == 0:
        return 0.0 if not targets else float("-inf")
    previous = np.full(len(states), -np.inf)
    previous[0] = scores[0, blank]
    if targets:
        previous[1] = scores[0, targets[0]]
    for emissions in scores[1:]:
        current = previous.copy()
        current[1:] = np.logaddexp(current[1:], previous[:-1])
        skip = np.where(can_skip[2:], previous[:-2], -np.inf)
        current[2:] = np.logaddexp(current[2:], skip)
        previous = current + emissions[states]
    return float(np.logaddexp(previous[-1], previous[-2])) if targets else float(previous[0])


def forced_align(log_probs, target_ids, blank=0) -> dict:
    """最大確率のCTC経路とtarget tokenごとのframe区間を返す。

    戻り値: log_score（単一経路の自然対数確率）, token_spans,
    state_path。token_spansのstart_frameはinclusive、end_frameはexclusive。
    state_pathはblankを挟んだ拡張系列の状態index（token IDではない）。
    token間のblank frameは区間に含めない。同点ではstay, +1, +2の順に
    遷移を優先し、終端では最後のblankを優先する。
    到達不能ならlog_score=-inf、token_spansとstate_pathは空。
    GTで拘束した単調仮説であり、真の時間GTや因果的説明ではない。
    """
    scores, targets, states, can_skip = _prepare(log_probs, target_ids, blank)
    impossible = {"log_score": float("-inf"), "token_spans": [], "state_path": []}
    if len(scores) == 0:
        return {**impossible, "log_score": 0.0} if not targets else impossible
    previous = np.full(len(states), -np.inf)
    previous[0] = scores[0, blank]
    if targets:
        previous[1] = scores[0, targets[0]]
    backpointers = np.zeros((len(scores), len(states)), dtype=np.int8)
    for time, emissions in enumerate(scores[1:], start=1):
        candidates = np.full((3, len(states)), -np.inf)
        candidates[0] = previous
        candidates[1, 1:] = previous[:-1]
        candidates[2, 2:] = np.where(can_skip[2:], previous[:-2], -np.inf)
        choices = candidates.argmax(axis=0)
        backpointers[time] = choices
        previous = candidates[choices, np.arange(len(states))] + emissions[states]
    state = len(states) - 1
    if targets and previous[-2] > previous[-1]:
        state -= 1
    log_score = float(previous[state])
    if np.isneginf(log_score):
        return impossible
    path = np.empty(len(scores), dtype=np.int64)
    for time in range(len(scores) - 1, -1, -1):
        path[time] = state
        if time:
            state -= int(backpointers[time, state])
    spans = []
    for index, token in enumerate(targets):
        frames = np.flatnonzero(path == 2 * index + 1)
        spans.append({"token_index": index, "token_id": int(token),
                      "start_frame": int(frames[0]), "end_frame": int(frames[-1]) + 1})
    return {"log_score": log_score, "token_spans": spans, "state_path": path.tolist()}
