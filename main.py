import socket
import threading
import unittest
import time


class Microphone:
    def __init__(self, phone_id) -> None:
        self.phoneid = phone_id
        self.people = None
        self.content = None
        self.speech_judgement = None
        pass

    def input(self, people, content):
        self.people = people
        self.content = content
        self.speech_judgement = True
        pass

    def get_phone_id(self):
        return self.phoneid
        pass


class Room:
    def __init__(self) -> None:
        self.room_members = []
        self.socketlist = []
        self.phonelist = []
        self.phonemember = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.roomip = '127.0.0.1'
        self.port = 8080
        self.socket.bind((self.roomip, self.port))
        self.socket.listen(5)

    def add_microphone(self, phones: list):
        for phone in phones:
            assert phone.phoneid is not None
            self.phonelist.append(phone)
        pass

    def get_microphone(self):
        if not self.phonelist:
            return None
        self.phonemember = self.phonemember + 1
        phone = self.phonelist[0]
        del self.phonelist[0]
        return phone
        pass

    def return_microphone(self, phone):
        self.phonelist.append(phone)
        pass

    def how_many_people(self):
        time.sleep(0.01)
        print(self.room_members)
        return len(self.room_members)
        pass

    def how_many_microphone(self):
        return len(self.phonelist)
        pass

    def broadcast(self):
        for phone in self.phonelist:
            if phone.speech_judgement is True:
                for roomsocket in self.socketlist:
                    sendmsg = f"[{phone.phoneid}][{phone.people}]: {phone.content}".encode('utf-8')
                    roomsocket.send(sendmsg)
                phone.speech_judgement = 1
                return f"[{phone.phoneid}][{phone.people}]: {phone.content}"
        return None
        pass

    def open(self):
        def getrecvmsg(num):
            while True:
                try:
                    recvmsg = roomsocket.recv(1024).decode('utf-8')
                except OSError:
                    break
                if str(recvmsg) == 'leave':
                    del self.socketlist[num]
                    self.room_members.remove(str(name.decode('utf-8')))

        while True:
            try:
                roomsocket, address = self.socket.accept()
                self.socketlist.append(roomsocket)
                num = len(self.socketlist) - 1
                name = roomsocket.recv(1024)
                if name:
                    self.room_members.append(str(name.decode('utf-8')))
                threading.Thread(target=getrecvmsg, args=(num,)).start()
            except OSError:
                break
        pass

    def close(self):
        time.sleep(0.01)
        for i in range(len(self.socketlist)):
            self.socketlist[i].close()
            del self.socketlist[i]
        self.socket.close()
        pass


class People:
    def __init__(self, name) -> None:
        self.name = name
        self.room = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.recvmsg = None

    def join(self, room):
        self.room.connect((room.roomip, room.port))
        self.room.send(self.name.encode('utf-8'))

        def wait_for_message():
            self.room.send(b'i have joined')
            while True:
                try:
                    self.recvmsg = self.room.recv(1024)
                except OSError:
                    break
                if self.recvmsg == b'':
                    break
                self.recvmsg = str(self.recvmsg.decode('utf-8'))

        threading.Thread(target=wait_for_message).start()

    def leave(self):
        time.sleep(0.01)
        self.room.send(b'leave')
        self.room.close()
        pass

    def talk(self, microphone, content):
        pass

    def hear(self):
        return self.recvmsg
        pass
