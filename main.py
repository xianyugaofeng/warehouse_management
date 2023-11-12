import socket
import threading
import unittest
import time
import re


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
        self.speech_judgement = 'microphone'
        pass

    def get_phone_id(self):
        return self.phoneid
        pass


class Room:
    def __init__(self) -> None:
        self.microphone = None
        self.lock1judge = None
        self.lock1 = threading.Condition()
        self.room_members = []
        self.socketlist = []
        self.phonelist = []
        self.shutdownsockets = []
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
        phone = self.phonelist[0]
        del self.phonelist[0]
        return phone
        pass

    def return_microphone(self, phone):
        self.phonelist.append(phone)
        pass

    def how_many_people(self):
        print(self.room_members)
        return len(self.room_members)
        pass

    def how_many_microphone(self):
        return len(self.phonelist)
        pass

    def broadcast(self):
        # 等待name和message中的phoneid和content全部传输完毕
        print(self.room_members)
        if self.lock1judge is None:
            self.lock1.acquire()
            self.lock1.wait()
            self.lock1.release()
        for phone in self.phonelist:
            if phone.speech_judgement == 'microphone':
                self.microphone = phone
                self.microphone.speech_judgement = None
                break
        if self.microphone is None:
            return None
        for roomsocket in self.socketlist:
            for i in self.shutdownsockets:
                if roomsocket == self.socketlist[i]:
                    continue
            sendmsg = f"[{self.microphone.people}]: {self.microphone.content}".encode('utf-8')
            roomsocket.send(sendmsg)  # 广播people发送的信息
        msg = f"[{self.microphone.phoneid}][{self.microphone.people}]: " \
              f"{self.microphone.content}"
        self.microphone = None
        print(msg)
        return msg
        pass

    def open(self):
        def getrecvmsg(num):
            while True:
                try:
                    recvmsg = self.socketlist[num].recv(1024).decode('utf-8')  # 接收phoneid和content
                    self.lock1judge = True
                    self.lock1.acquire()
                except OSError:
                    break
                if str(recvmsg) == 'leave':
                    self.room_members.remove(name.decode('utf-8'))
                    self.socketlist[num].close()
                    print(f'客户端已关闭 {address}')
                    try:
                        self.socketlist[num].send(b'data')
                        raise AssertionError('套接字未关闭')
                    except OSError:
                        print('套接字已关闭')
                        pass
                    break
                elif str(recvmsg) is not None:
                    select_results = re.match('(\w*)\s(.*)', str(recvmsg))
                    if select_results is None:
                        self.microphone = None
                        self.lock1.notify()
                        self.lock1.release()
                        continue
                    phoneid = select_results.group(1)
                    content = select_results.group(2)
                    self.microphone = Microphone(phoneid)
                    self.microphone.input(self.room_members[num], content)
                self.lock1.notify()
                self.lock1.release()
                pass

        while True:
            try:
                roomsocket, address = self.socket.accept()
                self.socketlist.append(roomsocket)
                print(f'有新的客户端连接{address}')
                num = len(self.socketlist) - 1
                name = roomsocket.recv(1024)  # 接收名字
                # 备注：先接收名字再接收phoneid和content
                if name:
                    self.room_members.append(str(name.decode('utf-8')))
                threading.Thread(target=getrecvmsg, args=(num,)).start()     # people.talk()以后执行
            except OSError:
                break
        pass

    def close(self):
        for i in range(len(self.socketlist)):
            self.socketlist[i].close()
        self.socket.close()
        pass


class People:
    def __init__(self, name) -> None:
        self.recvmsglist = []
        self.name = name
        self.room = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.recvmsg = None
        self.thread = None

    def join(self, room):
        self.room.connect((room.roomip, room.port))
        self.room.send(self.name.encode('utf-8'))  # 发送自己的名字

        def wait_for_message():
            while True:
                try:
                    self.recvmsg = self.room.recv(1024)
                except OSError:
                    break
                if self.recvmsg == b'':
                    break
                if self.recvmsg:
                    self.recvmsg = self.recvmsg.decode('utf-8')
                    self.recvmsglist.append(self.recvmsg)

        threading.Thread(target=wait_for_message).start()

    def leave(self):
        self.room.send(b'leave')
        self.recvmsg = None
        print('套接字发送关闭请求')
        pass

    def talk(self, microphone, content):
        self.room.send(str(microphone.phoneid + ' ' + content).encode('utf-8'))  # 发送phoneid和content
        pass

    def hear(self):
        # recvmsg = self.recvmsglist[0]
        # del self.recvmsglist[0]
        return self.recvmsg
        pass
