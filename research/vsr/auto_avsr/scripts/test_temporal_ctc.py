"""全経路列挙と独立比較するCTC検証（学習済みモデル・torchは不要）。"""

import itertools
import unittest

import numpy as np

from temporal_ctc import ctc_log_probability, forced_align


def collapse(path, blank):
    return tuple(token for index, token in enumerate(path)
                 if token != blank and (index == 0 or token != path[index - 1]))


def enumerate_scores(log_probs, blank):
    sums, maxima = {}, {}
    for path in itertools.product(range(log_probs.shape[1]), repeat=len(log_probs)):
        target = collapse(path, blank)
        score = sum(log_probs[time, token] for time, token in enumerate(path))
        sums[target] = np.logaddexp(sums.get(target, -np.inf), score)
        maxima[target] = max(maxima.get(target, -np.inf), score)
    return sums, maxima


class TemporalCTCTest(unittest.TestCase):
    def test_exhaustive_all_paths(self):
        rng = np.random.default_rng(20260912)
        for blank in (0, 2):
            alphabet = [token for token in range(3) if token != blank]
            targets = [target for length in range(4)
                       for target in itertools.product(alphabet, repeat=length)]
            for frames in range(6):
                probabilities = rng.uniform(0.01, 1, (frames, 3))
                probabilities /= probabilities.sum(axis=1, keepdims=True)
                log_probs = np.log(probabilities)
                sums, maxima = enumerate_scores(log_probs, blank)
                for target in targets:
                    with self.subTest(blank=blank, frames=frames, target=target):
                        result = forced_align(log_probs, target, blank)
                        expected_sum = sums.get(target, -np.inf)
                        expected_max = maxima.get(target, -np.inf)
                        self.assertAlmostEqual(ctc_log_probability(log_probs, target, blank), expected_sum)
                        self.assertAlmostEqual(result["log_score"], expected_max)
                        if not np.isfinite(expected_max):
                            self.assertEqual(result["state_path"], [])
                            self.assertEqual(result["token_spans"], [])
                            continue
                        states = [blank]
                        for token in target:
                            states.extend([token, blank])
                        path = result["state_path"]
                        emissions = [states[state] for state in path]
                        self.assertEqual(collapse(emissions, blank), target)
                        self.assertAlmostEqual(sum(log_probs[t, token] for t, token in enumerate(emissions)), expected_max)
                        self.assertEqual(len(result["token_spans"]), len(target))
                        for span in result["token_spans"]:
                            expected_frames = [t for t, state in enumerate(path)
                                               if state == 2 * span["token_index"] + 1]
                            self.assertEqual(expected_frames, list(range(span["start_frame"], span["end_frame"])))

    def test_repeated_token_needs_blank(self):
        log_probs = np.log([[0.05, 0.95], [0.9, 0.1], [0.05, 0.95]])
        result = forced_align(log_probs, [1, 1])
        self.assertEqual(result["state_path"], [1, 2, 3])
        self.assertEqual([(span["start_frame"], span["end_frame"]) for span in result["token_spans"]], [(0, 1), (2, 3)])
        self.assertEqual(ctc_log_probability(log_probs[:2], [1, 1]), -np.inf)

    def test_zero_probability_and_empty_target(self):
        log_probs = np.array([[-np.inf, 0.0], [0.0, -np.inf]])
        self.assertEqual(ctc_log_probability(log_probs, [1]), 0.0)
        self.assertEqual(forced_align(log_probs, [1])["log_score"], 0.0)
        self.assertEqual(forced_align(log_probs, [])["log_score"], -np.inf)
        self.assertEqual(ctc_log_probability(np.log([[0.2, 0.8], [0.3, 0.7]]), []), np.log(0.2) + np.log(0.3))

    def test_long_sequence_numerical_stability(self):
        log_probs = np.log(np.full((10000, 2), 0.5))
        self.assertAlmostEqual(ctc_log_probability(log_probs, []), 10000 * np.log(0.5), places=7)

    def test_invalid_inputs(self):
        for scores, targets, blank in [([0.0], [], 0), ([[np.nan, 0.0]], [1], 0),
                                       ([[np.inf, 0.0]], [1], 0), ([[0.0, 0.0]], [0], 0),
                                       ([[0.0, 0.0]], [2], 0), ([[0.0, 0.0]], [1.5], 0),
                                       ([[0.0, 0.0]], [1], 2)]:
            for function in (ctc_log_probability, forced_align):
                with self.assertRaises(ValueError):
                    function(scores, targets, blank)


if __name__ == "__main__":
    unittest.main()
