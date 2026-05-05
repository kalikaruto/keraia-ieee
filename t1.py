import socket

HOST = "0.0.0.0"
PORT = 5000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)

print("Waiting for Pico...")
conn, addr = server.accept()
print("Connected by:", addr)

try:
    while True:
        data = conn.recv(1024)
        if not data:
            break

        print(data.decode(errors="ignore"))

except KeyboardInterrupt:
    print("Stopped")

finally:
        conn.close()
        server.close()



