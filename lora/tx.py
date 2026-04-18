## TX


from machine import Pin, SPI
import time
import urandom
from lora import LoRa

rst = Pin(15, Pin.OUT)
rst.value(0)
time.sleep_ms(100)
rst.value(1)
time.sleep_ms(100)

spi = SPI(0,
          baudrate=10000000,
          polarity=0,
          phase=0,
          sck=Pin(18),
          mosi=Pin(19),
          miso=Pin(16))

lora = LoRa(
    spi,
    cs=Pin(17, Pin.OUT),
    rx=Pin(14, Pin.IN),
    frequency=433.0
)

def encode_packet_from_string(text: str) -> bytes:
    payload = text.encode('utf-8')  # deterministic encoding
    length = len(payload)

    checksum = length
    for b in payload:
        checksum ^= b

    return bytes([0xAA, length]) + payload + bytes([checksum])

while True:
    msg = "Hello LoRa"
    packet = encode_packet_from_string(msg)

    print("TX str:", msg)
    print("TX pkt:", packet.hex())

    lora.send(packet)
    time.sleep(1)
