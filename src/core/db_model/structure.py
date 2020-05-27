from mongoengine import *
from .core import Core
from ...tg_bot.db_model.user_register import UserRegister
from .category import Category
# from telebot import TeleBot
# from ...config import BOT_TOKEN
# from .text.text import Text
# from ...tg_bot.db_model.user import User


# product it is the same as advert
class Product(Document):
    """ Advert
        fields: default parameters ['name': str, 'description': str, 'price': str, 'reward': str]
        images: list(file_paths: str)
        is_validated: bool is it right
        is_moderated: bool is it view """
    fields = DictField()
    images = ListField(StringField())
    is_accepted = BooleanField(default=False)
    is_canceled = BooleanField(default=False)
    category = ReferenceField(Category, reverse_delete_rule=CASCADE)
    contact = StringField()
    structure_users = ListField()
    creator = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    is_day_good = BooleanField(default=False)
    is_active = BooleanField(default=True)


class ProductStructureUser(Document):
    user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    parent = ReferenceField('self', reverse_delete_rule=NULLIFY)
    positional_id = IntField()
    level = IntField()
    left_referrals_branch = ReferenceField('self', reverse_delete_rule=NULLIFY)
    right_referrals_branch = ReferenceField('self', reverse_delete_rule=NULLIFY)
    percent = FloatField()
    structure = ReferenceField(Product, reverse_delete_rule=CASCADE)
    referral_parent = ReferenceField('ProductStructureUser', default=None, reverse_delete_rule=NULLIFY)

    def univers_distribute_trading_pack(self, sum):
        core: Core = Core.objects.first()

        core.bot_balance += sum*core.bot_comission
        core.save()
        parent_sum = sum*core.parent_comission

        self.user.univers_distribute_general_pack(parent_sum, bot_comission=False, general_pack=False)

        sum = sum * (1 - (core.parent_comission + core.bot_comission))
        parent = self.referral_parent if self.referral_parent else self.parent
        # bot = TeleBot(BOT_TOKEN)
        data: dict = dict()
        if parent:

            parent_line, general_percents = parent.get_all_parents()
            # text = Text.objects(tag='distributed_product_cash').first()
            for par in parent_line:
                par.user.balance += sum * (par.percent / general_percents)
                par.user.earned_sum += sum * (par.percent / general_percents)
                try:
                    par.user.goods_structures_earned_sum[str(self.structure.id)] += sum * (par.percent / general_percents)
                except KeyError:
                    par.user.goods_structures_earned_sum[str(self.structure.id)] = sum * (par.percent / general_percents)

                # tgs = User.objects(auth_login=par.user.login)
                # for tg in tgs:
                #     bot.send_message(tg.user_id, text.values.get(tg.user_lang).format(par.login,
                #                                                                       sum * (par.percent / general_percents),
                #                                                                       self.structure.fields.get('name')),
                #                      parse_mode='markdown')

                par.save()
                data[str(par.id)] = sum * (par.percent / general_percents)

        else:
            self.user.balance += sum
            self.user.earned_sum += sum
            try:
                self.user.goods_structures_earned_sum[str(self.structure.id)] += sum
            except KeyError:
                self.user.goods_structures_earned_sum[str(self.structure.id)] = sum

        self.user.save()
        return data

    def get_all_parents(self):
        if self.parent:
            res, general_percents = self.parent.get_all_parents()
            res.append(self)
            general_percents += self.percent
            return (res, general_percents)
        else:
            return ([self], self.percent)


class ProductHistory(Document):
    user = ReferenceField(UserRegister, reverse_delete_rule=CASCADE)
    good = ReferenceField(Product, reverse_delete_rule=CASCADE)
    structure_user = ReferenceField(ProductStructureUser, reverse_delete_rule=CASCADE)
    date = DateTimeField()
