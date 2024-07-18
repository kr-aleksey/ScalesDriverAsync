from abc import ABC, abstractmethod
from decimal import Decimal, DecimalException

from connector import Connector
from exeptions import ScalesError


class ScalesDriver(ABC):
    """
    Интерфейс драйвера весов.
    """
    # Единицы измерения веса
    UNIT_GR = 0
    UNIT_KG = 1
    UNIT_LB = 2
    UNIT_OZ = 3

    UNIT_DIVIDER = {
        UNIT_GR: Decimal('1'),
        UNIT_KG: Decimal('1000'),
        UNIT_LB: Decimal('453.592'),
        UNIT_OZ: Decimal('28.3495')
    }

    # Статус весов
    STATUS_UNSTABLE = 0
    STATUS_STABLE = 1
    STATUS_OVERLOAD = 3

    def __init__(self,
                 name: str,
                 connection_type: str,
                 transfer_timeout: int | float,
                 **kwargs):
        """
        :param connector: экземпляр класса Connector
        """
        self.name = name
        self.connector = Connector(connection_type=connection_type,
                                   transfer_timeout=transfer_timeout,
                                   **kwargs)

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
        Возвращает шестнадцатеричное представление байт-строки.
        :param data: Данные.
        :return: Текстовое представление.
        """
        return data.hex(sep=':')


class CASType6(ScalesDriver):

    CMD_ACK = b'\x06'
    CMD_DC1 = b'\x11'
    CMD_ENQ = b'\x05'

    RESPONSE_WRAP = b'\x01\x02\x03\x04'
    RESPONSE_PREFIX = slice(0, 2)
    RESPONSE_SUFFIX = slice(13, 15)
    RESPONSE_PAYLOAD = slice(2, 12)
    RESPONSE_BCC = slice(12, 13)

    PAYLOAD_STATUS = slice(0, 1)
    PAYLOAD_WEIGHT = slice(1, 8)
    PAYLOAD_UNIT = slice(8, 10)

    STATUS_REPR = {
        b'\x53': ScalesDriver.STATUS_STABLE,
        b'\x55': ScalesDriver.STATUS_UNSTABLE,
        b'\x46': ScalesDriver.STATUS_OVERLOAD
    }

    MEASURE_UNITS = {
        b'\x20\x67': ScalesDriver.UNIT_GR,
        b'\x67\x20': ScalesDriver.UNIT_GR,
        b'\x6B\x67': ScalesDriver.UNIT_KG,
        b'\x6C\x62': ScalesDriver.UNIT_LB,
        b'\x6F\x7A': ScalesDriver.UNIT_OZ
    }

    async def get_info(self) -> dict:
        return {}

    async def get_weight(self, measure_unit) -> tuple[Decimal, int]:
        data = self.check_response(await self.read_data())
        status = self.STATUS_REPR.get(data[self.PAYLOAD_STATUS],
                                      self.STATUS_UNSTABLE)
        scales_measure_unit = self.MEASURE_UNITS[data[self.PAYLOAD_UNIT]]
        try:
            weight = (
                Decimal(data[self.PAYLOAD_WEIGHT].decode(errors='ignore'))
                * self.UNIT_DIVIDER[scales_measure_unit]
                / self.UNIT_DIVIDER[measure_unit]
            )
        except DecimalException:
            raise ScalesError('Response parsing error')

        return weight, status

    def check_response(self, response: bytes):
        # response wrap
        wrap: bytes = (response[self.RESPONSE_PREFIX]
                       + response[self.RESPONSE_SUFFIX])
        if wrap != self.RESPONSE_WRAP:
            raise ScalesError(
                f'Response wrap={wrap!r}, expected {self.RESPONSE_WRAP!r}')

        # response BCC
        payload = response[self.RESPONSE_PAYLOAD]
        received_bcc = self.calc_bcc(payload)
        computed_bcc = response[self.RESPONSE_BCC]
        if received_bcc != computed_bcc:
            raise ScalesError(f'Computed BCC={received_bcc}, '
                              f'expected {computed_bcc}')
        return payload

    async def read_data(self) -> bytes:
        await self.connector.write(self.CMD_ENQ)
        ack = await self.connector.read(len(self.CMD_ACK))
        if ack != self.CMD_ACK:
            expected = self.CMD_ACK
            raise ConnectionError(
                f'Incorrect response received from the scale. '
                f'Expected ACK = {expected}, received: {ack!r}'
            )
        await self.connector.write(self.CMD_DC1)
        return await self.connector.read(15)

    @staticmethod
    def calc_bcc(data: bytes) -> bytes:
        """Returns BCC for data."""
        bcc: int = 0
        for item in data:
            bcc ^= item
        return bcc.to_bytes()


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
        CMD_GET_WEIGHT: b'\x10'
    }

    # Ожидаемые длины ответов
    CMD_RESPONSE_LEN = {
        CMD_POLL: 34,
        CMD_GET_WEIGHT: 14
    }

    # Цена деления - коэффициент пересчета в граммы
    DIVISION_RATIO = {
        0: Decimal('0.1'),
        1: Decimal('1'),
        2: Decimal('10'),
        3: Decimal('100')
    }

    # Статус весов - представление
    STATUS_REPR = {
        0: ScalesDriver.STATUS_UNSTABLE,
        1: ScalesDriver.STATUS_STABLE
    }

    """
    Интерфейс драйвера.
    """

    async def get_info(self) -> dict:
        data = await self.exec_command(self.CMD_POLL)
        # получаем версию прошивки
        version_start = 1
        version_end = 3
        serial_start = 5
        serial_end = 8
        return {
            'firmware_version': data[version_start:version_end],
            'serial_number': int.from_bytes(data[serial_start:serial_end], byteorder='little'),
            # 'serial_number': data[serial_start:serial_end].decode('ascii'),
        }

    async def get_weight(self, measure_unit: int) -> tuple[Decimal, int]:
        if measure_unit not in self.UNIT_DIVIDER:
            raise ValueError('Invalid measure unit')
        data = await self.exec_command(self.CMD_GET_WEIGHT)
        # получаем цену деления
        division_index = 4
        division = data[division_index]
        # получаем вес в граммах
        weight_end = 4
        weight = (
            int.from_bytes(data[:weight_end], 'little', signed=True)
            * self.DIVISION_RATIO.get(division, Decimal('0'))
            / self.UNIT_DIVIDER[measure_unit]
        )
        # получаем статус
        status_index = 5
        status = self.STATUS_REPR.get(data[status_index], self.STATUS_OVERLOAD)
        return weight, status

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
        data += self.calc_crc(data)
        await self.connector.write(data)

        data: bytes = await self.connector.read(self.CMD_RESPONSE_LEN[command])
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
        computed_crc = self.calc_crc(data[data_start: data_end])
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
    def calc_crc(data: bytes) -> bytes:
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
            crc = accumulator ^ (crc << 8) ^ byte
        crc &= 0xffff
        return crc.to_bytes(length=2, byteorder='little')
