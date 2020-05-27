from mongoengine import *
from ...tg_bot.db_model.user_register import UserRegister


class Comment(Document):
    reg_user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    comment = StringField()
    is_moderated = BooleanField(default=False)
    date = DateTimeField()
