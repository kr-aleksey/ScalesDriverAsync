import asyncio

from connectors import SerialConnector


async def main():

    connector = SerialConnector(
        port='/dev/ttyUSB0',
        baud_rate=19200,
        bytesize=8,
        parity='N',
        stop_bits=1,
        timeout=0.1
    )
    await connector.connect()

    while True:
        message = b'test message'
        connector.write(message)
        print('Message sent:', message)
        received = await connector.read(50)
        print('Received:', received)
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
