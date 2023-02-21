from asyncio import Queue
from abc import abstractmethod, ABC
from threading import Thread, Event


class ImageDetectorInitializationFailed(Exception):
    pass


class ImageDetector(Thread, ABC):
    """
    The base class for NetApps based on image processing. Provides abstract
    methods for processing images and publishing results. It is based on Threads.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.stop_event = Event()
        self.time = None
        self.fps = 0.0

    def stop(self):
        self.stop_event.set()

    @abstractmethod
    def run(self):
        """
        This method is run once the thread is started and could be used e.g.
        for periodical retrieval of images.
        """

        pass

    @abstractmethod
    def process_image(self, frame):
        """
        This method is responsible for processing of passed image.

        Args:
            frame (_type_): Image to be processed

        Raises:
            NotImplemented
        """

        pass

    @abstractmethod
    def publish_results(self, **kw):
        """
        This method is responsible for returning results back to the robot. 

        Args:
            data (_type_): The results to be returned to the robot. The format is
                NetApp-specific.

        Raises:
            NotImplemented
        """

        pass
        