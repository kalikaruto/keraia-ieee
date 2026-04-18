from machine import Pin, SPI
import time
from lora import LoRa

# Reset LoRa module
rst = Pin(15, Pin.OUT)
rst.value(0)
time.sleep_ms(100)
rst.value(1)
time.sleep_ms(100)

# SPI setup (same as TX)
spi = SPI(0,
          baudrate=10000000,
          polarity=0,
          phase=0,
          sck=Pin(18),
          mosi=Pin(19),
          miso=Pin(16))

# LoRa init (same frequency)
lora = LoRa(
    spi,
    cs=Pin(17, Pin.OUT),
    rx=Pin(14, Pin.IN),
    frequency=433.0
)

def decode_packet_to_string(packet: bytes):
    if len(packet) < 3:
        return None, "too short"

    if packet[0] != 0xAA:
        return None, "bad header"

    length = packet[1]

    if len(packet) != length + 3:
        return None, "length mismatch"

    payload = packet[2:-1]
    recv_checksum = packet[-1]

    calc_checksum = length
    for b in payload:
        calc_checksum ^= b

    if calc_checksum != recv_checksum:
        return None, "checksum error"

    try:
        return payload.decode('utf-8'), None
    except:
        return None, "decode error"

# Callback function for received data
def on_receive(data):
    text, err = decode_packet_to_string(data)

    if err:
        print("RX error:", err, data.hex())
        return

    print("RX str:", text)

# Start receiving
lora.recv(on_receive)

# Keep program alive
while True:
    time.sleep(1)
