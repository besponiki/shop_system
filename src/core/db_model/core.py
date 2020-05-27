from mongoengine import *

from .message import Message


class Core(Document):
    random = BooleanField(db_field='random', default=True)
    messages = ListField(db_field='messages', field=ReferenceField(Message), default=list())

    bot_comission = FloatField(default=0.01)
    parent_comission = FloatField(default=0.09)
    structure_comission = FloatField(default=0.9)
    bot_balance = FloatField(default=0)

    bot_counter = IntField(default=1)

    category_row_num = IntField(default=5)
    category_col_num = IntField(default=1)

    subscribe_price = FloatField(default=1000)

    default_fields = ListField(default=['name', 'description', 'price', 'distributed_price'])
    order_counter = IntField(default=1)
    bitcoin_wallet = StringField(default='1KyetXBEUbiGvSPE1WG2ekPVV33Ba5nt6k')
    bip_minter_wallet = StringField(default='Mxebabbd2a666a4ef36472ef31775c9da8fa662078')
    ethereum_wallet = StringField(default='0xe3bc0360c13E6553792877B4E9f7f1763603507E')
    perfectmoney_wallet = StringField(default='U13036731')
    sber_wallet = StringField(default='4817 7601 1187 0386')

    presentation_path = StringField()
    image_id = IntField(default=1)
    shop_name_text = StringField(default='ShopSystem')

    bot_counter_2 = IntField(default=1)

    positional_id = IntField(default=1)

    tgs_bot_counter = IntField(default=0)
