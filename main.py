import socket
import threading


class Microphone:
    def __init__(self, phone_id) -> None:
        pass

    def input(self, people, content):
        pass

    def get_phone_id(self):
        pass


class Room:
    def __init__(self) -> None:
        self.socketlist = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        roomip = '127.0.0.1'
        port = 8080
        self.socket.bind((roomip, port))
        self.socket.listen(128)

    def add_microphone(self, phones: list):
        pass

    def get_microphone(self) -> Microphone:
        pass

    def return_microphone(self, phone):
        pass

    def how_many_people(self):
        for i in range(len(self.socketlist)):
            try:
                self.socketlist[i].send(b'send more data')
            except OSError:
                del self.socketlist[i]
            pass
        return len(self.socketlist)
        pass

    def how_many_microphone(self):
        pass

    def broadcast(self):
        pass

    def open(self):
        while True:
            roomsocket, address = self.socket.accept()
            self.socketlist.append(roomsocket)
        pass

    def close(self):
        pass


class People:

    def __init__(self, name) -> None:
        self.name = name
        self.room = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def join(self, room):

        pass

    def leave(self):
        pass

    def talk(self, microphone, content):
        pass

    def hear(self):
        pass
