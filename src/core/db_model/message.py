from mongoengine import *


class Message(Document):
    text = StringField(db_field='text', null=True)
