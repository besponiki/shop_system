from mongoengine import *


class Secret(Document):
    user = StringField()
    value = StringField()
