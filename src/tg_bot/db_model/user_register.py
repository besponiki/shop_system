from mongoengine import *
from ...core.db_model.core import Core
# from telebot import TeleBot
# from ...config import BOT_TOKEN
# from .user import User
# from ...core.db_model.text.text import Text


class UserRegister(Document):
    login = StringField()
    password = StringField()
    positional_id = IntField()
    percent = FloatField()
    level = IntField()
    number_to_distribute = FloatField()
    distributed_cashback = FloatField()
    mail = StringField()
    phone = StringField()
    address = StringField()
    is_phone = BooleanField(default=False)
    parent = ReferenceField('UserRegister', default=None, reverse_delete_rule=NULLIFY)
    referral_parent = ReferenceField('UserRegister', default=None, reverse_delete_rule=NULLIFY)
    left_referrals_branch = ReferenceField('UserRegister', default=None, reverse_delete_rule=NULLIFY)
    right_referrals_branch = ReferenceField('UserRegister', default=None, reverse_delete_rule=NULLIFY)
    is_main_structure = BooleanField(default=False)
    referral_link = StringField(default='')

    structures = ListField()

    session_id = StringField(db_field='session_id')
    time_alive = FloatField(db_field='time_alive')

    partner_pannel_lang = StringField(default='rus')

    balance = FloatField(default=0)     # На счету
    input_sum = FloatField(default=0)   # Введено средств
    output_sum = FloatField(default=0)   # Выведено средств
    earned_sum = FloatField(default=0)   # Заработано
    structure_earned_sum = FloatField(default=0)  # Доход с главной структуры
    my_goods_earned_sum = DictField()    # {good_id: float} Доход от моих товаров
    goods_structures_earned_sum = DictField()        # {good_id: float} Доход от моих товарных сеток

    structure_referrals = DictField()   # {'good_id': 'reg_user_id'}

    wallets = DictField()
    choose_wallet = StringField()
    is_registered = BooleanField(default=False)  # до прохождения регистрации

    frozen_distribute_sum = FloatField(default=0) #  todo distribute this shit after subscribe

    is_reserved = BooleanField(default=False)

    def univers_distribute_general_pack(self, sum, bot_comission: bool = True, general_pack: bool = True):
        core: Core = Core.objects.first()

        if bot_comission:
            core.bot_balance += sum * core.bot_comission
            core.save()
            sum = sum * (1-core.bot_comission)

        parent = self.referral_parent if self.referral_parent else self.parent
        data: dict = dict()
        # bot = TeleBot(BOT_TOKEN)
        if parent:
            parent_line, general_percents = parent.get_all_parents()

            for par in parent_line:
                par.balance += sum * (par.percent/general_percents)
                par.earned_sum += sum * (par.percent/general_percents)
                par.structure_earned_sum += sum * (par.percent/general_percents)
                par.save()
                data[str(par.id)] = sum * (par.percent/general_percents)
                # tgs = User.objects(auth_login=par.login)
                # for tg in tgs:
                #     msg_to_del = bot.send_message(tg.user_id,
                #                                   Text.objects(tag='destributed_cash').first().values.get(tg.user_lang).format(par.login,
                #                                                                                                                sum * (par.percent/general_percents)))
                #     tg.msgs_to_del.append(msg_to_del.message_id)
                #     tg.save()

        else:
            if general_pack:
                self.balance += sum
                self.earned_sum += sum
                self.structure_earned_sum += sum
                self.save()
                data[str(self.id)] = sum
            else:
                self.frozen_distribute_sum += sum
                self.save()

        return data

    def get_all_parents(self):
        if self.is_reserved:
            if self.parent:
                res, general_percents = self.parent.get_all_parents()
                return (res, general_percents)

        if self.parent:
            res, general_percents = self.parent.get_all_parents()
            res.append(self)
            general_percents += self.percent
            return (res, general_percents)
        else:
            return ([self], self.percent)
