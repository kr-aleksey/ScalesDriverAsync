# ScalesDriverAsync
## About
Электронные весы получили широкое распространение на производственных предприятиях, в логистике, торговле, медицине
и в других областях. Несмотря на широкое распространение программное взаимодействие с весами не стандартизировано.
Электронные весы имеют разнообразные интерфейсы для подключения и протоколы для обмена данными. Наиболее распространены 
весы с интерфейсами RS-232, Ethernet и Wi-Fi. Некоторые модели имеют более одного интерфейса. Многие производители 
реализуют широко известные протоколы обмена данными в своих устройствах, например протокол CAS и его разновидности, 
другие же реализуют собственные открытые протоколы. 

**ScalesDriverAsync** - это асинхронный драйвер электронных весов. **ScalesDriverAsync** предоставляет единый интерфейс 
независимо ни от физического интерфейса, ни от протокола.

Класс **Connector** модуля connector предоставляет высокоуровневый интерфейс для отправки и получения данных. Кроме 
того он предоставляет логику для простой обработки ошибок передачи данных и восстановления соединения после сбоев.

Модуль **drivers** предоставляет реализации протоколов обмена данными.

## Requirements
- Python >= 3.10
- [pyserial-asyncio](https://pypi.org/project/pyserial-asyncio/)

## Usage
`pip install scales-driver-async`


```python
import asyncio

from scales_driver_async.drivers import CASType6, ScalesDriver


async def main():
    scales = CASType6(
            name='Bench scales',
            connection_type='serial',
            transfer_timeout=1,
            url='/dev/ttyUSB0',
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1
    )
    print(await scales.get_weight(ScalesDriver.UNIT_KG))

asyncio.run(main())

```


## Class connector.Connector
**Connector** предоставляет высокоуровневый API для получения и отправки данных. Работает поверх `asyncio.StreamReader` 
и `asyncio.StreamWriter`. Конструктор принимает параметры `connection_type`, `transfer_timout` и другие ключевые 
параметры (`kwargs`). Параметр `connection_type`может иметь значение 'socket' или 'serial'. Параметр 
`transfer_timout` - число, время ожидание отправки и получения данных в секундах. `Kwargs` должны иметь значения 
параметров соединения передаваемых в функцию `asyncio.open_connection(**kwargs)` или 
`serial_asyncio.open_serial_connection(**kwargs)`.

```python
async def main():
    connector = Connector('socket', 1.5, host='localhost', port=8080)
    await connector.write('Hello!'.encode())
    print(connector.read(6))
```

Вам обычно ненужно создавать объект этого класса напрямую.

### coroutine read(data_len)
Открывает соединение, если оно не было открыто. Читает data_len байт из потока. Если данные небыли получены по 
истечении таймаута, будет поднято исключение `ConnectorError`. При возникновении других ошибок соединение будет закрыто 
и также будет поднято исключение.

### coroutine write(data)
Открывает соединение, если оно не было открыто. Записывает данные. Ждет завершения передачи. Если данные небыли 
записаны по истечении таймаута, будет поднято исключение `ConnectorError`. При возникновении других ошибок соединение 
будет закрыто и также будет поднято исключение.

### Exceptions
***Connector*** может поднимать два типа исключений: `ValueError` и `ConnectorError`. Исключение `ValueError` будет 
поднято, если были переданы неверные параметры при инстанцировании. Исключение `ConnectorError` будет поднято при
возникновении ошибок передачи данных. Это исключение может быть перехвачено и обработано, а работа приложения 
продолжена без каких-либо дополнительных действий. Соединение будет восстановлено автоматически.


## Class drivers.ScalesDriver
***ScalesDriver*** - абстрактный класс предоставляющий высокоуровневый API весов. Классы модуля `drivers` наследуются 
от ***ScalesDriver*** и реализуют протокол весов. Любой протокол может работать через сокет или последовательный порт.
Пока реализовано два протокола `CASType6` (CAS type #6) и `MassK1C` (Масса-К 1С). Протокол CAS type #6 поддерживают 
многие весы разных брендов. Масса-К 1С - протокол [АО "МАССА-К" ](https://massa.ru/).

```python
async def main():
    scales = CASType6(
        name='Bench scales',
        connection_type='serial',
        transfer_timeout=1,
        url='/dev/ttyUSB0',
        baudrate=9600,
        bytesize=8,
        parity='N',
        stopbits=1
    )
    print(await scales.get_weight(ScalesDriver.UNIT_KG))
```
