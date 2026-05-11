# config.py


class SPIBus:

    ID = 2

    SCK = 18
    MOSI = 23
    MISO = 19

    BAUDRATE = 1_000_000


class OLED:

    WIDTH = 128
    HEIGHT = 64

    CS = 15
    DC = 27
    RST = 33


class GPS:

    UART_ID = 2

    TX = 17
    RX = 16

    BAUDRATE = 9600

    TIMEOUT = 1000
