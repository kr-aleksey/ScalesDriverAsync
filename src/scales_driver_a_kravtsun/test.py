import asyncio

from drivers import CASType6, MassK1C, ScalesDriver


async def poller(device):
    while True:
        try:
            value = await device.get_weight(ScalesDriver.UNIT_KG)
            print(value)
        except ConnectionError as err:
            print('err:', err)
        except ValueError as err:
            print('err:', err)
            raise
        await asyncio.sleep(0.5)


async def main_coro(devices):
    tasks = [asyncio.create_task(poller(device)) for device in devices]
    await asyncio.gather(*tasks)


def main():
    devises = [
        CASType6(
            name='Настольные весы',
            connection_type='serial',
            transfer_timeout=1,
            url='/dev/ttyUSB0',
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1
        ),
        # MassK1C(
        #     name='Кран',
        #     connection_type='socket',
        #     transfer_timeout=1,
        #     host='10.1.20.30',
        #     port=9000
        # ),
    ]
    asyncio.run(main_coro(devises))


if __name__ == '__main__':
    main()
