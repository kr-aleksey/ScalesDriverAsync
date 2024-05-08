from abc import ABC, abstractmethod

from serial.serialutil import SerialException
from serial_asyncio import open_serial_connection


class Connector(ABC):
    """
    Interface for connecting to scales.
    """

    # @abstractmethod
    async def connect(self) -> int:
        """
        Establishes a connection with the scale.
        """

    # @abstractmethod
    # def disconnect(self) -> None:
    #     """
    #     Closes the connection to the scale.
    #     """

    @abstractmethod
    async def read(self, data_len: None | int = None) -> bytes:
        """
        Reading data from scales.
        :param data_len: Length of data read in bytes.
        """

    @abstractmethod
    async def write(self, data: bytes) -> int:
        """
        Writing data to the scale.
        """


class SerialConnector(Connector):
    def __init__(self,
                 port: str,
                 baud_rate: int,
                 bytesize: int,
                 parity: str,
                 stop_bits: int,
                 timeout: float):
        self.port = port
        self.baud_rate = baud_rate
        self.bytesize = bytesize
        self.parity = parity
        self.stop_bits = stop_bits
        self.timeout = timeout
        self.reader = None
        self.writer = None

    async def connect(self) -> None:
        self.reader, self.writer = await (
            open_serial_connection(
                url=self.port
            )
        )
        self.writer.transport.serial.timeout = self.timeout

    async def read(self, data_len: None | int = None) -> bytes:
        try:
            data = await self.reader.read(data_len)
        except SerialException:
            # await self.connect()
            data = None
        return data

    async def write(self, data: bytes) -> None:
        self.writer.write(data)
