from mongoengine import *
from src.tg_bot.db_model.user_register import UserRegister
from .structure import Product


class Order(Document):
    good = ReferenceField(Product, reverse_delete_rule=NULLIFY)
    sum = FloatField()
    user = ReferenceField(UserRegister, reverse_delete_rule=NULLIFY)
    order_id = IntField()
    status = DictField()
    adres = StringField(default=None)
    date = DateTimeField()
    phone = StringField()
    is_accept = BooleanField(default=False)
    is_cancel = BooleanField(default=False)
    is_done = BooleanField(default=False)
    sailer = ReferenceField(UserRegister)
    reward = FloatField()
    counter = IntField(default=0)
