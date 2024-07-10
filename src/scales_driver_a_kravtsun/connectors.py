import asyncio
from abc import ABC, abstractmethod

from serial.serialutil import SerialException
from serial_asyncio import open_serial_connection


class Connector(ABC):
    """
    Interface for connecting to scales.
    """

    def __init__(self, url: str):
        self.url = url
        self.reader = self.writer = None

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


class SocketConnector(Connector):

    def __init__(self, url: str):
        super().__init__(url)
        try:
            self.host, self.port = url.split(':')
        except ValueError:
            raise ConnectionError(
                f'Invalid url "{url}". {__class__.__name__} expects '
                f'a URL in the format <host:port>.'
            )

    async def read(self, data_len: None | int = None) -> bytes:
        try:
            if self.reader is None:
                await self.connect()
            data = await asyncio.wait_for(self.reader.read(data_len), 2)
            return data
        except ConnectionError as err:
            self.reader = self.writer = None
            raise err
        except TimeoutError:
            raise ConnectionError('Timed out waiting for data')

    async def write(self, data: bytes) -> None:
        try:
            if self.writer is None:
                await self.connect()
            self.writer.write(data)
            await self.writer.drain()
        except (ConnectionError, OSError )as err:
            self.reader = self.writer = None
            raise err

    async def connect(self) -> None:
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port)
        except OSError as err:
            raise ConnectionError(err)