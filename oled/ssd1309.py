from micropython import const
import framebuf

SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)

class SSD1309(framebuf.FrameBuffer):
    def __init__(self, width, height, spi, dc, res, cs):
        self.width = width
        self.height = height
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs

        self.buffer = bytearray(self.height * self.width // 8)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)

        self.init_display()

    def write_cmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.dc(1)
        self.cs(0)
        self.spi.write(buf)
        self.cs(1)

    def init_display(self):
        self.res(1)
        self.res(0)
        self.res(1)

        self.write_cmd(SET_DISP | 0x00)  # off

        self.write_cmd(0xD5)  # clock
        self.write_cmd(0x80)

        self.write_cmd(0xA8)  # multiplex
        self.write_cmd(self.height - 1)

        self.write_cmd(0xD3)  # offset
        self.write_cmd(0x00)

        self.write_cmd(0x40)  # start line

        self.write_cmd(0x8D)  # charge pump
        self.write_cmd(0x14)

        self.write_cmd(SET_MEM_ADDR)
        self.write_cmd(0x00)

        self.write_cmd(0xA1)  # seg remap
        self.write_cmd(0xC8)  # scan dir

        self.write_cmd(0xDA)
        self.write_cmd(0x12)

        self.write_cmd(SET_CONTRAST)
        self.write_cmd(0xCF)

        self.write_cmd(0xD9)
        self.write_cmd(0xF1)

        self.write_cmd(0xDB)
        self.write_cmd(0x40)

        self.write_cmd(SET_ENTIRE_ON)
        self.write_cmd(SET_NORM_INV)

        self.write_cmd(SET_DISP | 0x01)  # on

    def show(self):
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)

        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd((self.height // 8) - 1)

        self.write_data(self.buffer)