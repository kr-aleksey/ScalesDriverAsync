import asyncio

from serial_asyncio import open_serial_connection

from scales_driver_async.exeptions import ConfigurationError, ConnectorError


class Connector:
    SERIAL_CONN = 'serial'
    SOCKET_CONN = 'socket'

    _CONN_BUILDER = {
        SERIAL_CONN: open_serial_connection,
        SOCKET_CONN: asyncio.open_connection
    }

    _REQUIRED_CONN_PARAMS = {
        SERIAL_CONN: ('port', ),
        SOCKET_CONN: ('host', 'port')
    }

    def __init__(self,
                 connection_type: str,
                 transfer_timeout: int | float,
                 **kwargs) -> None:
        if connection_type not in self._CONN_BUILDER:
            raise ConfigurationError(
                f'Connection type "{connection_type}" is not supported. '
                f'Use one of {list(self._CONN_BUILDER.keys())}'
            )

        missing_conn_params = (self._REQUIRED_CONN_PARAMS[connection_type]
                               - kwargs.keys())
        if missing_conn_params:
            raise ConfigurationError(f'Required connection parameters '
                                     f'are missing: {missing_conn_params}')

        self.reader = self.writer = None
        self.connection_type = connection_type
        self.connection_builder = self._CONN_BUILDER[connection_type]
        self.transfer_timeout = transfer_timeout

        # open_serial_connection expects 'url' parameter instead of 'port'.
        if connection_type == self.SERIAL_CONN:
            kwargs['url'] = kwargs.pop('port')
        self.connection_params = kwargs

    def __str__(self) -> str:
        conn_params = (
            ', '.join(f'{k}={v}' for k, v in self.connection_params.items()))
        return f'{self.connection_type.capitalize()} connection {conn_params}'

    async def _open_connection(self) -> None:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                self.connection_builder(**self.connection_params),
                self.transfer_timeout
            )
        except TimeoutError:
            raise ConnectorError('Connection timout.')
        except ValueError as err:
            raise ConfigurationError(f'Configuration error. {err}')
        except (OSError, RuntimeError) as err:
            raise ConnectorError(err)

    async def _close_connection(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except (OSError, RuntimeError):
                pass
        self.reader = self.writer = None

    async def read(self, data_len: int) -> bytes:
        """Reads n bytes from the device."""
        if self.reader is None:
            await self._open_connection()
        try:
            return await asyncio.wait_for(self.reader.readexactly(data_len),
                                          self.transfer_timeout)
        except TimeoutError:
            raise ConnectorError('Receive data timeout.')
        except (OSError, RuntimeError, asyncio.IncompleteReadError) as err:
            await self._close_connection()
            raise ConnectorError(err)

    async def write(self, data: bytes) -> None:
        """Sends data to the device."""
        if self.writer is None:
            await self._open_connection()
        try:
            self.writer.write(data)
            await asyncio.wait_for(self.writer.drain(), self.transfer_timeout)
        except TimeoutError:
            raise ConnectorError('Data sending timeout.')
        except (OSError, RuntimeError) as err:
            self.reader = self.writer = None
            raise ConnectorError(err)
