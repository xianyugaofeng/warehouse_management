import threading
import unittest
import sys
from main import Room, Microphone, People
import time
sys.path.append("..")


class TestChatRoom(unittest.TestCase):

    def setUp(self):
        self.test_room = Room()
        threading.Thread(target=self.test_room.open).start()

    def tearDown(self):
        self.test_room.close()
        self.test_room = None

    def test_people_join(self):
        john = People("John")
        john.join(self.test_room)
        assert self.test_room.how_many_people() == 1

    def test_people_leave(self):
        john = People("John")
        john.join(self.test_room)
        john.leave()
        assert self.test_room.how_many_people() == 0

    def test_add_and_get_microphone(self):
        phone_a = Microphone("A")
        self.test_room.add_microphone([phone_a])
        assert self.test_room.how_many_microphone() == 1
        phone = self.test_room.get_microphone()
        assert phone.get_phone_id() == phone_a.get_phone_id()
        assert self.test_room.get_microphone() == None

    def test_get_and_return_microphone(self):
        phone = Microphone("A")
        self.test_room.add_microphone([phone])
        assert self.test_room.get_microphone()
        assert self.test_room.get_microphone() == None
        self.test_room.return_microphone(phone)
        assert self.test_room.get_microphone()

    def test_test_single_microphone(self):
        phone_a = Microphone("A")
        self.test_room.add_microphone([phone_a])
        phone_a.input("TEST", "Hi")
        assert self.test_room.broadcast() == "[A][TEST]: Hi"

    def test_no_microphone(self):
        phone_a = Microphone("A")
        phone_a.input("TEST", "Hi")
        assert self.test_room.broadcast() == None

    def test_test_microphones(self):
        phone_a = Microphone("A")
        phone_b = Microphone("B")
        self.test_room.add_microphone([phone_a, phone_b])
        phone_a.input("TEST", "Hi")
        phone_b.input("TEST", "Hi")
        assert self.test_room.broadcast() == "[A][TEST]: Hi"
        assert self.test_room.broadcast() == "[B][TEST]: Hi"

    def test_people_want_to_talk(self):
        self.test_room.add_microphone([Microphone("A")])
        john = People("John")
        john.join(self.test_room)
        microphone = self.test_room.get_microphone()
        john.talk(microphone, "I'm John.")
        assert self.test_room.broadcast() == f"[{microphone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."

    def test_people_share_microphone(self):
        self.test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(self.test_room)
        jimmy.join(self.test_room)

        phone = self.test_room.get_microphone()

        john.talk(phone, "I'm John.")
        assert self.test_room.broadcast() == f"[{phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

        jimmy.talk(phone, "I'm Jimmy.")
        assert self.test_room.broadcast() == f"[{phone.get_phone_id()}][Jimmy]: I'm Jimmy."
        assert john.hear() == "[Jimmy]: I'm Jimmy."
        assert jimmy.hear() == "[Jimmy]: I'm Jimmy."

    def test_two_people_but_only_one_talk(self):
        self.test_room.add_microphone([Microphone("A")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(self.test_room)
        jimmy.join(self.test_room)
        microphone = self.test_room.get_microphone()
        john.talk(microphone, "I'm John.")
        assert self.test_room.broadcast() == f"[{microphone.get_phone_id()}][John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

    def test_lots_of_people(self):
        self.test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        guys = [People("Jimmy"), People("Andy"), People("Eric"), People("Ken"), People("Bob")]
        john.join(self.test_room)
        for guy in guys:
            guy.join(self.test_room)

        phone = self.test_room.get_microphone()

        john.talk(phone, "I'm John.")
        assert self.test_room.broadcast() == f"[{phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        for guy in guys:
            assert guy.hear() == "[John]: I'm John."

    def test_two_people_chat(self):
        self.test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(self.test_room)
        jimmy.join(self.test_room)
        john_phone = self.test_room.get_microphone()
        jimmy_phone = self.test_room.get_microphone()

        john.talk(john_phone, "I'm John.")
        assert self.test_room.broadcast() == f"[{john_phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

        jimmy.talk(jimmy_phone, "I'm Jimmy.")
        assert self.test_room.broadcast() == f"[{jimmy_phone.get_phone_id()}][Jimmy]: I'm Jimmy."
        assert john.hear() == "[Jimmy]: I'm Jimmy."
        assert jimmy.hear() == "[Jimmy]: I'm Jimmy."

    def test_one_people_leave_room(self):
        self.test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(self.test_room)
        jimmy.join(self.test_room)

        phone = self.test_room.get_microphone()

        john.talk(phone, "I'm John.")
        assert self.test_room.broadcast() == f"[{phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

        jimmy.leave()

        john.talk(phone, "Hi, Jimmy?")
        assert self.test_room.broadcast() == f"[{phone.get_phone_id()}][John]: Hi, Jimmy?"
        assert john.hear() == "[John]: Hi, Jimmy?"
        assert jimmy.hear() == None


if __name__ == '__main__':
    unittest.main()
