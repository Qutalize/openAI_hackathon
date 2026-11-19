from app.inference.preprocessing import pack_frames


def clip(hand_frames: int, total: int = 96):
    """A sign clip with both shoulders in view and one hand visible only in the first frames."""
    frames = []
    for n in range(total):
        frame = [[0.0, 0.0, 0.0, 0.0] for _ in range(100)]
        for i in (53, 54):
            frame[i] = [0.1, 0.1, 0.0, 1.0]
        if n < hand_frames:
            for i in range(21):
                frame[i] = [0.2, 0.3, 0.0, 1.0]
        frames.append(frame)
    return frames, [n * 50.0 for n in range(total)]


def test_sign_keeps_frames_with_lowered_hands():
    # The hands are in view for under a third of the clip, as with a short sign framed by lowered hands.
    _, mask, ratio = pack_frames(*clip(30), 96, "sign")
    assert ratio == 1.0
    assert mask.sum() == 96


def test_sign_without_hands_is_rejected():
    _, _, ratio = pack_frames(*clip(5), 96, "sign")
    assert ratio == 0.0
