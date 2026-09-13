from abc import ABC, abstractmethod


class Recognizer(ABC):
    @abstractmethod
    def warmup(self): ...

    @abstractmethod
    def recognize(self, segment: dict) -> dict: ...

    def close(self):
        pass
