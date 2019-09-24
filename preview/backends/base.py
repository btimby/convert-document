from abc import ABC, abstractmethod


class BaseBackend(ABC):
    extensions = []

    def __init__(self):
        pass

    @abstractmethod
    def preview(self, path, width, height):
        pass

    def check(self):
        return True
