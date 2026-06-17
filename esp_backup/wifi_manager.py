import network
import socket
import ujson
import time
import _thread
import oled

import oled

class WiFiManager:

    HEADER_SIZE = 8

    def __init__(
        self,
        mode,
        ssid="ESP32_LINK",
        password="12345678",
        ip="192.168.4.1",
        port=5000,
        oled=oled,
    ):

        self.mode = mode

        self.ssid = ssid
        self.password = password

        self.ip = ip
        self.port = port

        self.sock = None
        self.conn = None

        self.ap = network.WLAN(network.AP_IF)
        self.sta = network.WLAN(network.STA_IF)

        self.rx_callback = None
        self.oled = oled

    def _wifi_reset(self):

        print("Resetting WiFi")

        self.ap.active(False)
        self.sta.active(False)

        time.sleep(1)

    def start(self):

        self.stop()

        self._wifi_reset()

        if self.mode == "ap":

            self._start_ap()

        else:

            self._start_sta()

        _thread.start_new_thread(
            self._rx_loop,
            ()
        )

    def send(self, packet):

        payload = ujson.dumps(packet).encode()

        header = "{:08d}".format(
            len(payload)
        ).encode()

        packet = header + payload

        if self.mode == "ap":

            self.conn.sendall(packet)

        else:

            self.sock.sendall(packet)

    def _recv_exact(self, sock, size):

        data = b""

        while len(data) < size:

            chunk = sock.recv(
                size - len(data)
            )

            if not chunk:

                raise OSError(
                    "Connection closed"
                )

            data += chunk

        return data

    def _recv_packet(self):

        if self.mode == "ap":
            sock = self.conn
        else:
            sock = self.sock

        header = self._recv_exact(
            sock,
            self.HEADER_SIZE
        )

        length = int(header.decode())

        payload = self._recv_exact(
            sock,
            length
        )

        return ujson.loads(
            payload.decode()
        )

    def _rx_loop(self):

        while True:

            try:

                packet = self._recv_packet()

                print("RX:", packet)

                if self.rx_callback:

                    self.rx_callback(
                        packet
                    )

            except Exception as e:

                print(
                    "RX ERROR:",
                    e
                )

                break

    def on_receive(
        self,
        callback
    ):

        self.rx_callback = callback

    def _start_ap(self):

        self.ap.active(True)

        self.ap.ifconfig((
            self.ip,
            "255.255.255.0",
            self.ip,
            self.ip
        ))

        self.ap.config(
            ssid=self.ssid,
            password=self.password,
            authmode=3
        )

        while not self.ap.active():
            time.sleep(0.1)

        print("AP READY")
        print(self.ap.ifconfig())

        self.oled.clear_buf()
        self.oled.text(
            "AP READY",
            10,
            21
        )

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.sock.bind(("", self.port))

        self.sock.listen(1)

        print("Waiting for client...")

        self.oled.text(
            "WAIT CLIENT",
            10,
            42
        )

        self.conn, addr = self.sock.accept()

        print("Client:", addr)

        self.oled.clear_buf()

        self.oled.text(
            "CLIENT OK",
            10,
            21
        )

    def _start_sta(self):

        self.sta.active(True)

        if not self.sta.isconnected():

            self.sta.connect(
                self.ssid,
                self.password
            )

            self.oled.clear_buf()

            self.oled.text(
                "CONNECTING",
                10,
                21
            )

            while not self.sta.isconnected():

                time.sleep(0.2)

        print("WiFi Connected")

        print(self.sta.ifconfig())

        self.oled.clear_buf()

        self.oled.text(
            "WIFI OK",
            10,
            21
        )

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        oled.oled.clear_buf()
        oled.oled.center_text("WAITING FOR SERVER", 21)
        while True:

            try:

                self.sock.connect(
                    (
                        self.ip,
                        self.port
                    )
                )

                break

            except OSError:

                print("Waiting for server...")

                time.sleep(1)

        print("Server Connected")

        self.oled.clear_buf()

        self.oled.text(
            "SERVER OK",
            10,
            21
        )


    def connected(self):

        try:

            if self.mode == "ap":

                return self.conn is not None

            return self.sta.isconnected()

        except:

            return False

    def stop(self):

        try:

            if self.conn:

                self.conn.close()

        except:
            pass

        try:

            if self.sock:

                self.sock.close()

        except:
            pass

        self.conn = None
        self.sock = None

        self.ap.active(False)
        self.sta.active(False)
