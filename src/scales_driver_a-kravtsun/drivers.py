from decimal import Decimal
from abc import ABC, abstractmethod

from exeptions import ScalesError


class Driver(ABC):
    """
    Scales driver interface.
    """
    GR = 1
    KG = 2
    LB = 3

    STABLE: int = 1
    UNSTABLE: int = 2
    OVERLOAD: int = 3

    def __init__(self, connector):
        self.connector = connector

    @abstractmethod
    async def get_info(self) -> dict:
        """Return scales info."""

    @abstractmethod
    async def get_weight(self) -> tuple[Decimal, int, int]:
        """Return tuple (weight, measure unit, status)."""


class CASType6(Driver):
    COMMANDS: dict[str, bytes] = {
        'ACK': b'\x06',
        'DC1': b'\x11',
        'ENQ': b'\x05',
    }
    RESPONSE_PREFIX = b'\x01\x02'
    RESPONSE_SUBFIX = b'\x03\x04'

    async def get_info(self) -> dict:
        return {}

    async def get_weight(self) -> tuple[Decimal, int, int]:
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
