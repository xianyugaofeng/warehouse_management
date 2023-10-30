import unittest
import sys
sys.path.append("..")

from main import Room, People, Microphone


class TestChatRoom(unittest.TestCase):

    def test_people_join(self):
        test_room = Room()
        john = People("John")
        john.join(test_room)
        assert test_room.how_many_people() == 1

    def test_people_leave(self):
        test_room = Room()
        john = People("John")
        john.join(test_room)
        john.leave()
        assert test_room.how_many_people() == 0

    def test_add_and_get_microphone(self):
        test_room = Room()
        phone_a = Microphone("A")
        test_room.add_microphone(phone_a)
        assert test_room.how_many_microphone() == 1
        phone = test_room.get_microphone()
        assert phone.get_phone_id() == phone_a.get_phone_id()
        assert test_room.get_microphone() == None

    def test_get_and_return_microphone(self):
        test_room = Room()
        phone = Microphone("A")
        test_room.add_microphone(phone)
        assert test_room.get_microphone()
        assert test_room.get_microphone() == None
        test_room.return_microphone(phone)
        assert test_room.get_microphone()

    def test_test_single_microphone(self):
        test_room = Room()
        phone_a = Microphone("A")
        test_room.add_microphone([phone_a])
        phone_a.input("TEST", "Hi")
        assert test_room.broadcast() == "[A][TEST]: Hi"

    def test_no_microphone(self):
        test_room = Room()
        phone_a = Microphone("A")
        phone_a.input("TEST", "Hi")
        assert test_room.broadcast() == None

    def test_test_microphones(self):
        test_room = Room()
        phone_a = Microphone("A")
        phone_b = Microphone("B")
        test_room.add_microphone([phone_a, phone_b])
        phone_a.input("TEST", "Hi")
        phone_b.input("TEST", "Hi")
        assert test_room.broadcast() == "[A][TEST]: Hi"
        assert test_room.broadcast() == "[B][TEST]: Hi"

    def test_people_want_to_talk(self):
        test_room = Room()
        test_room.add_microphone([Microphone("A")])
        john = People("John")
        john.join(test_room)
        microphone = test_room.get_microphone()
        john.talk(microphone, "I'm John.")
        assert test_room.broadcast() == f"[{microphone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."

    def test_people_share_microphone(self):
        test_room = Room()
        test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(test_room)
        jimmy.join(test_room)

        phone = test_room.get_microphone()

        john.talk(phone, "I'm John.")
        assert test_room.broadcast() == f"[{phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

        jimmy.talk(phone, "I'm Jimmy.")
        assert test_room.broadcast() == f"[{phone.get_phone_id()}][Jimmy]: I'm Jimmy."
        assert john.hear() == "[Jimmy]: I'm Jimmy."
        assert jimmy.hear() == "[Jimmy]: I'm Jimmy."

    def test_two_people_but_only_one_talk(self):
        test_room = Room()
        test_room.add_microphone([Microphone("A")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(test_room)
        jimmy.join(test_room)
        microphone = test_room.get_microphone()
        john.talk(microphone, "I'm John.")
        assert test_room.broadcast() == f"[{microphone.get_phone_id()}][John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

    def test_lots_of_people(self):
        test_room = Room()
        test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        guys = [People("Jimmy"), People("Andy"),  People("Eric"), People("Ken"), People("Bob")]
        john.join(test_room)
        for guy in guys:
            guy.join(test_room)

        phone = test_room.get_microphone()

        john.talk(phone, "I'm John.")
        assert test_room.broadcast() == f"[{phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        for guy in guys:
            assert guy.hear() == "[John]: I'm John."

    def test_two_people_chat(self):
        test_room = Room()
        test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(test_room)
        jimmy.join(test_room)
        john_phone = test_room.get_microphone()
        jimmy_phone = test_room.get_microphone()

        john.talk(john_phone, "I'm John.")
        assert test_room.broadcast() == f"[{john_phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

        jimmy.talk(jimmy_phone, "I'm Jimmy.")
        assert test_room.broadcast() == f"[{jimmy_phone.get_phone_id()}][Jimmy]: I'm Jimmy."
        assert john.hear() == "[Jimmy]: I'm Jimmy."
        assert jimmy.hear() == "[Jimmy]: I'm Jimmy."

    def test_one_people_leave_room(self):
        test_room = Room()
        test_room.add_microphone([Microphone("A"), Microphone("B")])
        john = People("John")
        jimmy = People("Jimmy")
        john.join(test_room)
        jimmy.join(test_room)

        phone = test_room.get_microphone()

        john.talk(phone, "I'm John.")
        assert test_room.broadcast() == f"[{phone.get_phone_id()}][John]: I'm John."
        assert john.hear() == "[John]: I'm John."
        assert jimmy.hear() == "[John]: I'm John."

        jimmy.leave()

        john.talk(phone, "Hi, Jimmy?")
        assert test_room.broadcast() == f"[{phone.get_phone_id()}][John]: Hi, Jimmy?"
        assert john.hear() == "[John]: Hi, Jimmy?"
        assert jimmy.hear() == None


        
if __name__ == '__main__':
    unittest.main()