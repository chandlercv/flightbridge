"""Base reader abstraction"""
import abc


class DeviceReader(abc.ABC):
    @abc.abstractmethod
    def start(self):
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self):
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe(self, callback):
        raise NotImplementedError
