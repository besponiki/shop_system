from mongoengine import *
from ...core.db_model.structure import Product
from ...core.db_model.field import Field
from .user_register import UserRegister


class User(Document):
    user_id = IntField(required=True, unique=True)
    username = StringField()
    phone = StringField()
    mail = StringField()

    login = StringField()
    password = StringField()

    # boolechki
    is_authed = BooleanField(default=False)
    is_recover = BooleanField(default=False)
    is_phone = BooleanField(default=False)
    is_seller = BooleanField(default=False)
    is_in_settings = BooleanField(default=False)
    is_shop_info_check = BooleanField(default=False)
    is_search = BooleanField(default=False)
    from_cabinet = BooleanField(default=False)
    change_address = BooleanField(default=False)
    change_phone = BooleanField(default=False)
    password_three_wrong = BooleanField(default=False)
    low_price = BooleanField(default=False)
    negative_price = BooleanField(default=False)

    password_tries_counter = IntField(default=0)
    block_password_time = DateTimeField()

    auth_login = StringField()
    auth_password = StringField()

    first_name = StringField()
    last_name = StringField()
    referral_link = StringField(default='')

    state = StringField(max_length=50)
    user_lang = StringField(default='rus')

    advert_name = StringField()
    description = StringField()
    advert_price = FloatField()
    advert_distributed_price = FloatField()
    category = ReferenceField('Category', default=None, reverse_delete_rule=NULLIFY)
    choosed_category = ReferenceField('Category', default=None, reverse_delete_rule=NULLIFY)
    categories = ListField()

    msg_to_delete = IntField()
    msgs_to_del = ListField(IntField(), default=list())
    media_msgs_to_del = ListField(IntField(), default=list())
    txt_msg_to_edit = IntField()

    media_msg_to_edit = IntField()

    is_in_shop = BooleanField(default=False)
    target_good = ReferenceField(Product, reverse_delete_rule=NULLIFY)

    # values for enter advert fields
    fields_without_value = ListField()
    current_field = ReferenceField(Field, reverse_delete_rule=NULLIFY)
    entered_fields = ListField()

    adress = StringField()
    order_phone = StringField()
    target_good_for_buy = ReferenceField(Product, reverse_delete_rule=NULLIFY)

    cart = ListField()

    shared_product_id = StringField()

    structure_info = DictField()
    target_line = ListField()

    structure_referrals = DictField()   # {'good_id': 'reg_user_id'}

    wallets = DictField()
    choose_wallet = StringField()

    defaul_unregister_user = ReferenceField(UserRegister)
