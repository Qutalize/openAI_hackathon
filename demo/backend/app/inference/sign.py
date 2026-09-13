from app.inference.lipread import TemporalRecognizer


class SignRecognizer(TemporalRecognizer):
    """Shares the temporal runtime, with a sign100_v1 input contract."""

    def __init__(self, path, metadata_path, config, vocabulary):
        super().__init__(path, metadata_path, config, "sign", vocabulary)
