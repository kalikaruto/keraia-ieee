
# oled.py

from board import SDA, SCL
import busio
import adafruit_ssd1306 as ssd1306
from config import OLED as OLEDConfig


class OLED():
    def __init__(self):
        self.i2c = busio.I2C(SCL, SDA)
        self.oled = ssd1306.SSD1306_I2C(OLEDConfig.HEIGHT, OLEDConfig.WIDTH, self.i2c)
        self.oled.fill(0)
        self.oled.show()
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
    def center_text(self, txt, y):
        # Clear frame buffer
        self.oled.fill(0)
        x = (OLEDConfig.WIDTH - len(txt) * 8) // 2

        self.oled.rect(0, 0, OLEDConfig.WIDTH, OLEDConfig.HEIGHT, 1)
        self.oled.text(txt, x, y, 1)
        self.oled.show()
