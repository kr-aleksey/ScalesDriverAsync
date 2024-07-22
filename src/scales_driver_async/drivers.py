import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal, DecimalException

from scales_driver_async.connector import Connector
from scales_driver_async.exeptions import ScalesError


class ScalesDriver(ABC):
    # Measure units
    UNIT_GR = 0
    UNIT_KG = 1
    UNIT_LB = 2
    UNIT_OZ = 3

    # Measure unit ratio
    UNIT_RATIO = {
        UNIT_GR: Decimal('1'),
        UNIT_KG: Decimal('1000'),
        UNIT_LB: Decimal('453.592'),
        UNIT_OZ: Decimal('28.3495')
    }

    # Scales statuses
    STATUS_UNSTABLE = 0
    STATUS_STABLE = 1
    STATUS_OVERLOAD = 3

    INVALID_RESPONSE_MSG = (
        'Incorrect response received from the scale. Invalid {subject}. '
        'Received: "{received}", expected: "{expected}".'
    )

    HEX_SEP = ':'

    def __init__(self,
                 name: str,
                 connection_type: str,
                 transfer_timeout: int | float,
                 **kwargs):
        """
        :param name: Scales name.
        :param connection_type: Connection type ('serial' or 'socket').
        :param transfer_timeout: Transfer timeout in seconds.
        :param kwargs: Connection parameters. Host and port for
        socket connection. Url, baudrate, bytesize, parity and stopbits
        for serial connection.
        """
        self.name = name
        self.connector = Connector(connection_type=connection_type,
                                   transfer_timeout=transfer_timeout,
                                   **kwargs)
        self.lock = asyncio.Lock()

    def __str__(self):
        return self.name

    @abstractmethod
    async def get_weight(self, measure_unit: int) -> tuple[Decimal, int]:
        """Returns the scale readings and their status."""

    @abstractmethod
    async def get_info(self) -> str:
        """Returns scales info."""


