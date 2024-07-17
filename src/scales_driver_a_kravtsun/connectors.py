import asyncio
from abc import ABC, abstractmethod

from serial_asyncio import open_serial_connection


class Connector(ABC):
    """
    Interface for connecting to scales.
    """

    def __init__(self, url: str):
        self.url = url
        self.reader = self.writer = None

    @abstractmethod
    async def _open_connection(self) -> (
            tuple[asyncio.StreamReader, asyncio.StreamWriter]):
        pass

    async def _reconnect(self) -> None:
        await self._close_connection()
        try:
            self.reader, self.writer = await self._open_connection()
        except OSError as err:
            raise ConnectionError(err)
        # self.writer.transport.serial.timeout = 0.005

    async def _close_connection(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except OSError:
                pass
            self.reader = self.writer = None

    async def read(self, data_len: int) -> bytes:
        if self.reader is None:
            await self._reconnect()
        try:
            return await asyncio.wait_for(self.reader.readexactly(data_len), 2)
        except TimeoutError:
            raise ConnectionError('Timed out waiting for data')
        except OSError as err:
            await self._close_connection()
            raise ConnectionError(err)

    async def write(self, data: bytes) -> None:
        try:
            if self.writer is None:
                await self._reconnect()
            self.writer.write(data)
            await self.writer.drain()
        except OSError as err:
            self.reader = self.writer = None
            raise ConnectionError(err)


class SerialConnector(Connector):
    # def __init__(self,
    #              port: str,
    #              baud_rate: int,
    #              bytesize: int,
    #              parity: str,
    #              stop_bits: int,
    #              timeout: float):
    #     self.port = port
    #     self.baud_rate = baud_rate
    #     self.bytesize = bytesize
    #     self.parity = parity
    #     self.stop_bits = stop_bits
    #     self.timeout = timeout
    #     self.reader = None
    #     self.writer = None

    async def _open_connection(self) -> (
            tuple[asyncio.StreamReader, asyncio.StreamWriter]):
        reader, writer = await open_serial_connection(url=self.url)
        return reader, writer


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

    async def _open_connection(self) -> (
            tuple[asyncio.StreamReader, asyncio.StreamWriter]):
        return await asyncio.open_connection(self.host, self.port)
