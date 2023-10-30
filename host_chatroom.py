import socket
from tkinter import *
import threading


class Host:
    def __init__(self):
        self.socket = None
        self.socketlist = []
        self.user = {}

    def setup(self):
        host = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hostip = '127.0.0.1'
        port = 8080
        host.bind((hostip, port))
        host.listen(5)
        self.socket = host

    def wait_for_access(self):
        while True:
            hostsocket, address = self.socket.accept()
            self.socketlist.append(hostsocket)
            print(f'有新的客户端{address}连接')

    def broadcast(self):
        sendmsg = '欢迎来到聊天室'.encode('utf-8')
        for i in self.socketlist:
            i.send(sendmsg)


"""           
root = Tk()
root.title('host')
root.resizable(True, False)
root.config(bg="white")
root.geometry("800x600")
textframe = Frame(root, bg='black', height=200, width=200)
textframe.pack(side='bottom')
root.mainloop()
"""

host = Host()
host.setup()
thread1 = threading.Thread(target=host.wait_for_access)
thread1.start()
while True:
    host.broadcast()
