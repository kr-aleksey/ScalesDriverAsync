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
        """
        Возвращает текстовое представление байт-строки.
        :param data: Данные.
        :return: Текстовое представление.
        """
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
    # Заголовок пакетов
    HEADER = b'\xF8\x55\xCE'

    # Команды исполняемые весами
    CMD_POLL = b'\x00'
    CMD_GET_WEIGHT = b'\xA0'

    # Ответные ACK
    CMD_ACK = {
        CMD_POLL: b'\x01',
        CMD_GET_WEIGHT: b'\x10',
    }

    # Ожидаемые длины ответов
    CMD_RESPONSE_LEN = {
        CMD_POLL: 34,
        CMD_GET_WEIGHT: 14
    }

    """
    Интерфейс драйвера.
    """

    async def get_info(self) -> dict:
        return {}

    async def get_weight(self, measure_unit) -> tuple[Decimal, int]:
        data = await self.exec_command(self.CMD_GET_WEIGHT)
        weight_end = 4
        weight = int.from_bytes(
            data[:weight_end], 'little', signed=True)
        return Decimal(weight), 0

    """
    Протокол весов.
    """

    async def exec_command(self, command: bytes) -> bytes:
        """
        Подготавливает и отправляет запрос. Возвращает полезные данные ответа.
        :param command: Выполняемая команда (CMD_GET_WEIGHT, CMD_POLL ...).
        :return: Данные ответа.
        """
        data = self.HEADER + len(command).to_bytes(length=2) + command
        data += self.crc(data)
        await self.connector.write(data)

        data: bytes = await self.connector.read(1024)
        return self.check_response(command, data)

    def check_response(self, command: bytes, data: bytes) -> bytes:
        """
        Проверяет ответ, полученный от весов. Возвращает полезные данные
        ответа (без заголовка, длины ответа, ACK и CRC).
        :param command: Команда отправленная весам.
        :param data: Ответ полученный от весов.
        :return: Полезные данные.
        """

        err_msg = ('Incorrect response received from the scale. Invalid '
                   '{subject}. Received: {received}, expected: {expected}.')

        # проверяем длину
        if len(data) != self.CMD_RESPONSE_LEN[command]:
            raise ValueError(
                err_msg.format(subject='response length',
                               received=len(data),
                               expected=self.CMD_RESPONSE_LEN[command])
            )
        # проверяем header
        header_end = 3
        header = data[: header_end]
        if header != self.HEADER:
            raise ValueError(
                err_msg.format(subject='header',
                               received=self.to_hex(header),
                               expected=self.to_hex(self.HEADER))
            )
        # проверяем CRC
        data_start = 5
        data_end = -2
        crc_start = -2
        computed_crc = self.crc(data[data_start: data_end])
        received_crc = data[crc_start:]
        if computed_crc != data[crc_start:]:
            raise ValueError(
                err_msg.format(subject='CRC',
                               received=self.to_hex(received_crc),
                               expected=self.to_hex(computed_crc))
            )
        # проверяем ACK
        ack_start = 5
        ack_end = 6
        ack = data[ack_start: ack_end]
        if ack != self.CMD_ACK[command]:
            raise ValueError(
                err_msg.format(subject='ACK',
                               received=self.to_hex(ack),
                               expected=self.to_hex(self.CMD_ACK[command]))
            )
        # возвращаем payload
        payload_start = 6
        payload_end = -2
        return data[payload_start: payload_end]

    @staticmethod
    def crc(data: bytes) -> bytes:
        """
        Подсчет CRC пакетов данных.
        :param data: Данные.
        :return: CRC
        """
        poly = 0x1021
        crc = 0
        for byte in data:
            accumulator = 0
            temp = crc & 0xff00
            for _ in range(8):
                if (temp ^ accumulator) & 0x8000:
                    accumulator = (accumulator << 1) ^ poly
                else:
                    accumulator <<= 1
                temp <<= 1
            crc = accumulator ^ (crc << 8) ^ (byte & 0xff)
        crc &= 0xffff
        return crc.to_bytes(length=2, byteorder='little')
