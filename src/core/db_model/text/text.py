from mongoengine import *
from ....config import APPLYING_WAYS


class Text(Document):
    values = DictField(db_field='values', default=dict())
    tag = StringField(db_field='tag', required=True, null=False, unique=True)
    applying_way = StringField(choices=APPLYING_WAYS, default=APPLYING_WAYS[0])
