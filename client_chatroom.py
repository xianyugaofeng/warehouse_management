import socket


class Client:
    def __init__(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hostip = '127.0.0.1'
        port = 8080
        client.connect((hostip, port))
        self.socket = client

    def recv(self):
        recvmsg = self.socket.recv(1024)
        print(recvmsg.decode('utf-8'))


client = Client()
while True:
    client.recv()