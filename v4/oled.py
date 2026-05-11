# oled.py

import machine
import time
import framebuf
import config


SSD1309_WIDTH  = 128
SSD1309_HEIGHT = 64


class OLED(framebuf.FrameBuffer):

    def __init__(self):

        self.width = SSD1309_WIDTH
        self.height = SSD1309_HEIGHT

        self.cs = machine.Pin(config.OLED.CS, machine.Pin.OUT)
        self.dc = machine.Pin(config.OLED.DC, machine.Pin.OUT)
        self.rst = machine.Pin(config.OLED.RST, machine.Pin.OUT)

        self.cs.on()

        self.spi = machine.SPI(
            config.SPIBus.ID,
            baudrate=config.SPIBus.BAUDRATE,
            polarity=0,
            phase=0,
            sck=machine.Pin(config.SPIBus.SCK),
            mosi=machine.Pin(config.SPIBus.MOSI),
            miso=machine.Pin(config.SPIBus.MISO)
        )

        self.buffer = bytearray(self.width * self.height // 8)

        super().__init__(
            self.buffer,
            self.width,
            self.height,
            framebuf.MONO_VLSB
        )

        self.init_display()

    def write_cmd(self, cmd):

        self.cs.off()
        self.dc.off()

        self.spi.write(bytearray([cmd]))

        self.cs.on()

    def write_data(self, buf):

        self.cs.off()
        self.dc.on()

        self.spi.write(buf)

        self.cs.on()

    def reset(self):

        self.rst.on()
        time.sleep_ms(1)

        self.rst.off()
        time.sleep_ms(10)

        self.rst.on()

        time.sleep_ms(10)

    def init_display(self):

        self.reset()

        init_cmds = [
            0xAE,

            0xD5,
            0x80,

            0xA8,
            0x3F,

            0xD3,
            0x00,

            0x40,

            0x8D,
            0x14,

            0x20,
            0x00,

            0xA1,

            0xC8,

            0xDA,
            0x12,

            0x81,
            0xCF,

            0xD9,
            0xF1,

            0xDB,
            0x40,

            0xA4,

            0xA6,

            0xAF
        ]

        for cmd in init_cmds:
            self.write_cmd(cmd)

        self.fill(0)
        self.show()

    def show(self):

        self.write_cmd(0x21)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)

        self.write_cmd(0x22)
        self.write_cmd(0)
        self.write_cmd((self.height // 8) - 1)

        self.write_data(self.buffer)

    def center_text(self, txt, y):

        x = (self.width - len(txt) * 8) // 2

        self.text(txt, x, y, 1)

