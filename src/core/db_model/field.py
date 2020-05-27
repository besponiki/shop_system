from mongoengine import *
from ...tg_bot.db_model.user_register import UserRegister


class Field(Document):
    """ Unique fields for each RegisterUser
        Default must be created such classes as Name, Description,
        Price(with distributed price), DistributedPrice """
    user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    field_tag = StringField(required=True, null=False,)
    names = DictField(db_field='values', default=dict())
    value = StringField()
    is_required = BooleanField(default=False)
    message = DictField()
    priority = IntField(default=6)
    in_active = BooleanField(default=True)  # is_active
    is_moderated = BooleanField(default=True)
    # without moderation


class Photo(Document):
    """ Special field for photos """
    user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    field_tag = StringField(required=True, null=False)
    names = DictField(db_field='values', default=dict())
    paths = ListField(StringField())
