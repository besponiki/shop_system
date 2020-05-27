from mongoengine import *
from ...tg_bot.db_model.user_register import UserRegister


class Category(Document):
    values = DictField(default=dict())
    # sub_categories = ListField(ReferenceField('Category'), default=list(), reverse_delete_rule=PULL)
    parent_category = ReferenceField('Category', default=None, reverse_delete_rule=CASCADE)
    category_row_num = IntField(default=5)
    category_col_num = IntField(default=2)
    priority = IntField(default=1)
    goods_num = IntField(default=0)
    message = StringField()
    is_moderated = BooleanField(default=False)
    creator = ReferenceField(UserRegister, default=None)
    # user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
