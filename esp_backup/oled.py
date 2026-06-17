# oled.py

from machine import I2C, Pin
import sh1106
from config import OLED as OLEDConfig

class OLED():
    def __init__(self):
        self.i2c = I2C(0, scl=Pin(OLEDConfig.SCL), sda=Pin(OLEDConfig.SDA))
        self.oled = sh1106.SH1106_I2C(OLEDConfig.WIDTH, OLEDConfig.HEIGHT, self.i2c)
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
    def text(self, txt, x,y):
        self.oled.rect(0, 0, OLEDConfig.WIDTH, OLEDConfig.HEIGHT-2, 1)
        self.oled.text(txt, x, y, 1)
        self.oled.show()
    def error(self, txt, x, y):
        self.oled.fill(1)
        self.oled.text(txt, x, y, 0)
        self.oled.show()
