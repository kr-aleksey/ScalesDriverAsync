import asyncio

from scales_driver_async.drivers import CASType6, MassK1C, ScalesDriver
from scales_driver_async.exeptions import ConnectorError, ScalesError

statuses = {
    ScalesDriver.STATUS_STABLE: 'stable',
    ScalesDriver.STATUS_UNSTABLE: 'unstable',
    ScalesDriver.STATUS_OVERLOAD: 'overload'
}

async def poller(device):
    try:
        info = await device.get_info()
        print(f'{device}: {info}')
    except ConnectorError as err:
        print(f'{device}. {device.connector}. {err}')
    except ScalesError as err:
        print(f'{device} error. {err}')

    while True:
        try:
            weight, status = await device.get_weight(ScalesDriver.UNIT_KG)
            print(f'{device}. Weight: {weight} kg. '
                  f'Status: {statuses[status]}.')
        except ConnectorError as err:
            print(f'{device}. {device.connector}. {err}')
        except ScalesError as err:
            print(f'{device} error. {err}')
        await asyncio.sleep(1)


async def main_coro(devices):
    tasks = [asyncio.create_task(poller(device)) for device in devices]
    await asyncio.gather(*tasks)


def main():
    devices = [
        CASType6(
            'Bench scales',
            connection_type='serial',
            transfer_timeout=1,
            port='COM6',
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1
        ),
        MassK1C(
            'Crane scales',
            connection_type='socket',
            transfer_timeout=1,
            host='10.1.15.4',
            port=9000
        ),
    ]
    asyncio.run(main_coro(devices))


if __name__ == '__main__':
    main()
