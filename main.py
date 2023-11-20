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
        time.sleep(0.1)
        # 等待name和message中的phoneid和content全部传输完毕
        print("聊天室成员：", self.room_members)
        for phone in self.phonelist:
            if phone.speech_judgement == 'microphone':
                self.microphone = phone
                self.microphone.speech_judgement = None
                break
        if self.microphone is None:
            print('microphone is None')
            return None
        for roomsocket in self.socketlist:
            roomsocket_loop = 0
            for i in self.shutdownsockets:
                if int(self.socketlist.index(roomsocket)) == int(i):
                    if i == len(self.socketlist) - 1:
                        roomsocket_loop = 2
                    else:
                        roomsocket_loop = 1
            if roomsocket_loop == 1:
                continue
            elif roomsocket_loop == 2:
                break
            try:
                sendmsg = f"[{self.microphone.people}]: {self.microphone.content}".encode('utf-8')
                roomsocket.send(sendmsg)  # 广播people发送的信息
            except OSError:
                print(self.socketlist.index(roomsocket))
                print('选择了已关闭的套接字')
        msg = f"[{self.microphone.phoneid}][{self.microphone.people}]: " \
              f"{self.microphone.content}"
        self.microphone = None
        return msg
        pass

    def open(self):
        def getrecvmsg(num, room_num):
            while True:
                try:
                    recvmsg = self.socketlist[num].recv(1024).decode('utf-8')  # 接收phoneid和content
                except OSError:
                    break
                if str(recvmsg) == 'leave':
                    self.room_members.remove(name.decode('utf-8'))
                    self.socketlist[num].close()
                    self.shutdownsockets.append(num)
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
                        print('select_results is None')
                        self.microphone = None
                        continue
                    phoneid = select_results.group(1)
                    content = select_results.group(2)
                    self.microphone = Microphone(phoneid)
                    self.microphone.input(self.room_members[room_num], content)
                pass

        while True:
            try:
                roomsocket, address = self.socket.accept()
                self.socketlist.append(roomsocket)
                print(f'有新的客户端连接{address}')
                num = len(self.socketlist) - 1
                name = roomsocket.recv(1024)  # 接收名字
                room_num = len(self.room_members)
                # 备注：先接收名字再接收phoneid和content
                if name:
                    self.room_members.append(str(name.decode('utf-8')))
                threading.Thread(target=getrecvmsg, args=(num, room_num)).start()  # people.talk()以后执行
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
        self.room = None
        self.recvmsglist = []
        self.name = name
        self.recvmsg = None
        self.thread = None

    def join(self, room):
        self.room = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.room.connect((room.roomip, room.port))
        self.room.send(self.name.encode('utf-8'))  # 发送自己的名字

        def wait_for_message():
            while True:
                try:
                    recvmsg = self.room.recv(1024)
                except OSError:
                    break
                if recvmsg == b'':
                    break
                if recvmsg is not None:
                    self.recvmsg = str(recvmsg.decode('utf-8'))
                    self.recvmsglist.append(self.recvmsg)
                    print({self.name}, self.recvmsglist[0])

        threading.Thread(target=wait_for_message).start()

    def leave(self):
        self.room.send(b'leave')
        self.recvmsg = None
        self.room.close()
        self.recvmsglist = []
        print('套接字发送关闭请求')
        pass

    def talk(self, microphone, content):
        self.room.send(str(microphone.phoneid + ' ' + content).encode('utf-8'))  # 发送phoneid和content
        pass

    def hear(self):
        time.sleep(0.02)
        if self.recvmsglist is None:
            pass
        recvmsglist = self.recvmsglist.copy()
        try:
            del self.recvmsglist[0]
            return recvmsglist[0]
        except IndexError:
            return None
        pass
