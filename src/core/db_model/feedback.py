from mongoengine import *

import pytz

from ...tg_bot.db_model.user import User
from ...tg_bot.db_model.user_register import UserRegister


class Feedback(Document):
    user = ReferenceField(User, reverse_delete_rule=CASCADE)
    reg_user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    date = DateTimeField()
    is_new_question_exist = BooleanField(default=False)

    def formatted_date(self):
        local_datetime = self.date.astimezone(pytz.timezone('Europe/Moscow'))
        return local_datetime.strftime("%d.%m.%y %H:%M")


class Question(Document):
    feedback = ReferenceField(Feedback, reverse_delete_rule=CASCADE)
    date = DateTimeField()
    content_type = StringField()
    text = StringField()
    image_path = StringField()

    def formatted_date(self):
        local_datetime = self.date.astimezone(pytz.timezone('Europe/Moscow'))
        return local_datetime.strftime("%d.%m.%y %H:%M")


class Answer(Document):
    feedback = ReferenceField(Feedback, reverse_delete_rule=CASCADE)
    date = DateTimeField()
    text = StringField()
    image_path = StringField()

    def formatted_date(self):
        local_datetime = self.date.astimezone(pytz.timezone('Europe/Moscow'))
        return local_datetime.strftime("%d.%m.%y %H:%M")
