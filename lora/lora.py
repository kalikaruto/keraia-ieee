from machine import Pin
import time
import gc

TX_BASE_ADDR = 0x00
RX_BASE_ADDR = 0x00

PA_BOOST = 0x80

REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_LNA = 0x0c
REG_FIFO_ADDR_PTR = 0x0d
REG_FIFO_TX_BASE_ADDR = 0x0e
REG_FIFO_RX_BASE_ADDR = 0x0f
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_RSSI_VALUE = 0x1a
REG_PKT_SNR_VALUE = 0x1b
REG_MODEM_CONFIG_1 = 0x1d
REG_MODEM_CONFIG_2 = 0x1e
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_MODEM_CONFIG_3 = 0x26
REG_DETECTION_OPTIMIZE = 0x31
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42

MODE_LORA = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONTINUOUS = 0x05

IRQ_TX_DONE_MASK = 0x08
IRQ_PAYLOAD_CRC_ERROR_MASK = 0x20

MAX_PKT_LENGTH = 255


class LoRa:
    def __init__(self, spi, cs, rx, frequency=433.0):
        self.spi = spi
        self.cs = cs
        self.rx = rx

        self.cs.value(1)

        while self._read(REG_VERSION) != 0x12:
            time.sleep_ms(100)

        self.sleep()
        self.set_frequency(frequency)
        self.set_tx_power(17)

        self._write(REG_LNA, self._read(REG_LNA) | 0x03)
        self._write(REG_MODEM_CONFIG_3, 0x04)

        self._write(REG_FIFO_TX_BASE_ADDR, TX_BASE_ADDR)
        self._write(REG_FIFO_RX_BASE_ADDR, RX_BASE_ADDR)

        self.standby()

    def begin_packet(self):
        self.standby()
        self._write(REG_FIFO_ADDR_PTR, TX_BASE_ADDR)
        self._write(REG_PAYLOAD_LENGTH, 0)

    def end_packet(self):
        self._write(REG_OP_MODE, MODE_LORA | MODE_TX)
        while (self._read(REG_IRQ_FLAGS) & IRQ_TX_DONE_MASK) == 0:
            pass
        self._write(REG_IRQ_FLAGS, IRQ_TX_DONE_MASK)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()

        self.begin_packet()

        for b in data:
            self._write(REG_FIFO, b)

        self._write(REG_PAYLOAD_LENGTH, len(data))
        self.end_packet()

    def recv(self, callback):
        self._write(REG_DIO_MAPPING_1, 0x00)
        self.rx.irq(handler=lambda pin: self._handle_irq(callback),
                    trigger=Pin.IRQ_RISING)
        self._write(REG_OP_MODE, MODE_LORA | MODE_RX_CONTINUOUS)

    def _handle_irq(self, callback):
        irq = self._read(REG_IRQ_FLAGS)
        self._write(REG_IRQ_FLAGS, irq)

        if irq & IRQ_PAYLOAD_CRC_ERROR_MASK == 0:
            self._write(REG_FIFO_ADDR_PTR,
                        self._read(REG_FIFO_RX_CURRENT_ADDR))

            length = self._read(REG_RX_NB_BYTES)
            payload = bytearray()

            for _ in range(length):
                payload.append(self._read(REG_FIFO))

            callback(bytes(payload))
            gc.collect()

    def sleep(self):
        self._write(REG_OP_MODE, MODE_LORA | MODE_SLEEP)

    def standby(self):
        self._write(REG_OP_MODE, MODE_LORA | MODE_STDBY)

    def set_tx_power(self, level):
        level = min(max(level, 2), 17)
        self._write(REG_PA_CONFIG, PA_BOOST | (level - 2))

    def set_frequency(self, freq):
        self._frequency = freq
        frf = int((freq * 1000000.0) / 61.03515625)
        self._write(REG_FRF_MSB, (frf >> 16) & 0xff)
        self._write(REG_FRF_MID, (frf >> 8) & 0xff)
        self._write(REG_FRF_LSB, frf & 0xff)

    def _transfer(self, addr, val=0x00):
        buf = bytearray(1)
        self.cs.value(0)
        self.spi.write(bytearray([addr]))
        self.spi.write_readinto(bytearray([val]), buf)
        self.cs.value(1)
        return buf[0]

    def _read(self, addr):
        return self._transfer(addr & 0x7F)

    def _write(self, addr, val):
        self._transfer(addr | 0x80, val)

