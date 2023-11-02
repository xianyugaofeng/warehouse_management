import socket


class People:

    def __init__(self, name) -> None:
        self.name = name
        self.room = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def join(self, room):
        self.room.connect((room.hostip, room.port))
        pass

    def leave(self):
        self.room.close()
        pass

    def talk(self, microphone, content):
        pass

    def hear(self):
        pass