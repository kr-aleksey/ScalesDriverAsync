import asyncio

from connectors import SerialConnector, SocketConnector
from drivers import CASType6, MassK1C, ScalesDriver


async def poller(device):
    while True:
        try:
            value = await device.get_weight(ScalesDriver.UNIT_KG)
            print(value)
        except (ValueError, ConnectionError) as err:
            print('err:', err)

        await asyncio.sleep(0.5)


async def main_coro(devices):
    tasks = [asyncio.create_task(poller(device)) for device in devices]
    await asyncio.gather(*tasks)


def main():
    devises = [
        CASType6(SerialConnector('/dev/ttyUSB0')),
        MassK1C(SocketConnector('10.1.20.30:9000')),
    ]
    asyncio.run(main_coro(devises))


if __name__ == '__main__':
    main()
