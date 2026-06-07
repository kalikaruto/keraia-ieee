import network
import time
wlan = network.WLAN(network.STA_IF)
wlan.active(False)
time.sleep(1)
wlan.active(True)
#wlan.connect("Guest", "Holiday#2023@")