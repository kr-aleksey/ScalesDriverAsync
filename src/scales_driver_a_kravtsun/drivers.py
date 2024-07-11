from abc import ABC, abstractmethod
from decimal import Decimal

from connectors import Connector
from exeptions import ScalesError


class ScalesDriver(ABC):
    """
    Интерфейс драйвера весов.
    """
    # Единицы измерения веса
    UNIT_GR = 1
    UNIT_KG = 2
    UNIT_LB = 3
    # Статус весов
    STATUS_STABLE = 1
    STATUS_UNSTABLE = 2
    STATUS_OVERLOAD = 3

    def __init__(self, connector: Connector):
        """
        :param connector: экземпляр класса Connector
        """
        self.connector = connector

    @abstractmethod
    async def get_info(self) -> dict:
        """Возвращает информацию о весах."""

    @abstractmethod
    async def get_weight(self, measure_unit: int) -> tuple[Decimal, int]:
        """
        Получает показания весов. Возвращает результат кортежем (вес, статус).
        Статус может иметь значения: STATUS_STABLE, STATUS_UNSTABLE,
        STATUS_OVERLOAD.
        :param measure_unit: Единица измерения, в которой будет возвращен вес.
        """

    @staticmethod
    def to_hex(data: bytes) -> str:
        return data.hex(sep=':')



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
    """
    Драйвер весов Масса-К. Протокол "1С".
    """
    HEADER = b'\xF8\x55\xCE'
    HEADER_SLICE = slice(0, 3)
    DATA_LEN_SLICE = slice(3, 5)
    DATA_START = 5

    CMD_POLL = b'\x00'
    CMD_GET_WEIGHT = b'\xA0'

    CMD_ACK = {
        CMD_POLL: b'\x01',
        CMD_GET_WEIGHT: b'\x10',
    }

    CMD_RESPONSE_LEN = {
        CMD_POLL: 34,
        CMD_GET_WEIGHT: 14
    }

    async def get_info(self) -> dict:
        return {}

    async def exec_command(self, command: bytes) -> bytes:
        data = self.HEADER + len(command).to_bytes(
            length=2) + command + b'\x00\x00'
        await self.connector.write(data)

        data: bytes = await self.connector.read(1024)
        return self.check_response(command, data)

    def check_response(self, command: bytes, data: bytes) -> bytes:
        if len(data) != self.CMD_RESPONSE_LEN[command]:
            raise ValueError(
                f'Incorrect response received from the scale. '
                f'Received {len(data)} bytes, '
                f'expected {self.CMD_RESPONSE_LEN[command]} bytes'
            )
        if data[self.HEADER_SLICE] != self.HEADER:
            raise ValueError(
                f'Incorrect response received from the scale. '
                f'Invalid header: {self.to_hex(data[self.HEADER_SLICE])}, '
                f'expected: {self.to_hex(self.HEADER)}')
        ack = data[self.DATA_START: self.DATA_START + 1]
        if ack != self.CMD_ACK[command]:
            raise ValueError(
                f'Incorrect response received from the scale. '
                f'Invalid ACK: {self.to_hex(ack)}, '
                f'expected: {self.to_hex(self.CMD_ACK[command])}'
            )

        data_len = int.from_bytes(
            data[self.DATA_LEN_SLICE], byteorder='little')
        return data[self.DATA_START + 1: self.DATA_START + data_len]

    async def get_weight(self, measure_unit) -> tuple[Decimal, int]:
        data = await self.exec_command(self.CMD_GET_WEIGHT)
        weight = int.from_bytes(data[:4], 'little', signed=True)
        #             division=response[10],
        #             stable=response[11]
        return Decimal(weight), 0
