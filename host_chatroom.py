import socket
from tkinter import *
import threading


class Host:
    def __init__(self):
        self.socket = None
        self.socketlist = []

    def setup(self):
        host = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hostip = '127.0.0.1'
        port = 8080
        host.bind((hostip, port))
        host.listen(5)
        self.socket = host

    def waitforacess(self):
        while True:
            hostsocket, address = self.socket.accept()
            self.socketlist.append(hostsocket)
            print(f'有新的客户端{address}连接')

    thread1 = threading.Thread(target=waitforacess)
    thread1.start()
