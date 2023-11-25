import socket
import threading
import time
import random
import re


class Microphone:
    def __init__(self, phone_id) -> None:
        self.phoneid = phone_id
        self.people = None
        self.content = None
        self.speech_judgement = None


    def input(self, people, content):
        self.people = people
        self.content = content
        self.speech_judgement = 'microphone'


    def get_phone_id(self):
        return self.phoneid



class Room:
    def __init__(self) -> None:
        self.threadlist = []
        self.close_judgement = None
        self.people_judgement = None
        self.microphone = None
        self.room_members = []
        self.socketlist = []
        self.phonelist = []
        self.room_history = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.roomip = 'localhost'
        self.port = random.randint(10000, 20000)


    def add_microphone(self, phones: list):
        for phone in phones:
            assert phone.phoneid is not None
            self.phonelist.append(phone)


    def get_microphone(self):
        if not self.phonelist:
            return None
        phone = self.phonelist[0]
        del self.phonelist[0]
        return phone


    def return_microphone(self, phone):
        self.phonelist.append(phone)


    def how_many_people(self):
        time.sleep(0.1)
        if self.people_judgement == 'leave' or \
                self.people_judgement == 'join':
            print(self.room_members)
            self.people_judgement = 0
            return len(self.room_members)


    def how_many_microphone(self):
        return len(self.phonelist)


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
        msg = f"[{self.microphone.phoneid}][{self.microphone.people}]: " \
              f"{self.microphone.content}"
        self.room_history.append(msg)
        return self.room_history[-1]


    def send_content(self, microphone):
        for phone in self.phonelist:
            if phone.speech_judgement == 'microphone':
                self.microphone = phone
                self.microphone.speech_judgement = None
                break
        if microphone is None:
            print('microphone is None')
            return None
        num = 0
        for roomsocket in self.socketlist:
            try:
                sendmsg = f"[{microphone.people}]: {microphone.content}".encode('utf-8')
                print(f'向用户 {self.room_members[num]}发送:{sendmsg}')
                roomsocket.send(sendmsg)  # 广播people发送的信息
            except OSError:
                print(self.socketlist.index(roomsocket))
                print('选择了已关闭的套接字')
            num = num + 1



    def open(self):

        def getrecvmsg(num, room_num):
            while True:
                try:
                    recvmsg = self.socketlist[num].recv(1024).decode('utf-8')  # 接收phoneid和content
                    if self.close_judgement == 1:
                        break
                except OSError:
                    break
                if str(recvmsg) is not None:
                    select_results = re.match('function:{(.*)}'
                                              'data:(.*)', str(recvmsg))
                    if select_results is None:
                        print('select_results is None')
                        self.microphone = None
                        print('Server shutdown')
                        continue
                    elif select_results.group(1) == 'talk':
                        data = select_results.group(2)
                        talkcontent = re.match('(\w*)\s(.*)', data)
                        phoneid = talkcontent.group(1)
                        content = talkcontent.group(2)
                        self.microphone = Microphone(phoneid)
                        self.microphone.input(self.room_members[room_num], content)
                        microphone = self.microphone
                        self.send_content(microphone)
                    elif select_results.group(1) == 'leave':
                        self.room_members.remove(str(name.decode('utf-8')))
                        self.socketlist[num].close()
                        print(f'客户端已关闭 {address}')
                        try:
                            self.socketlist[num].send(b'data')
                            raise AssertionError('套接字未关闭')
                        except OSError:
                            print('套接字已关闭')

                        del self.socketlist[num]
                        self.people_judgement = 'leave'
                        break
        try:
            self.socket.bind((self.roomip, self.port))
            self.socket.listen()
        except OSError:
            pass

        while True:
            try:
                if self.close_judgement == 1:
                    print("Server shutdown")
                    break
                roomsocket, address = self.socket.accept()
                self.socketlist.append(roomsocket)
                print(f'有新的客户端连接{address}')
                num = len(self.socketlist) - 1
                name = roomsocket.recv(1024)  # 接收名字
                room_num = len(self.room_members)
                # 备注：先接收名字再接收phoneid和content
                if name:
                    self.room_members.append(str(name.decode('utf-8')))
                    self.people_judgement = 'join'
                sub_thread = threading.Thread(target=getrecvmsg, args=(num, room_num), daemon=True) # people.talk()以后执行
                sub_thread.start()
                self.threadlist.append(sub_thread)
            except OSError:
                print("Server shutdown")
                break


    def close(self):
        for i in self.socketlist:
            try:
               i.send(b'close')
            except OSError:
                pass
            i.close()
        self.socket.close()
        self.close_judgement = 1



class People:
    def __init__(self, name) -> None:
        self.room = None
        self.recvmsglist = []
        self.name = name
        self.sub_thread = None
        self.recvmsg = None

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
                if recvmsg == b'close':
                    self.room.close()
                    break
                if recvmsg == b'':
                    break
                if recvmsg is not None:
                    self.recvmsg = str(recvmsg.decode('utf-8'))
                    self.recvmsglist.append(self.recvmsg)
                    print({self.name}, self.recvmsg)

        self.sub_thread = threading.Thread(target=wait_for_message, daemon=True)
        self.sub_thread.start()

    def leave(self):
        self.room.send(str('function:{leave}'
                           'data:').encode('utf-8'))
        self.recvmsg = None
        self.room.close()
        self.recvmsglist = []
        print('套接字发送关闭请求')
        self.sub_thread.join()


    def talk(self, microphone, content):
        time.sleep(0.01)
        self.room.send(str('function:{talk}'
                           'data:' + microphone.phoneid + ' ' + content).encode('utf-8'))  # 发送phoneid和content


    def hear(self):
        time.sleep(0.02)
        if self.recvmsglist is None:
            return None
        try:
            return self.recvmsglist.pop(0)
        except IndexError:
            return None

