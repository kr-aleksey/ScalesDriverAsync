from decimal import Decimal
from abc import ABC, abstractmethod

from exeptions import ScalesError
from connectors import Connector


class ScalesDriver(ABC):
    """
    Scales driver interface.
    """
    GR = 1
    KG = 2
    LB = 3

    STABLE: int = 1
    UNSTABLE: int = 2
    OVERLOAD: int = 3

    def __init__(self, connector: Connector):
        self.connector = connector

    @abstractmethod
    async def get_info(self) -> dict:
        """Return scales info."""

    @abstractmethod
    async def get_weight(self, measure_unit: int) -> tuple[Decimal, int]:
        """Return tuple (weight, measure unit, status)."""


class CASType6(ScalesDriver):
    COMMANDS: dict[str, bytes] = {
        'ACK': b'\x06',
        'DC1': b'\x11',
        'ENQ': b'\x05',
    }
    RESPONSE_PREFIX = b'\x01\x02'
    RESPONSE_SUBFIX = b'\x03\x04'

    async def get_info(self) -> dict:
        return {}

    async def get_weight(self, measure_unit) -> tuple[Decimal, int, int]:
        await self.connector.write(self.COMMANDS['ENQ'])
        ack = await self.connector.read(1)
        if ack != self.COMMANDS['ACK']:
            expected = self.COMMANDS['ACK']
            raise ScalesError(
                f'Incorrect response received from the scale. '
                f'Expected ACK = {expected}, received: {ack!r}'
            )
        await self.connector.write(self.COMMANDS['DC1'])
        data = await self.connector.read(15)
        print(data)
        return Decimal('0'), self.GR, self.OVERLOAD

    def check_response(self, data):
        pass


class MassK1C(ScalesDriver):
    HEADER = b'\xF8\x55\xCE'

    async def get_info(self) -> dict:
        return {}

    async def send_command(self, command: bytes):
        data = self.HEADER + len(command).to_bytes(length=2) + command + b'\x00\x00'
        try:
            await self.connector.write(data)
        except ConnectionError as err:
            print(err)
            # self.writer.close()
            # await self.writer.wait_closed()
            raise err

    async def read_result(self):
        header_slice = slice(0, 3)
        len_slice = slice(3, 5)
        data_start = 5

        data: bytes = await self.connector.read(1024)
        if data[header_slice] != self.HEADER:
            raise ValueError(f'Invalid header: {data[header_slice]}')
        _len = data[len_slice]
        data_len = int.from_bytes(data[len_slice], byteorder='little')
        return data[data_start: data_start + data_len]

    async def get_weight(self, measure_unit) -> tuple[Decimal, int]:
        command = b'\xA0'
        await self.send_command(command)
        data = await self.read_result()
        weight = int.from_bytes(data[1:5], 'little', signed=True)
        #             division=response[10],
        #             stable=response[11]
        return Decimal(weight), 0
