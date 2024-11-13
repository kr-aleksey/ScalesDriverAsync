class ConfigurationError(Exception):
    pass


class ConnectorError(Exception):
    pass


class ScalesError(Exception):
    pass


class ScalesFunctionNotSupported(ScalesError):
    pass