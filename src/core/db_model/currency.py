from mongoengine import *


class Currency(Document):
    values = DictField(db_field='values', default=dict())
    tag = StringField(unique=True)
