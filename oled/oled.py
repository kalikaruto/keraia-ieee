from machine import Pin, SPI
import ssd1309

spi = SPI(0,
          baudrate=10000000,
          polarity=0,
          phase=0,
          sck=Pin(18),
          mosi=Pin(19))

cs = Pin(17, Pin.OUT)
dc = Pin(16, Pin.OUT)
res = Pin(20, Pin.OUT)

oled = ssd1309.SSD1309(128, 64, spi, dc, res, cs)

oled.fill(0)
oled.text("================", 0, 0)
oled.text("IEEE APS", 0, 12)
oled.text("Team Keraia", 0, 24)
oled.text("(c) 2026", 0, 36)
oled.text("================", 0, 48)
oled.show()