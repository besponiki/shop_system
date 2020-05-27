from mongoengine import *
from ...tg_bot.db_model.user_register import UserRegister
from ...tg_bot.db_model.user import User


class Frequent(Document):
    user = ReferenceField(User, reverse_delete_rule=CASCADE)
    reg_user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    question = StringField()
    answer = StringField()
    question_lang = DictField()
    answer_lang = DictField()
