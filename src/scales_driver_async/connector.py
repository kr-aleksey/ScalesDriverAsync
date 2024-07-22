import asyncio

from serial_asyncio import open_serial_connection

from scales_driver_async.exeptions import ConnectorError


class Connector:
    connection_coroutines = {
        'serial': open_serial_connection,
        'socket': asyncio.open_connection
    }

    def __init__(self,
                 connection_type: str,
                 transfer_timeout: int | float, **kwargs) -> None:
        self.reader = self.writer = None
        self.connection_type = connection_type
        self.transfer_timeout = transfer_timeout
        self.kwargs = kwargs

        if connection_type not in self.connection_coroutines:
            raise ValueError(f'Connection type "{connection_type}" '
                             f'is not supported.')

    def __str__(self) -> str:
        conn_params = ', '.join(f'{k}={v}' for k, v in self.kwargs.items())
        return f'{self.connection_type.capitalize()} connection {conn_params}'

    @property
    def connection_coroutine(self):
        return self.connection_coroutines[self.connection_type]

    async def _open_connection(self) -> None:
        try:
            self.reader, self.writer = await self.connection_coroutine(
                **self.kwargs)
        except ValueError as err:
            raise ValueError(f'Configuration error. {err}')
        except OSError as err:
            raise ConnectorError(err)

    async def _close_connection(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except OSError:
                pass
        self.reader = self.writer = None

    async def read(self, data_len: int) -> bytes:
        if self.reader is None:
            await self._open_connection()
        try:
            return await asyncio.wait_for(self.reader.readexactly(data_len),
                                          self.transfer_timeout)
        except TimeoutError:
            raise ConnectorError('Receive data timeout.')
        except (OSError, asyncio.IncompleteReadError) as err:
            await self._close_connection()
            raise ConnectorError(err)

    async def write(self, data: bytes) -> None:
        if self.writer is None:
            await self._open_connection()
        try:
            self.writer.write(data)
            await asyncio.wait_for(self.writer.drain(), self.transfer_timeout)
        except TimeoutError:
            raise ConnectorError('Data sending timeout.')
        except OSError as err:
            self.reader = self.writer = None
            raise ConnectorError(err)
