import socket
import matplotlib.pyplot as plt

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", 9000))

plt.ion()
xs, zs = [], []

while True:
    data, _ = sock.recvfrom(1024)
    try:
        x, z = map(float, data.decode().split(","))
        xs.append(x)
        zs.append(z)

        xs = xs[-400:]
        zs = zs[-400:]

        plt.clf()
        plt.scatter(xs, zs, s=8)
        plt.ylim(-20, 20)
        plt.pause(0.01)
    except:
        pass
