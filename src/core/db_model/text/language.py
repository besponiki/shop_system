from mongoengine import *


class Language(Document):
    name = StringField(db_field='name', unique=True, required=True)
    tag = StringField(db_field='tag', unique=True, required=True)
    button_text = StringField(db_field='button_text', null=True)
