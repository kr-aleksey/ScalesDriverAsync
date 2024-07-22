import asyncio

from scales_driver_async.drivers import CASType6, MassK1C, ScalesDriver
from scales_driver_async.exeptions import ConnectorError, ScalesError


async def poller(device):
    try:
        value = await device.get_info()
        print(f'{device}: {value}')
    except ConnectorError as err:
        print(f'{device}. {device.connector}. {err}')
    except ScalesError as err:
        print(f'{device} error. {err}')

    while True:
        try:
            value = await device.get_weight(ScalesDriver.UNIT_KG)
            print(f'{device}: {value}')
        except ConnectorError as err:
            print(f'{device}. {device.connector}. {err}')
        except ScalesError as err:
            print(f'{device} error. {err}')
        except ValueError as err:
            print(f'{device} error. {err}')
            raise
        await asyncio.sleep(1)


async def main_coro(devices):
    tasks = [asyncio.create_task(poller(device)) for device in devices]
    await asyncio.gather(*tasks)


def main():
    devices = [
        CASType6(
            name='Bench scales',
            connection_type='serial',
            transfer_timeout=1,
            url='/dev/ttyUSB0',
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1
        ),
        MassK1C(
            name='Crane scales',
            connection_type='socket',
            transfer_timeout=1,
            host='10.1.20.30',
            port=9000
        ),
    ]
    asyncio.run(main_coro(devices))


if __name__ == '__main__':
    main()