class CASType6(ScalesDriver):
    # Scales commands
    CMD_ACK = b'\x06'
    CMD_DC1 = b'\x11'
    CMD_ENQ = b'\x05'

    # Response prefix + subfix
    RESPONSE_WRAP = b'\x01\x02\x03\x04'

    # Response fields
    FIELD_PREFIX = slice(0, 2)
    FIELD_SUFFIX = slice(13, 15)
    FIELD_PAYLOAD = slice(2, 12)
    FIELD_BCC = slice(12, 13)

    # Response payload fields
    FIELD_STATUS = slice(0, 1)
    FIELD_WEIGHT = slice(1, 8)
    FIELD_UNIT = slice(8, 10)

    # Scales status mapping
    STATUS_MAPPING = {
        b'\x53': ScalesDriver.STATUS_STABLE,
        b'\x55': ScalesDriver.STATUS_UNSTABLE,
        b'\x46': ScalesDriver.STATUS_OVERLOAD
    }

    # Measure unit mapping
    MEASURE_MAPPING = {
        b'\x20\x67': ScalesDriver.UNIT_GR,
        b'\x67\x20': ScalesDriver.UNIT_GR,
        b'\x6B\x67': ScalesDriver.UNIT_KG,
        b'\x6C\x62': ScalesDriver.UNIT_LB,
        b'\x6F\x7A': ScalesDriver.UNIT_OZ
    }

    async def get_info(self) -> str:
        return self.name

    async def get_weight(self, measure_unit) -> tuple[Decimal, int]:
        payload = self.check_response(await self.read_data())
        # get status
        status = self.STATUS_MAPPING.get(payload[self.FIELD_STATUS],
                                         self.STATUS_OVERLOAD)
        if status == self.STATUS_OVERLOAD:
            return Decimal('0'), status
        # get unit
        scales_unit = payload[self.FIELD_UNIT]
        if scales_unit not in self.MEASURE_MAPPING:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='measure unit',
                    received=scales_unit,
                    expected=', '.join(map(str, self.MEASURE_MAPPING)),
                )
            )
        # get the weight
        try:
            weight = Decimal(
                payload[self.FIELD_WEIGHT].decode(errors='ignore'))
        except DecimalException:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='scale readings',
                    received=payload[self.FIELD_WEIGHT].decode(
                        errors='ignore'),
                    expected='number'
                )
            )
        # convert unit
        weight = (weight
                  * self.UNIT_RATIO[self.MEASURE_MAPPING[scales_unit]]
                  / self.UNIT_RATIO[measure_unit])

        return weight, status

    def check_response(self, response: bytes) -> bytes:
        """
        Checks the response received from the scales.
        Returns the response payload (without prefix and subfix).
        :param response: Response data
        :return: Payload
        """
        # check response wrap
        wrap = response[self.FIELD_PREFIX] + response[self.FIELD_SUFFIX]
        if wrap != self.RESPONSE_WRAP:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='packet wrap',
                    received=wrap.hex(self.HEX_SEP),
                    expected=self.RESPONSE_WRAP.hex(self.HEX_SEP)
                )
            )
        # check response BCC
        payload = response[self.FIELD_PAYLOAD]
        received_bcc = self.calc_bcc(payload)
        computed_bcc = response[self.FIELD_BCC]
        if received_bcc != computed_bcc:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='bcc',
                    received=received_bcc.hex(self.HEX_SEP),
                    expected=computed_bcc.hex(self.HEX_SEP)
                )
            )
        return payload

    async def read_data(self) -> bytes:
        async with self.lock:
            await self.connector.write(self.CMD_ENQ)
            ack = await self.connector.read(len(self.CMD_ACK))
            if ack != self.CMD_ACK:
                raise ScalesError(
                    self.INVALID_RESPONSE_MSG.format(
                        subject='ACK',
                        received=ack.hex(self.HEX_SEP),
                        expected=self.CMD_ACK.hex(self.HEX_SEP)
                    )
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
    # Packet header (request and response)
    HEADER = b'\xF8\x55\xCE'

    # Scales commands
    CMD_POLL = b'\x00'  # Get firmware version and serial number
    CMD_GET_WEIGHT = b'\xA0'  # Get current scale reading

    # Commands ACK
    CMD_ACK = {
        CMD_POLL: b'\x01',
        CMD_GET_WEIGHT: b'\x10'
    }

    # Responses lengths
    CMD_RESPONSE_LEN = {
        CMD_POLL: 34,
        CMD_GET_WEIGHT: 14
    }

    # Response fields
    FIELD_HEADER = slice(0, 3)
    FIELD_ACK = slice(5, 6)
    FIELD_PAYLOAD = slice(5, -2)
    FIELD_CRC = slice(-2, None)

    # Response payload fields
    # CMD_POLL
    FIELD_FW_MAJOR = 5
    FIELD_FW_MINOR = 4
    FIELD_SERIAL = slice(6, 10)
    # CMD_GET_WEIGHT
    FIELD_WEIGHT = slice(1, 5)
    FIELD_DIVISION = 5
    FIELD_STATUS = 6

    # Conversion factors for divisions
    DIVISION_FACTOR = {
        0: Decimal('0.1'),  # 100 mg
        1: Decimal('1'),  # 1 g
        2: Decimal('10'),  # 10 g
        3: Decimal('100'),  # 100 g
        4: Decimal('1000')  # 1 kg
    }

    # Status mapping
    STATUS_REPR = {
        0: ScalesDriver.STATUS_UNSTABLE,
        1: ScalesDriver.STATUS_STABLE
    }

    async def get_info(self) -> str:
        payload = await self.exec_command(self.CMD_POLL)
        firmware = (f'{payload[self.FIELD_FW_MAJOR]}.'
                    f'{payload[self.FIELD_FW_MINOR]}')
        serial = int.from_bytes(payload[self.FIELD_SERIAL], byteorder='little')
        return (f'{self.name.capitalize()}. '
                f'Firmware version: {firmware}. '
                f'Serial number: {serial}')

    async def get_weight(self, measure_unit: int) -> tuple[Decimal, int]:
        if measure_unit not in self.UNIT_RATIO:
            raise ValueError('Invalid measure unit.')
        payload = await self.exec_command(self.CMD_GET_WEIGHT)
        # scales status
        status = self.STATUS_REPR.get(
            payload[self.FIELD_STATUS], self.STATUS_OVERLOAD)
        if status == self.STATUS_OVERLOAD:
            return Decimal('0'), status
        # value of division
        division = payload[self.FIELD_DIVISION]
        if division not in self.DIVISION_FACTOR:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='division cost',
                    received=division,
                    expected=', '.join(map(str, self.DIVISION_FACTOR))
                )
            )
        # weight in measure_unit
        weight = (
                int.from_bytes(
                    payload[self.FIELD_WEIGHT], 'little', signed=True)
                * self.DIVISION_FACTOR[division]
                / self.UNIT_RATIO[measure_unit]
        )
        return weight, status

    async def exec_command(self, command: bytes) -> bytes:
        """
        Prepares and sends the request. Returns the response payload.
        :param command: Command (CMD_GET_WEIGHT, CMD_POLL ...).
        :return: Response payload.
        """
        async with self.lock:
            data = self.HEADER + len(command).to_bytes(length=2) + command
            data += self.calc_crc(data)
            await self.connector.write(data)

            data: bytes = await self.connector.read(
                self.CMD_RESPONSE_LEN[command])
            return self.check_response(command, data)

    def check_response(self, command: bytes, response: bytes) -> bytes:
        """
        Checks the response received from the scales.
        Returns the response payload (without header, response length,
        ACK and CRC).
        :param command: Request command.
        :param response: Response data.
        :return: Payload.
        """
        # check header
        header = response[self.FIELD_HEADER]
        if header != self.HEADER:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='header',
                    received=header.hex(self.HEX_SEP),
                    expected=self.HEADER.hex(self.HEX_SEP)
                )
            )
        # check CRC
        payload = response[self.FIELD_PAYLOAD]
        computed_crc = self.calc_crc(payload)
        received_crc = response[self.FIELD_CRC]
        if computed_crc != received_crc:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='CRC',
                    received=received_crc.hex(self.HEX_SEP),
                    expected=computed_crc.hex(self.HEX_SEP)
                )
            )
        # check ACK
        ack = response[self.FIELD_ACK]
        expected_ack = self.CMD_ACK[command]
        if ack != expected_ack:
            raise ScalesError(
                self.INVALID_RESPONSE_MSG.format(
                    subject='ACK',
                    received=ack.hex(self.HEX_SEP),
                    expected=expected_ack.hex(self.HEX_SEP)
                )
            )
        return payload

    @staticmethod
    def calc_crc(data: bytes) -> bytes:
        """
        Calculates the CRC of the data.
        :param data: Data to calculate.
        :return: CRC.
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
