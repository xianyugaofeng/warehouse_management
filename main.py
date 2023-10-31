import socket


class Microphone:
    def __init__(self, phone_id) -> None:
        pass

    def input(self, people, content):
        pass

    def get_phone_id(self):
        pass


class Room:
    def __init__(self) -> None:
        room = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pass

    def add_microphone(self, phones: list):
        pass

    def get_microphone(self) -> Microphone:
        pass

    def return_microphone(self, phone):
        pass

    def how_many_people(self):
        pass

    def how_many_microphone(self):
        pass

    def broadcast(self):
        pass

    def open(self):
        pass

    def close(self):
        pass

class People:

    def __init__(self, name) -> None:
        self.name = name
        self.room = None

    def join(self, room):
        pass

    def leave(self):
        pass

    def talk(self, microphone, content):
        pass

    def hear(self):
        pass