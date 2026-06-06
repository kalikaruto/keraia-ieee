# wifi_manager.py

import network
import socket
import time
import _thread
import oled


class WiFiManager:

    def __init__(
        self,
        mode,
        ssid="ESP32_LINK",
        password="12345678",
        ip="192.168.4.1",
        port=5000,
    ):

        self.mode = mode
        self.ssid = ssid
        self.password = password
        self.ip = ip
        self.port = port

        self.sock = None
        self.conn = None

        self.rx_callback = None

    def start(self):

        if self.mode == "ap":
            self._start_ap()

        elif self.mode == "sta":
            self._start_sta()

    def _start_ap(self):
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.ifconfig((
            self.ip,
            "255.255.255.0",
            self.ip,
            self.ip
        ))
        ap.config(
            ssid=self.ssid,
            password=self.password,
            authmode=3
        )
        while not ap.active():
            time.sleep(0.1)
        print("AP READY")
        print(ap.ifconfig())
        oled.oled.clear_buf()
        oled.oled.center_text("AP Ready", 21)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.port))          # '' instead of specific IP
        self.sock.listen(1)
        print("WAITING FOR CLIENT")
        oled.oled.center_text("Waiting For Client", 42)

        while True:
            try:
                self.conn, addr = self.sock.accept()
                print("CLIENT:", addr)
                break
            except OSError as e:
                print("Waiting...", e)
                time.sleep(0.5)

        _thread.start_new_thread(self._rx_loop, ())

    def _start_sta(self):

        sta = network.WLAN(network.STA_IF)

        sta.active(True)

        if not sta.isconnected():

            sta.connect(self.ssid, self.password)
            oled.oled.clear_buf()
            oled.oled.center_text("CONNECTING...", 21)
            while not sta.isconnected():
                print("CONNECTING...")
                time.sleep(1)

        print("CONNECTED")
        oled.oled.center_text("CONNECTED", 42)
        print(sta.ifconfig())

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        oled.oled.clear_buf()
        oled.oled.center_text("WAITING FOR SERVER", 21)
        while True:

            try:
                self.sock.connect((self.ip, self.port))
                break

            except:
                print("WAITING FOR SERVER")
                time.sleep(1)

        print("SERVER CONNECTED")
        oled.oled.center_text("SERVER CONNECTED", 42)

        _thread.start_new_thread(self._rx_loop, ())

    def _rx_loop(self):
        buffer = ""
        while True:
            try:
                if self.mode == "ap":
                    data = self.conn.recv(1024)
                else:
                    data = self.sock.recv(1024)
                if not data:
                    continue

                buffer += data.decode()

                # Process all complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    print("RX:", line)
                    if self.rx_callback:
                        self.rx_callback(line)

            except Exception as e:
                print("RX ERROR:", e)

    def send(self, msg):

        try:

            payload = (msg + "\n").encode()

            if self.mode == "ap":
                self.conn.send(payload)

            else:
                self.sock.send(payload)

        except Exception as e:
            print("SEND ERROR:", e)

    def on_receive(self, callback):
        self.rx_callback = callback
