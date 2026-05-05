from machine import Pin, SPI, UART
import ssd1309

# -------- OLED (YOUR PINS) --------
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

# -------- GPS UART --------
uart = UART(0, 9600)
uart.init(9600, bits=8, parity=None, stop=1, tx=Pin(0), rx=Pin(1))

buffer = ""

def convert_to_decimal(raw, direction):
    if direction in ['N','S']:
        degrees = int(raw[0:2])
        minutes = float(raw[2:])
    else:
        degrees = int(raw[0:3])
        minutes = float(raw[3:])
    decimal = degrees + (minutes / 60)
    if direction in ['S','W']:
        decimal = -decimal
    return decimal

oled.fill(0)
oled.text("Waiting GPS...", 0, 25)
oled.show()

while True:
    if uart.any():
        char = uart.read(1).decode('utf-8', 'ignore')
        
        if char == '\n':
            line = buffer.strip()
            buffer = ""
            
            if line.startswith("$GPGLL"):
                parts = line.split(',')
                
                if parts[6] == 'A':
                    lat = convert_to_decimal(parts[1], parts[2])
                    lon = convert_to_decimal(parts[3], parts[4])
                    
                    oled.fill(0)
                    oled.text("Lat:", 0, 0)
                    oled.text(str(lat), 0, 15)
                    oled.text("Lon:", 0, 35)
                    oled.text(str(lon), 0, 50)
                    oled.show()
        else:
            buffer += char
