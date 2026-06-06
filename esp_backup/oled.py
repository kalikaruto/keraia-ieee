
# oled.py

from machine import I2C
import sh1106
from config import OLED as OLEDConfig


class OLED():
    def __init__(self):
        self.i2c = I2C(OLEDConfig.SCL, OLEDConfig.SDA)
        self.oled = sh1106.SH1106_I2C(OLEDConfig.HEIGHT, OLEDConfig.WIDTH, self.i2c)
        self.oled.rotate(1)
    def write_cmd(self, cmd):
        self.oled.write_cmd(cmd)
    def write_data(self, buf):
        self.oled.write(buf)
        self.oled.show()
    def reset(self):
        self.oled.fill(0)
        self.oled.show()
    def show(self):
        self.oled.show()
    def clear_buf(self):
        self.oled.fill(0)
    def rotate(self, rot):
        self.oled.rotate(rot)
    def center_text(self, txt, y):
        x = (OLEDConfig.WIDTH - len(txt) * 8) // 2

        self.oled.rect(0, 0, OLEDConfig.WIDTH, OLEDConfig.HEIGHT, 1)
        self.oled.text(txt, x, y, 1)
        self.oled.show()
    def center_error(self, txt, y):
        self.oled.invert(1)
        x = (OLEDConfig.WIDTH - len(txt) * 8) // 2
        self.oled.rect(0, 0, OLEDConfig.WIDTH, OLEDConfig.HEIGHT, 0)
        self.oled.text(txt, x, y, 0)
        self.oled.show()


def init():
    global oled
    oled = OLED()
