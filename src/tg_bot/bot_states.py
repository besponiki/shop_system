import threading
import time
import datetime
import os
import re
import hashlib
import smtplib
from email.mime.text import MIMEText
from datetime import tzinfo, timedelta
from collections import Counter
import string
import random
import math
import phonenumbers
import logging
from multiprocessing import Pool

from ..core.db_model.feedback import Feedback, Question
from ..core.db_model.faq import Frequent
from ..core.db_model.currency import Currency
from ..core.db_model.comment import Comment
from ..core.db_model.field import Field, Photo

from telebot import types
from mongoengine.queryset.visitor import Q

from phonenumbers import carrier
from phonenumbers.phonenumberutil import number_type


from . import keyboards
from .state_handler import StateHandler


from .db_model.user import User
from .db_model.user_register import UserRegister
from .db_model.secret import Secret
from ..core.db_model.category import Category
from ..core.db_model.order import Order
from ..binary_referral_system import referrals_indent
from ..core.db_model.core import Core
from ..core.db_model.structure import Product, ProductStructureUser, ProductHistory
from ..core.db_model.message import Message
from .. import config
from ..core.db_model.text.text import Text
from ..core.db_model.text.language import Language


class BotStates(StateHandler):
    def __init__(self, bot):
        super(BotStates, self).__init__(bot)
        self._register_states([
            # all states
            self._start_state,

            self.auth_state,
            self.choose_recover_state,
            self.email_recover_state,
            self.phone_recover_state,

            self.login_state,
            self.log_password_state,
            self.login_finale_state,

            self.register_state,
            self.reg_with_phone_state,
            self.phone_validation_state,
            self.reg_with_email_state,
            self.email_validation_state,
            self.reg_password_state,
            self.reg_finale_state,

            self.buy_place_in_structure_state,

            self.main_menu_state,
            self.company_state,
            self.contacts_state,
            self.request_phone_state,
            self.cabinet_state,
            self.comments_state,
            self.leave_comment_state,
            self._category_state,
            self.my_goods_state,
            self.shop_state,
            self._buy_history_state,

            self.settings_state,
            self.enter_adres_state,
            self.enter_phone_state,

            self.enter_field_state,
            self.advert_finale,
            self.new_shop_state,
            self.feedback_state,
            self.pin_photo_to_advert,
            self.language_state,
            self.v_a_c_s,
            self.order_finale_state,
            self.choose_wallets_state,
            self.apply_to_del_state,
            self.enter_wallet_state,
        ])

        self._running = True

        self._kill_scheduling_event = threading.Event()
        self._kill_mailing_event = threading.Event()

        # mailing = threading.Thread(target=self._mailing)
        # mailing.daemon = True
        # mailing.start()

    def __del__(self):
        self._running = False
        self._kill_mailing_event.set()
        self._kill_scheduling_event.set()

    def _mailing(self):
        core: Core = Core.objects.first()

        if not core:
            core = Core()
            core.save()

        while self._running and not self._kill_mailing_event.is_set():
            if len(core.messages) != 0:
                message: Message = core.messages[0]
                try:
                    if message:
                        users = User.objects()

                        for user in users:
                            try:
                                self._bot.send_message(user.user_id, message.text, parse_mode='markdown')
                                time.sleep(0.5)
                            except Exception as e:
                                logging.exception(e)
                except Exception as e:
                    logging.exception(e)
                finally:
                    core.update(pop__messages=1)
                    core.reload()

            core.reload()
            time.sleep(5)

    def _start_state(self, message: types.Message, entry=False):
        core: Core = Core.objects.first()

        if not core:
            core = Core()
            core.save()

        user: User = User.objects(user_id=message.chat.id).first()
        if message.text.find('/start shareprod_') != -1:
            user_id, prod_id = [x for x in message.text[len('/start shareprod_'):].split('_')]
            if not user.is_authed:
                user.referral_link = '/start {0}'.format(user_id)

            user.shared_product_id = prod_id
            user.structure_referrals[prod_id] = user_id
            user.save()

        else:
            if not user.is_authed and len(message.text[7:]) == 24:
                user.referral_link = message.text
                user.save()

        keyboard = keyboards.remove_reply_keyboard()

        delete_message_hook = self._bot.send_message(
            message.chat.id,
            text='Loading...',
            parse_mode='markdown',
            reply_markup=keyboard
        )

        user.msg_to_delete = delete_message_hook.message_id
        user.save()
        self.delete_msgs(self._bot, user)
        self._go_to_state(message, 'language_state')

    def language_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            try:
                self._bot.delete_message(user.user_id, user.msg_to_delete)
            except Exception as e:
                print(e)
            text = self.locale_text(user_lang, 'choose_language')
            msg_to_edit = self._bot.send_message(user.user_id, text, reply_markup=keyboards.language_keyboard())
            # user.txt_msg_to_edit = msg_to_edit.message_id
            user.msgs_to_del.append(msg_to_edit.message_id)
            user.save()
        else:
            if call.data.find('language_state_inline_button_') != -1:
                ident = call.data[len('language_state_inline_button_'):]
                lang: Language = Language.objects(id=ident).first()
                user.user_lang = lang.tag
                user.save()
                self._go_to_state(message, 'main_menu_state')

    def auth_state(self, message, entry=False, call: types.CallbackQuery = None, no_del: bool = False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if user.is_authed:
            self.user_bool_clear(user)
            user.is_authed = False
            user.save()

            self._go_to_state(message, 'login_finale_state')
            return None
        else:
            self.user_clear(user)

        if entry:
            print('auth entry')
            print('user.from_cabinet : {}'.format(user.from_cabinet))
            text: str = self.locale_text(user_lang, 'auth_msg')
            keyboard = keyboards.auth_keyboard(user_lang)

            if not no_del:
                print('not no_del')
                self.delete_msgs(self._bot, user)
            if user.from_cabinet:
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

            if call:
                try:
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id, reply_markup=keyboard,
                                                parse_mode='markdown')
                    print('auth if call try')
                except Exception as e:
                    try:
                        self._bot.delete_message(user.user_id, call.message.message_id)
                        print('auth if call except try')
                    except Exception as e:
                        print('auth if call except except')
                        print(e)
            else:
                try:
                    self._bot.delete_message(
                        message.chat.id,
                        user.msg_to_delete
                    )
                except Exception as e:
                    print(e)

                msg = self._bot.send_message(
                    message.chat.id,
                    text=text,
                    parse_mode='markdown',
                    reply_markup=keyboard
                )
                user.msg_to_delete = int(msg.message_id)
                user.save()
        else:
            if call:
                if call.data == 'auth_state_$$_1_option':
                    self._go_to_state(message, 'login_state', call=call)
                elif call.data == 'auth_state_$$_2_option':
                    self._go_to_state(message, 'register_state', call=call)
                elif call.data == 'auth_state_$$_4_option':
                    self._go_to_state(message, 'choose_recover_state', call=call)

            else:
                core: Core = Core.objects.first()
                reg_user: UserRegister = UserRegister.objects(login = user.auth_login).first()
                if not reg_user:
                    reg_user = user.defaul_unregister_user
                if message.text == self.locale_text(user_lang, 'info_btn'):
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    text = self.locale_text(user_lang, 'info_msg')
                    keyboard = keyboards.cabinet_info_keyboard(user_lang)
                    msg_to_del = self._bot.send_message(user.user_id, text, reply_markup=keyboard,
                                                        parse_mode='markdown')

                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

                elif message.text == self.locale_text(user_lang, 'invite_friend_btn'):
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    text = self.locale_text(user.user_lang, 'ref_link_template').format(core.shop_name_text,
                                                                                        (str(reg_user.id)))
                    text_2 = self.locale_text(user_lang, 'invite_friend_first_msg')

                    msg_to_del = self._bot.send_message(user.user_id, text_2)
                    msg_to_del_1 = self._bot.send_message(user.user_id, text.format(str(reg_user.id)),
                                                          parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del_1.message_id)
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

                elif message.text == self.locale_text(user_lang, 'web_cabinet_btn'):
                    if not reg_user.is_registered:
                        self._go_to_state(message, 'auth_state')

                    else:
                        self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                           self.delete_msgs)
                        text = self.locale_text(user_lang, 'ur_cabinet').format(config.CABINET_LINK)
                        msg_to_del = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                        user.msgs_to_del.append(msg_to_del.message_id)
                        user.save()
                        # self._go_to_state(message, 'cabinet_state')

                elif message.text == self.locale_text(user_lang, 'activate_btn'):
                    if not reg_user.is_registered:
                        self._go_to_state(message, 'auth_state')

                    else:
                        self._go_to_state(message, 'cabinet_state')

                elif message.text == self.locale_text(user_lang, 'add_good'):
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    # self.delete_msgs(self._bot, user)
                    if not reg_user.is_main_structure:
                        text = self.locale_text(user_lang, 'activate_description')
                        msg = self._bot.send_message(user.user_id, text,
                                                     reply_markup=keyboards.buy_place_in_structure_keyboard(user_lang))
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                    else:
                        # self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                        user.category = None
                        user.choosed_category = None
                        user.target_good = None
                        user.is_in_shop = False
                        user.fields_without_value = Field.objects(Q(user=reg_user)
                                                                  & Q(in_active=True) &
                                                                  Q(is_moderated=True)).order_by('priority')
                        user.save()

                        text = self.locale_text(user_lang, 'add_good_choose_way_msg')
                        msg_to_del = self._bot.send_message(user.user_id, text,
                                                            reply_markup=keyboards.add_good_choose_way_keyboard(
                                                                user_lang),
                                                            parse_mode='markdown')
                        user.msgs_to_del.append(msg_to_del.message_id)
                        user.save()

                elif message.text == self.locale_text(user_lang, 'settings'):
                    self._go_to_state(message, 'settings_state')

                elif message.text == self.locale_text(user_lang, 'basket_btn'):
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    user.from_cabinet = True
                    user.save()
                    self._go_to_state(message, 'v_a_c_s')

                elif message.text == self.locale_text(user_lang, 'back_btn'):
                    user.from_cabinet = False
                    user.save()
                    self._go_to_state(message, 'main_menu_state')

                elif message.text == self.locale_text(user_lang, 'log_out_btn'):
                    self.delete_msgs(self._bot, user)

                    user.auth_login = ''
                    user.auth_password = ''
                    user.is_authed = False
                    user.from_cabinet = False
                    user.save()
                    text = self.locale_text(user_lang, 'logout_msg')
                    msg_to_del = self._bot.send_message(user.user_id, text,
                                                        reply_markup=keyboards.remove_reply_keyboard())
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                    reg_user.is_registered = False
                    reg_user.save()
                    self._go_to_state(message, 'main_menu_state')
                # msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'incorrect_msg'),
                #                                     reply_markup=types.ReplyKeyboardRemove())
                # user.msgs_to_del.append(msg_to_del.message_id)
                # user.save()
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)

                # self._go_to_state(message, 'auth_state')

    def choose_recover_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text: str = self.locale_text(user_lang, 'choose_recovery_type_msg')
            keyboard = keyboards.choose_recovery_type_keyboard(user_lang)

            if call:
                try:
                    self._bot.delete_message(
                        message.chat.id,
                        call.message.message_id
                    )
                except Exception as e:
                    print(e)
            # # self.delete_msgs(self._bot, user)
            msg = self._bot.send_message(
                chat_id=message.chat.id,
                text=text,
                parse_mode='markdown',
                reply_markup=keyboard
            )
            user.msg_to_delete = msg.message_id
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'recover_by_email_btn'):
                self._go_to_state(message, 'email_recover_state')
            elif message.text == self.locale_text(user_lang, 'cancel_msg'):
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'auth_state')

    def email_recover_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            try:
                self._bot.delete_message(
                    message.chat.id,
                    user.msg_to_delete
                )
            except Exception as e:
                print(e)
            self.delete_msgs(self._bot, user)

            text: str = self.locale_text(user_lang, 'email_recovery_msg')
            keyboard = keyboards.cancel_back(user_lang)

            msg = self._bot.send_message(
                message.chat.id,
                text=text,
                parse_mode='markdown',
                reply_markup=keyboard
            )
            user.msg_to_delete = int(msg.message_id)
            user.save()

        else:
            # replace cancel_btn, cancel_msg
            if message.text == self.locale_text(user_lang, 'back_btn'):
                try:
                    self._bot.delete_message(
                        message.chat.id,
                        user.msg_to_delete
                    )
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'choose_recover_state')
            elif message.text == self.locale_text(user_lang, 'cancel_msg'):
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'auth_state')
            elif message.text:
                email = message.text.lower()
                if not re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
                    try:
                        self._bot.delete_message(user.user_id, user.msg_to_delete)
                    except Exception as e:
                        print(e)
                    self.save_keyboard(self._bot, keyboards.cancel_back(user_lang), user, self.delete_msgs(self._bot, user))

                    text = self.locale_text(user_lang, 'request_mail_validation_error_msg')
                    msg_to_delete = self._bot.send_message(message.chat.id, text=text)
                    user.msgs_to_del.append(msg_to_delete.message_id)
                    user.save()
                else:
                    reg_user = UserRegister.objects(login=email).first()

                    if reg_user:
                        user.is_recover = True
                        user.auth_login = email.lower()
                        user.is_authed = True
                        user.save()
                        try:
                            self._bot.delete_message(user.user_id, user.msg_to_delete)
                        except Exception as e:
                            print(e)
                        self.delete_msgs(self._bot, user)

                        self._go_to_state(message, 'email_validation_state')
                    else:
                        try:
                            self._bot.delete_message(user.user_id, user.msg_to_delete)
                        except Exception as e:
                            print(e)
                        self.delete_msgs(self._bot, user)

                        text = self.locale_text(user_lang, 'wrong_mail_error_msg')
                        # self._bot.edit_message_text(
                        #     chat_id=message.chat.id,
                        #     message_id=message.message_id,
                        #     text=text
                        # )
                        msg = self._bot.send_message(message.chat.id, text=text)
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                        self._go_to_state(message, 'choose_recover_state')

    def phone_recover_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text = self.locale_text(user_lang, 'in_development_msg')

            self._bot.send_message(message.chat.id, text=text)
            self._go_to_state(message, 'choose_recover_state')

    def register_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text: str = self.locale_text(user_lang, 'register_msg')
            keyboard = keyboards.registration_keyboard(user_lang)

            if call:
                try:
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id, reply_markup=keyboard,
                                                parse_mode='markdown')
                except Exception as e:
                    try:
                        self._bot.delete_message(user.user_id, call.message.message_id)

                    except Exception as e:
                        print(e)

                    msg = self._bot.send_message(
                        chat_id=user.user_id,
                        text=text,
                        parse_mode='markdown',
                        reply_markup=keyboard
                    )

                    user.msg_to_delete = msg.message_id
                    user.save()

        else:
            if call:
                if call.data == 'register_state_$$_1_option':
                    self._go_to_state(message, 'reg_with_email_state', call=call)
                elif call.data == 'register_state_$$_3_option':
                    self._go_to_state(message, 'auth_state', call=call)

    def reg_with_phone_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text = self.locale_text(user_lang, 'in_development_msg')

            self._bot.send_message(message.chat.id, text=text)
            self._go_to_state(message, 'register_state')

    def phone_validation_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text = self.locale_text(user_lang, 'in_development_msg')

            self._bot.send_message(message.chat.id, text=text)
            self._go_to_state(message, 'auth_state')

    def reg_with_email_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text = self.locale_text(user_lang, 'request_mail_msg')
            keyboard = keyboards.email_request_keyboard(user_lang)
            if call:
                try:
                    self._bot.delete_message(
                        message.chat.id,
                        call.message.message_id
                    )
                except Exception as e:
                    print(e)

            msg = self._bot.send_message(
                chat_id=message.chat.id,
                text=text,
                parse_mode='markdown',
                reply_markup=keyboard
            )
            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'cancel_msg'):
                # self._bot.delete_message(message.chat.id, user.msg_to_delete)
                self._go_to_state(message, 'auth_state')
            else:
                email = message.text.lower()
                if not re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
                    text = self.locale_text(user_lang, 'request_mail_validation_error_msg')
                    self.save_keyboard(self._bot, keyboards.email_request_keyboard(user_lang),
                                       user, self.delete_msgs(self._bot, user))
                    try:
                        self._bot.delete_message(
                            message.chat.id,
                            user.msg_to_delete
                        )
                    except Exception as e:
                        print(e)

                    msg = self._bot.send_message(
                        chat_id=message.chat.id,
                        text=text,
                    )
                    user.msgs_to_del.append(msg.message_id)
                    user.save()
                else:
                    reg_user: UserRegister = UserRegister.objects(login=email.lower()).first()

                    if reg_user:
                        text = self.locale_text(user_lang, 'already_account_mail_msg')
                        try:
                            self._bot.delete_message(
                                message.chat.id,
                                user.msg_to_delete
                            )
                        except Exception as e:
                            print(e)
                        # self.delete_msgs(self._bot, user)
                        self.save_keyboard(self._bot, keyboards.email_request_keyboard(user_lang), user,
                                           self.delete_msgs(self._bot, user))
                        msg = self._bot.send_message(
                            chat_id=message.chat.id,
                            text=text
                        )
                        user.msg_to_delete = msg.message_id
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                        # self._bot.send_message(user.user_id, text)
                        # self._go_to_state(message, 'auth_state')

                    else:
                        user.mail = email
                        user.is_phone = False
                        user.save()
                        self.delete_msgs(self._bot, user)
                        try:
                            self._bot.delete_message(user.user_id, user.msg_to_delete)
                        except Exception as e:
                            print(e)

                        self._go_to_state(message, 'email_validation_state')

    def email_validation_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        # self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        if entry:
            try:
                self._bot.delete_message(user.user_id, user.msg_to_delete)
            except Exception as e:
                print(e)
            self.delete_msgs(self._bot, user)
            text = self.locale_text(user_lang, 'request_email_code_msg')
            msg = self._bot.send_message(message.chat.id, text=text)

            user.msgs_to_del.append(msg.message_id)
            user.save()

            secret = Secret()
            value = self.secret_generator()
            secret.value = hashlib.md5(value.encode('utf-8')).hexdigest()
            secret.user = str(user.user_id)
            secret.save()

            smtp = smtplib.SMTP('smtp.gmail.com', 587)
            smtp.starttls()
            smtp.login(config.EMAIL_LOGIN, config.EMAIL_PASSWORD)
            text1 = self.locale_text(user_lang, 'your_code_msg')
            msg = MIMEText(text1.format(value))
            msg['Subject'] = 'Auth message'
            msg['From'] = config.EMAIL_LOGIN

            if user.is_recover:
                to = reg_user.login
            else:
                to = user.mail

            msg['To'] = to
            smtp.send_message(from_addr=config.EMAIL_PASSWORD, to_addrs=to, msg=msg)
            smtp.quit()

        else:
            code = message.text
            secret: Secret = Secret.objects(value=hashlib.md5(code.encode('utf-8')).hexdigest()).first()
            if message.text == self.locale_text(user_lang, 'cancel_msg'):
                self._go_to_state(message, 'auth_state')
                secret.delete()
            elif secret:
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'reg_password_state')
                secret.delete()

            else:
                text = self.locale_text(user_lang, 'wrong_code_msg')
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)

                msg = self._bot.send_message(
                    chat_id=message.chat.id,
                    text=text,
                )
                user.msgs_to_del.append(msg.message_id)
                user.save()
                # secret.delete()
                # self._go_to_state(message, 'email_validation_state')

    def reg_password_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text = self.locale_text(user_lang, 'request_password_msg')
            keyboard = keyboards.password_request_keyboard(user_lang)

            msg = self._bot.send_message(
                message.chat.id,
                text=text,
                parse_mode='markdown',
                reply_markup=keyboard
            )

            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'cancel_msg'):
                self._go_to_state(message, 'auth_state')
            else:
                password = message.text

                if len(password) < 8 or len(password) > 64:
                    text = self.locale_text(user_lang, 'request_password_validation_error_msg')

                    try:
                        self._bot.delete_message(user.user_id, user.msg_to_delete)
                    except Exception as e:
                        print(e)

                    msg = self._bot.send_message(
                        chat_id=message.chat.id,
                        text=text,
                        parse_mode='markdown'
                    )
                    user.msg_to_delete = msg.message_id
                    user.save()
                else:
                    user.password = password
                    user.save()

                    try:
                        self._bot.delete_message(user.user_id, user.msg_to_delete)
                    except Exception as e:
                        print(e)

                    self._go_to_state(message, 'reg_finale_state')

    def reg_finale_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        core: Core = Core.objects.first()

        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        # self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        if user.is_recover:
            self._go_to_state(message, 'main_menu_state')
            user.is_recover = False
            user.auth_password = user.password
            user.save()

            reg_user.password = user.password
            # gmt = self.Zone(3, False, 'GMT')
            # reg_user.enter_history[str(user.user_id)] = datetime.datetime.now(gmt)
            reg_user.save()

            return None

        reg_user = UserRegister.objects(login=user.mail).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
            if not reg_user:
                reg_user = UserRegister()
        reg_user.login = user.phone if user.is_phone else user.mail
        reg_user.password = user.password
        reg_user.phone = user.phone if user.is_phone else None
        reg_user.is_registered = True
        reg_user.save()
        # referrals_indent.referrals_indent(user, reg_user)

        self.create_default_fields(reg_user, self.locale_text)
        #   встать в структуру дефолт
        # reg_user.number_to_distribute = core.subscribe_price
        # reg_user.save()
        # text = self.locale_text(user_lang, 'buy_info_msg')
        # self.distribute_percents(reg_user, self._bot, text=text)
        # reg_user.is_main_structure = True
        reg_user.save()
        # gmt = self.Zone(3, False, 'GMT')
        # reg_user.enter_history[str(user.user_id)] = datetime.datetime.now(gmt)
        # reg_user.save()

        # core.api_mail_counter += 1
        # core.save()
        user.auth_login = user.phone if user.is_phone else user.mail
        user.is_authed = True
        user.auth_password = user.password
        user.login = None
        user.password = None
        user.save()
        try:
            self._bot.delete_message(user.user_id, user.msg_to_delete)
        except Exception as e:
            print(e)

        self._go_to_state(message, 'cabinet_state')

    def login_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            text: str = self.locale_text(user_lang, 'login_msg')
            keyboard = keyboards.login_keyboard(user_lang)

            if call:
                try:
                    self._bot.delete_message(
                        message.chat.id,
                        call.message.message_id
                    )
                except Exception as e:
                    print(e)

            msg = self._bot.send_message(
                message.chat.id,
                text=text,
                parse_mode='markdown',
                reply_markup=keyboard
            )
            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'cancel_msg'):
                self._go_to_state(message, 'auth_state')
            else:
                reg_user = UserRegister.objects(login=message.text.lower()).first()
                if user.change_address or user.change_phone:
                    if not reg_user or reg_user.login != user.auth_login:
                        text = self.locale_text(user_lang, 'no_user_with_this_login_msg')
                        self.save_keyboard(self._bot, keyboards.login_keyboard(user_lang), user,
                                           self.delete_msgs(self._bot, user))
                        msg = self._bot.send_message(user.user_id, text)
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                        self._go_to_state(message, 'login_state')
                        return None

                if not reg_user:
                    contact = str(message.text)
                    reg_user = User.objects(login=str('+' + contact)).first()
                    if not reg_user:
                        text = self.locale_text(user_lang, 'no_user_with_this_login_msg')
                        self.save_keyboard(self._bot, keyboards.login_keyboard(user_lang), user,
                                           self.delete_msgs(self._bot, user))
                        msg = self._bot.send_message(user.user_id, text)
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                        self._go_to_state(message, 'login_state')
                    else:
                        user.auth_login = '+' + contact
                        user.save()
                        try:
                            self._bot.delete_message(user.user_id, user.msg_to_delete)
                        except Exception as e:
                            print(e)

                        self._go_to_state(message, 'log_password_state')
                else:
                    user.auth_login = message.text.lower()
                    user.save()
                    try:
                        self._bot.delete_message(user.user_id, user.msg_to_delete)
                    except Exception as e:
                        print(e)

                    self._go_to_state(message, 'log_password_state')

    def log_password_state(self, message, entry=False, no_del: bool = False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
        if not reg_user.is_registered and (user.change_phone or user.change_address):
            self._go_to_state(message, 'login_finale_state')
            return None
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        if entry:
            print('user.change_phone: {0}\nChange_address: {1}\nis in settings: {2}'.format(user.change_phone,
                                                                                            user.change_address,
                                                                                            user.is_in_settings))
            text: str = self.locale_text(user_lang, 'login_pass_msg')
            keyboard = keyboards.log_pass_keyboard(user_lang)
            if not no_del:
                self.delete_msgs(self._bot, user)
            msg = self._bot.send_message(
                message.chat.id,
                text=text,
                parse_mode='markdown',
                reply_markup=keyboard
            )
            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'cancel_msg'):
                text: str = self.locale_text(user_lang, 'canceled_msg')
                if user.change_address or user.change_phone:
                    if user.is_in_settings:
                        self._go_to_state(message, 'settings_state')
                    else:
                        self._go_to_state(message, 'v_a_c_s')
                else:
                    self._go_to_state(message, 'auth_state')
            else:
                if user.password_three_wrong:
                    if user.block_password_time + datetime.timedelta(seconds=900) > datetime.datetime.utcnow():
                        text = self.locale_text(user_lang, 'too_many_wrong_password_msg')
                        self.delete_msgs(self._bot, user)
                        msg = self._bot.send_message(user.user_id, text,
                                                     reply_markup=types.ReplyKeyboardRemove())
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                        self._go_to_state(message, 'auth_state', no_del=True)
                        thread = threading.Thread(target=self.user_unlock, name='user_unlock', args=([user]))
                        thread.start()
                else:
                    if reg_user.password == message.text:
                        user.auth_password = message.text
                        user.save()
                        self.delete_msgs(self._bot, user)

                        self._go_to_state(message, 'login_finale_state')
                    else:
                        self.delete_msgs(self._bot, user)

                        msg = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'wrong_password_msg'))
                        user.msgs_to_del.append(msg.message_id)

                        user.password_tries_counter += 1
                        user.save()
                        if user.password_tries_counter >= 3:
                            user.password_three_wrong = True
                            user.password_tries_counter = 0
                            user.block_password_time = datetime.datetime.utcnow()
                            user.save()
                            text = self.locale_text(user_lang, 'three_times_wrong_password_msg')
                            msg = self._bot.send_message(
                                message.chat.id,
                                text,
                                parse_mode='markdown',
                            )
                            user.msgs_to_del.append(msg.message_id)
                            user.save()
                            self._go_to_state(message, 'auth_state', no_del=True)
                        else:
                            # try:
                            #     self._bot.delete_message(user.user_id, user.msg_to_delete)
                            # except Exception as e:
                            #     print(e)
                            self._go_to_state(message, 'log_password_state', no_del=True)

    def login_finale_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user or not reg_user.login or not user.auth_login:
            if user.change_address:
                user.change_address = False
                user.save()
                self._go_to_state(message, 'enter_adres_state')
            elif user.change_phone:
                user.change_phone = False
                user.save()
                self._go_to_state(message, 'enter_phone_state')
            else:
                pass

        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        # gmt = self.Zone(3, False, 'GMT')
        # reg_user.enter_history[str(user.user_id)] = datetime.datetime.now(gmt)
        self.delete_msgs(self._bot, user)

        if reg_user and reg_user.password == user.auth_password and reg_user.password and reg_user.login:
            # if reg_user.is_main_structure:
            user.is_authed = True
            user.save()
            if user.change_address:
                user.change_address = False
                user.save()
                self._go_to_state(message, 'enter_adres_state')
            elif user.change_phone:
                user.change_phone = False
                user.save()
                self._go_to_state(message, 'enter_phone_state')
            else:
                reg_user.is_registered = True
                reg_user.save()
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                text = self.locale_text(user_lang, 'ur_cabinet').format(config.CABINET_LINK)
                msg_to_del = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                user.msgs_to_del.append(msg_to_del.message_id)
                user.state = 'cabinet_state'
                user.save()
                # self._go_to_state(message, 'cabinet_state')
            # else:
            #     try:
            #         self._bot.delete_message(user.user_id, user.msg_to_delete)
            #     except Exception as e:
            #         print(e)
            #     self._go_to_state(message, 'main_menu_state')

    def buy_place_in_structure_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()

        if entry:
            if reg_user.is_main_structure:
                self._go_to_state(message, 'main_menu_state')
            else:
                text = self.locale_text(user_lang, 'buy_place_in_structure_msg')
                msg = self._bot.send_message(user.user_id, text,
                                             reply_markup=keyboards.buy_place_in_structure_keyboard(user_lang))
                user.msg_to_delete = msg.message_id
                user.save()
        else:
            if message.text == self.locale_text(user_lang, 'buy_place_in_structure_btn'):
                if not reg_user.is_main_structure:
                    referrals_indent.referrals_indent(user, reg_user)
                    self.create_default_fields(reg_user, self.locale_text)
                    core: Core = Core.objects.first()
                    reg_user.number_to_distribute = core.subscribe_price
                    reg_user.save()
                    text = self.locale_text(user_lang, 'buy_info_msg')
                    self.distribute_percents(reg_user, self._bot, text=text)
                    reg_user.is_main_structure = True
                    # reg_user.is_registered = True
                    reg_user.save()
                    self._go_to_state(message, 'main_menu_state')
                else:
                    self._go_to_state(message, 'main_menu_state')

            elif message.text == self.locale_text(user_lang, 'cancel_msg'):
                user.is_authed = False
                user.save()
                self._go_to_state(message, 'auth_state')

    def main_menu_state(self, message, entry=False, call: types.CallbackQuery = None, is_del: bool = True):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
            if not reg_user:
                reg_user = UserRegister()
                reg_user.is_registered = False
                reg_user.save()
                user.defaul_unregister_user = reg_user
                user.save()
            reg_user.is_registered = False
            reg_user.save()

        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        core: Core = Core.objects.first()

        if user.shared_product_id:
            if len(user.shared_product_id) != 0:
                good = Product.objects(id=user.shared_product_id).first()
                if good:
                    user.is_in_shop = True
                    user.target_good = good
                    user.shared_product_id = str()
                    user.save()
                    if reg_user:
                        reg_user.structure_referrals = user.structure_referrals
                        reg_user.save()
                    self._go_to_state(message, 'shop_state')
                    return None
                else:
                    user.shared_product_id = str()
                    user.save()

        if entry:
            user.from_cabinet = False
            user.password_tries_counter = 0
            user.password_three_wrong = False
            user.save()

            if is_del:
                self.delete_msgs(self._bot, user)
            else:
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

            user.msg_to_delete = None
            user.msgs_to_del = list()
            user.save()
            if user.username is not None and user.username != 'None':
                text = self.locale_text(user.user_lang, 'hi_msg').format(user.username, core.shop_name_text)
                msg_to_del = self._bot.send_message(user.user_id, text,
                                                    reply_markup=keyboards.main_menu_keyboard(user.user_lang))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

            elif user.first_name is not None and user.first_name != 'None':
                text = self.locale_text(user.user_lang, 'hi_msg').format(user.first_name, core.shop_name_text)
                msg_to_del = self._bot.send_message(user.user_id, text,
                                                    reply_markup=keyboards.main_menu_keyboard(user.user_lang))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

            elif user.last_name is not None and user.last_name != 'None':
                text = self.locale_text(user.user_lang, 'hi_msg').format(user.last_name, core.shop_name_text)
                msg_to_del = self._bot.send_message(user.user_id, text,
                                                    reply_markup=keyboards.main_menu_keyboard(user.user_lang))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

        else:

            if message.text == self.locale_text(user.user_lang, 'user_cabinet'):
                self._go_to_state(message, 'cabinet_state')

            elif message.text == self.locale_text(user.user_lang, 'company'):
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                self._go_to_state(message, 'company_state')

            elif message.text == self.locale_text(user.user_lang, 'contacts'):
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                self._go_to_state(message, 'contacts_state')

            elif message.text == self.locale_text(user_lang, 'market'):
                user.is_in_shop = True
                user.save()
                self._go_to_state(message, 'new_shop_state')

    def new_shop_state(self, message, entry=False, call: types.CallbackQuery = None, stay_here: bool = False):
        core: Core = Core.objects.first()
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        categories = Category.objects(is_moderated=True)
        products = Product.objects(is_active=True)

        if entry:
            if user.from_cabinet:
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                   self.delete_msgs)
            else:
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user,
                                   self.delete_msgs)

            text = self.locale_text(user_lang, 'new_shop_enter_msg').format(core.shop_name_text)
            msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.new_shop_keyboard(user_lang))
            user.msgs_to_del.append(msg.message_id)
            if not stay_here:
                if user.from_cabinet:
                    user.state = 'cabinet_state'
                    user.save()
                else:
                    user.state = 'main_menu_state'
                    user.save()
            user.save()
        else:

            if call:

                if call.data == 'new_shop_state_inline_button_1_option':
                    if user.from_cabinet:
                        self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user),
                                           user, self.delete_msgs)
                    else:
                        self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user,
                                           self.delete_msgs)
                    user.target_good = None
                    user.category = None
                    user.is_in_shop = True
                    user.choosed_category = None
                    user.save()
                    self._go_to_state(message, '_category_state')

                elif call.data == 'new_shop_state_inline_button_day_product':  # product of the day
                    good: Product = Product.objects(is_day_good=True).first()
                    if good:
                        if user.from_cabinet:
                            self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user),
                                               user, self.delete_msgs)
                        else:
                            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user,
                                               self.delete_msgs)
                        user.target_good = good
                        user.category = None
                        user.is_in_shop = True
                        user.choosed_category = None
                        user.save()
                        self._go_to_state(message, 'shop_state')
                    else:
                        text = self.locale_text(user_lang, 'no_good_day_msg')
                        self._bot.answer_callback_query(call.id, text=text)


                # basket
                elif call.data == 'new_shop_state_inline_button_2_option':
                    if len(user.cart) != 0:
                        self._bot.delete_message(user.user_id, call.message.message_id)
                        self._go_to_state(message, 'v_a_c_s')
                    else:
                        self._bot.answer_callback_query(call.id, self.locale_text(user_lang, 'empty_cart_msg'))

                elif call.data == 'new_shop_state_inline_button_3_option':
                    text = self.locale_text(user_lang, 'search_msg')
                    keyboard = keyboards.single_back_keyboard(user_lang)
                    msg_to_del = self._bot.send_message(user.user_id, text, reply_markup=keyboard, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)

                    user.state = 'new_shop_state'
                    user.save()

                elif call.data == 'new_shop_state_inline_button_4_option':
                    # self.delete_msgs(self._bot, user)
                    self._bot.delete_message(user.user_id, call.message.message_id)
                    if user.from_cabinet:
                        self._go_to_state(message, 'cabinet_state')
                    else:
                        self._go_to_state(message, 'main_menu_state', is_del=False)
            elif message.text == self.locale_text(user_lang, 'back_btn'):
                print(123)

                self._go_to_state(message, 'new_shop_state')
            else:
                print(123)

                # if user.is_search:
                found_categories = self.search_in_categories(message.text, categories)
                found_products = self.search_in_products(message.text, products)

                if found_products or found_categories:
                    print(123)

                    result = {'categories': found_categories,
                              'goods': found_products}

                    self._go_to_state(message, '_category_state', search=result)
                else:
                    msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'nothing_found_msg'))
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

    def advert_finale(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        photo: Photo = Photo.objects(user=reg_user).first()

        structure = Product()
        structure.category = user.choosed_category
        structure.creator = reg_user
        structure.images = photo.paths
        structure.save()

        photo.paths = None
        photo.save()

        fields = Field.objects(user=reg_user)
        for field in fields:
            structure.fields[field.field_tag] = field.value
            structure.save()
            field.value = None
            field.save()
        self._go_to_state(message, 'cabinet_state')

    def cabinet_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user

        print('reg_user.is_registered: {}'.format(reg_user.is_registered))
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        user_lang = user.user_lang
        core: Core = Core.objects.first()

        if entry:

            user.from_cabinet = True
            user.save()
            if not reg_user.is_main_structure:
                text_2 = self.locale_text(user_lang, 'activate_description')
            else:
                text_2 = self.locale_text(user_lang, 'cabinet_msg')

            msg = self._bot.send_message(user.user_id, text_2, reply_markup=keyboards.cabinet_keyboard(user_lang,
                                                                                                       user))
            self.delete_msgs(self._bot, user)

            user.msgs_to_del.append(msg.message_id)
            user.save()

            if reg_user.is_main_structure:
                msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user.user_lang, 'referal_links_msg'),
                                                    reply_markup=keyboards.referrals_menu(user))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

        else:
            if message.text == self.locale_text(user_lang, 'info_btn'):
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                text = self.locale_text(user_lang, 'info_msg')
                keyboard = keyboards.cabinet_info_keyboard(user_lang)
                msg_to_del = self._bot.send_message(user.user_id, text, reply_markup=keyboard, parse_mode='markdown')

                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

            elif message.text == self.locale_text(user_lang, 'invite_friend_btn'):
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                text = self.locale_text(user.user_lang, 'ref_link_template').format(core.shop_name_text,
                                                                                    (str(reg_user.id)))
                text_2 = self.locale_text(user_lang, 'invite_friend_first_msg')

                msg_to_del = self._bot.send_message(user.user_id, text_2)
                msg_to_del_1 = self._bot.send_message(user.user_id, text.format(str(reg_user.id)),
                                                      parse_mode='markdown')
                user.msgs_to_del.append(msg_to_del_1.message_id)
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

            elif message.text == self.locale_text(user_lang, 'web_cabinet_btn'):
                if not reg_user.is_registered:
                    self._go_to_state(message, 'auth_state')

                else:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    text = self.locale_text(user_lang, 'ur_cabinet').format(config.CABINET_LINK)
                    msg_to_del = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                    # self._go_to_state(message, 'cabinet_state')

            elif message.text == self.locale_text(user_lang, 'activate_btn'):
                if not reg_user.is_registered:
                    self._go_to_state(message, 'auth_state')

                else:
                    referrals_indent.referrals_indent(user, reg_user)
                    reg_user.is_main_structure = True
                    reg_user.save()
                    # self.create_default_fields(reg_user, self.locale_text)
                    #   todo balance check
                    data = reg_user.univers_distribute_general_pack(core.subscribe_price + reg_user.frozen_distribute_sum)
                    for par in data:
                        parent = UserRegister.objects(id=par).first()
                        tgs = User.objects(auth_login=parent.login)
                        for tg in tgs:
                            msg_to_del = self._bot.send_message(tg.user_id,
                                                              Text.objects(tag='destributed_cash').first().\
                                                                values.get(tg.user_lang).\
                                                                format(parent.login, data[par]))
                            tg.msgs_to_del.append(msg_to_del.message_id)
                            tg.save()
                    self._go_to_state(message, 'cabinet_state')

            elif message.text == self.locale_text(user_lang, 'add_good'):

                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                self.delete_msgs(self._bot, user)
                if not reg_user.is_registered:
                    text = self.locale_text(user_lang, 'activate_description')
                    msg = self._bot.send_message(user.user_id, text,
                                                 reply_markup=keyboards.buy_place_in_structure_keyboard(user_lang))
                    user.msgs_to_del.append(msg.message_id)
                    user.save()
                else:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    user.category = None
                    user.choosed_category = None
                    user.target_good = None
                    user.is_in_shop = False
                    user.fields_without_value = Field.objects(Q(user=reg_user)
                                                              & Q(in_active=True) &
                                                              Q(is_moderated=True)).order_by('priority')
                    user.save()

                    text = self.locale_text(user_lang, 'add_good_choose_way_msg')
                    msg_to_del = self._bot.send_message(user.user_id, text,
                                                        reply_markup=keyboards.add_good_choose_way_keyboard(user_lang),
                                                        parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

            elif message.text == self.locale_text(user_lang, 'settings'):
                self._go_to_state(message, 'settings_state')

            elif message.text == self.locale_text(user_lang, 'basket_btn'):
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                user.from_cabinet = True
                user.save()
                self._go_to_state(message, 'v_a_c_s')

            elif message.text == self.locale_text(user_lang, 'back_btn'):
                user.from_cabinet = False
                user.save()
                self._go_to_state(message, 'main_menu_state')

            elif message.text == self.locale_text(user_lang, 'log_out_btn'):
                self.delete_msgs(self._bot, user)

                user.auth_login = ''
                user.auth_password = ''
                user.is_authed = False
                user.from_cabinet = False
                user.save()
                text = self.locale_text(user_lang, 'logout_msg')
                msg_to_del = self._bot.send_message(user.user_id, text, reply_markup=keyboards.remove_reply_keyboard())
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()
                reg_user.is_registered = False
                reg_user.save()
                self._go_to_state(message, 'main_menu_state')
                # self._go_to_state(message, 'auth_state')

            if call:
                if call.data == 'cabinet_state_inline_button_1_option':  # entry referal link
                    text = self.locale_text(user.user_lang, 'ref_link_template').format(core.shop_name_text,
                                                                                        (str(reg_user.id)))
                    msg_to_del = self._bot.send_message(user.user_id,
                                                        text.format(str(reg_user.id)), parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

                elif call.data == 'cabinet_state_inline_button_2_option':  # activate cabinet from side options
                    if not reg_user.is_main_structure:

                        self._go_to_state(message, 'auth_state')
                    else:
                        referrals_indent.referrals_indent(user, reg_user)
                        reg_user.is_main_structure = True
                        reg_user.save()
                        # self.create_default_fields(reg_user, self.locale_text)
                        #   todo balance check
                        data = reg_user.univers_distribute_general_pack(core.subscribe_price + reg_user.frozen_distribute_sum)
                        for par in data:
                            parent = UserRegister.objects(id=par).first()
                            tgs = User.objects(auth_login=parent.login)
                            for tg in tgs:
                                msg_to_del = self._bot.send_message(tg.user_id,
                                                                    Text.objects(tag='destributed_cash').first(). \
                                                                    values.get(tg.user_lang). \
                                                                    format(parent.login, data[par]))
                                tg.msgs_to_del.append(msg_to_del.message_id)
                                tg.save()
                        self._go_to_state(message, 'cabinet_state')

                elif call.data == 'cabinet_state_inline_button_3_option':  # cancel activation
                    self._go_to_state(message, 'cabinet_state')

                elif call.data == 'cabinet_state_inline_button_4_option':  # go to shop from buy history
                    user.is_in_shop = True
                    user.from_cabinet = True
                    user.target_good = None
                    user.category = None
                    user.choosed_category = None
                    user.save()
                    self._go_to_state(message, '_category_state')

                elif call.data == 'cabinet_state_inline_button_5_option':  # go to product of the day from buy history
                    good: Product = Product.objects(is_day_good=True).first()
                    if good:
                        user.is_in_shop = True
                        user.from_cabinet = True
                        user.target_good = good
                        user.save()
                        self._go_to_state(message, 'shop_state')
                    else:
                        text = self.locale_text(user_lang, 'no_good_day_msg')
                        self._bot.answer_callback_query(call.id, text=text)

                elif call.data == 'cabinet_state_inline_button_6_option':  # from info to structure data
                    # self.delete_msgs(self._bot, user)
                    if not reg_user.is_main_structure:
                        text = self.locale_text(user_lang, 'activate_description')
                        self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                                    reply_markup=keyboards.buy_place_in_structure_keyboard(user_lang))
                        # user.msgs_to_del.append(msg.message_id)
                        # user.save()
                    else:
                        # self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                        #                    self.delete_msgs)
                        max_deep = referrals_indent.get_max_deep(reg_user.positional_id, reg_user.level)   # max_deep = self.get_max_deep(reg_user)
                        # self.format_line_information()
                        pages_count = math.ceil((max_deep/5))
                        text = self.structure_info_format_format(user, reg_user, user_lang, self.locale_text, self._bot)

                        self._bot.edit_message_text(text, user.user_id, call.message.message_id, parse_mode='markdown',
                                                    reply_markup=keyboards.structure_keyboard(max_deep, user_lang,
                                                                                              pages_count=pages_count))
                        # user.msgs_to_del.append(msg_to_del.message_id)
                        # user.save()

                elif call.data == 'cabinet_state_inline_button_7_option':  # show balance
                    # self.delete_msgs(self._bot, user)
                    # self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    text = self.balance_format(user, reg_user, user_lang, self.locale_text, self._bot)
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id, parse_mode='markdown')

                    # user.msgs_to_del.append(msg_to_del.message_id)
                    # user.save()

                elif call.data == 'cabinet_state_inline_button_8_option':  # TODO MY WALLETS
                    self._bot.delete_message(user.user_id, call.message.message_id)
                    self._go_to_state(message, 'choose_wallets_state')


                elif call.data == 'cabinet_state_inline_button_9_option':  # purchase history
                    self._go_to_state(message, '_buy_history_state')

                elif call.data == 'cabinet_state_inline_button_10_option':  # my goods
                    # self.delete_msgs(self._bot, user)
                    if not reg_user.is_main_structure:
                        text = self.locale_text(user_lang, 'activate_description')
                        self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                                    reply_markup=keyboards.buy_place_in_structure_keyboard(user_lang))
                        # user.msgs_to_del.append(msg.message_id)
                        # user.save()
                    else:
                        # self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                        #                    self.delete_msgs)
                        self._go_to_state(message, 'my_goods_state')

                elif call.data == 'cabinet_state_inline_button_11_option':  # get lorem ipsum text
                    msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'terms_msg'))
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

                elif call.data == 'cabinet_state_inline_button_12_option':  # add good from tg
                    user.category = None
                    user.choosed_category = None
                    user.target_good = None
                    user.is_in_shop = False
                    user.current_field = None
                    user.entered_fields = list()
                    user.fields_without_value = Field.objects(Q(user=reg_user)
                                                              & Q(in_active=True) &
                                                              Q(is_moderated=True)).order_by('priority')
                    user.save()
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                       delete_msgs=self.delete_msgs)

                    self._go_to_state(message, '_category_state')
                elif call.data == 'cabinet_state_inline_button_13_option':  # add good from cabinet
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    text = self.locale_text(user_lang, 'ur_cabinet').format(config.CABINET_LINK_ADD_GGOD)
                    msg_to_del = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                elif call.data.find('cabinet_state_inline_button_goto_') != -1:
                    page = int(call.data[len('cabinet_state_inline_button_goto_'):])
                    max_deep = referrals_indent.get_max_deep(reg_user.positional_id,
                                                             reg_user.level)
                    pages_count = math.ceil(max_deep/5)
                    text = self.structure_info_format_format(user, reg_user, user_lang, self.locale_text, self._bot)

                    self._bot.edit_message_text(text, user.user_id, call.message.message_id, parse_mode='markdown',
                                                reply_markup=keyboards.structure_keyboard(max_deep, user_lang,
                                                                                          current_page=page,
                                                                                          pages_count=pages_count))

                elif call.data.find('cabinet_state_inline_button_my_line_') != -1:

                    line, page = call.data[len('cabinet_state_inline_button_my_line_'):].split('_')
                    line = int(line)
                    page = int(page)
                    print(line)
                    print(page)
                    text = '*' + self.locale_text(user.user_lang, 'my_line').format(line) + '*' + '\n\n\n'

                    time_1 = datetime.datetime.now()

                    if reg_user.level == 1:
                        res = UserRegister.objects(level=line+reg_user.level).order_by('positional_id')
                    else:
                        left_pos = reg_user.positional_id * 2 ** line
                        right_pos = reg_user.positional_id * 2 ** line + 2 ** line - 1
                        print(left_pos)
                        print(right_pos)
                        res = UserRegister.objects(Q(level=line + reg_user.level) &
                                                   Q(positional_id__lte=right_pos) &
                                                   Q(positional_id__gte=left_pos)).order_by('positional_id')

                    time_2 = datetime.datetime.now()
                    print('1_timedelta seconds = {0} microseconds = {1}'.format((time_2 - time_1).seconds,
                                                                                (time_2 - time_1).microseconds))
                    # res = list(res)

                    # l_index = referrals_indent.get_verge_index(res, left_pos, len(res))
                    # r_index = referrals_indent.get_verge_index(res, right_pos, len(res))

                    # time_3 = datetime.datetime.now()
                    # print('2_timedelta seconds = {0} microseconds = {1}'.format((time_3 - time_2).seconds,
                    #                                                             (time_3 - time_2).microseconds))
                    # res = res[l_index:r_index]
                    time_11 = datetime.datetime.now()

                    max_pages_count = math.ceil(res.count()/32)
                    time_12 = datetime.datetime.now()

                    print('2_timedelta seconds = {0} microseconds = {1}'.format((time_12 - time_11).seconds,
                                                                                (time_12 - time_11).microseconds))

                    keyboard = keyboards.line_pages_keyboard(user_lang, page, line, max_pages_count)
                    time_13 = datetime.datetime.now()

                    print('2_timedelta seconds = {0} microseconds = {1}'.format((time_13 - time_12).seconds,
                                                                                (time_13 - time_12).microseconds))

                    counter = 0
                    time_4 = datetime.datetime.now()
                    print('3_timedelta seconds = {0} microseconds = {1}'.format((time_4 - time_2).seconds,
                                                                                (time_4 - time_2).microseconds))

                    for reg_referral in res[(page-1)*32: page*32]:
                        txt = str()
                        if reg_referral:
                            l_users_tgs = User.objects(auth_login=reg_referral.login)
                            if l_users_tgs:
                                for tg in l_users_tgs:
                                    if tg.username and not tg.username == 'None':
                                        link = 't.me/{0}'.format(str(tg.username).replace('_', '\_'))
                                        txt += link if len(txt) == 0 else ', {0}'.format(link)
                                    else:
                                        link = self.locale_text(user_lang, 'link_msg').format(tg.user_id)
                                        txt += link if len(txt) == 0 else ', {0}'.format(link)

                            txt = self.locale_text(user_lang, 'format_line_user').format(reg_referral.positional_id,
                                                                                         txt) + '\n'
                            text += txt
                            if len(text) >= 3000 and counter != res.count():
                                try:
                                    self._bot.delete_message(user.user_id, call.message.message_id)
                                except Exception as e:
                                    print(e)
                                msg = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                                user.msgs_to_del.append(msg.message_id)
                                user.save()
                                text = str()
                            counter += 1

                    time_5 = datetime.datetime.now()

                    print('4_timedelta seconds = {0} microseconds = {1}'.format((time_5 - time_4).seconds,
                                                                                   (time_5 - time_4).microseconds))
                    print('full_timedelta seconds = {0} microseconds = {1}'.format((time_5 - time_1).seconds,
                          (time_5 - time_1).microseconds))


                    try:
                        self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                                    reply_markup=keyboard, parse_mode='markdown')
                    except Exception as e:
                        msg = self._bot.send_message(user.user_id, text, reply_markup=keyboard, parse_mode='markdown')
                        user.msgs_to_del.append(msg.message_id)
                        user.save()

                elif call.data.find('cabinet_state_inline_button_back_my_line_') != -1:
                    self._bot.delete_message(user.user_id, call.message.message_id)
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

    def choose_wallets_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        user_lang = user.user_lang
        core: Core = Core.objects.first()

        if entry:
            text = self.locale_text(user_lang, 'choose_wallet_to_bind')
            msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.wallets_keyboard(user))
            user.msgs_to_del.append(msg.message_id)
            user.state = 'cabinet_state'
            user.save()
        else:
            if call.data.find('choose_wallets_state_inline_button_') != -1:
                tag = call.data[len('choose_wallets_state_inline_button_'):-4]
                print(tag)
                currency = Currency.objects(tag=tag).first()
                self._bot.delete_message(user.user_id, call.message.message_id)
                try:
                    res = reg_user.wallets.get(currency.tag)
                except Exception as e:
                    res = None
                    print(e)
                reg_user.choose_wallet = currency.tag
                reg_user.save()
                if res:
                    self._go_to_state(message, 'apply_to_del_state')
                else:
                    self._go_to_state(message, 'enter_wallet_state')

    def apply_to_del_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        user_lang = user.user_lang
        currency = Currency.objects(tag=reg_user.choose_wallet).first()
        # self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
        if entry:
            text = self.locale_text(user_lang, 'confirm_del_wallet') \
                .format(currency.values.get(user_lang), currency.values.get(user_lang),
                        user.wallets.get(user.choose_wallet))

            msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.apply_to_del_keyboard(user_lang))
            user.msgs_to_del.append(msg.message_id)
            user.state = 'cabinet_state'
            user.save()
        else:
            if call.data == 'apply_to_del_state_inline_button_apply':
                self._bot.delete_message(user.user_id, call.message.message_id)
                reg_user.wallets.pop(reg_user.choose_wallet)
                reg_user.save()
                self._bot.answer_callback_query(call.id, self.locale_text(user_lang, 'wallet_deleted_msg'))
                user.state = 'cabinet_state'
                user.save()
            elif call.data == 'apply_to_del_state_inline_button_cancel':
                self._bot.delete_message(user.user_id, call.message.message_id)
                self._bot.answer_callback_query(call.id, self.locale_text(user_lang, 'wallet_not_deleted_msg'))
                user.state = 'cabinet_state'
                user.save()

    def enter_wallet_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        user_lang = user.user_lang
        currency = Currency.objects(tag=reg_user.choose_wallet).first()

        if entry:
            if not reg_user.wallets.get(currency.tag):
                text = self.locale_text(user_lang, 'wallet_request_msg').format(currency.values.get(user_lang))
                msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.back_keyboard(user_lang))
            else:
                text = self.locale_text(user_lang, 'your_wallet_msg').format(user.wallets.get(currency.tag))
                msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.apply_rewrite_keyboard(user_lang))

            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'back_btn'):
                if not reg_user.is_main_structure:
                    text_2 = self.locale_text(user_lang, 'activate_description')
                else:
                    text_2 = self.locale_text(user_lang, 'cabinet_msg')

                msg = self._bot.send_message(user.user_id, text_2,
                                       reply_markup=keyboards.cabinet_keyboard(user_lang, user))
                user.msgs_to_del.append(msg.message_id)
                user.state = 'cabinet_state'
                user.save()
            else:
                if not reg_user.is_main_structure:
                    text_2 = self.locale_text(user_lang, 'activate_description')
                else:
                    text_2 = self.locale_text(user_lang, 'cabinet_msg')
                msg = self._bot.send_message(user.user_id, text_2,
                                       reply_markup=keyboards.cabinet_keyboard(user_lang, user))
                reg_user.wallets[reg_user.choose_wallet] = message.text
                reg_user.save()
                user.msgs_to_del.append(msg.message_id)
                user.state = 'cabinet_state'
                user.save()
            if call.data == 'enter_wallet_state_inline_button_apply':
                self._bot.delete_message(user.user_id, call.message.message_id)
                reg_user.wallets.pop(reg_user.choose_wallet)
                reg_user.save()
                self._go_to_state(message, 'enter_wallet_state')
            elif call.data == 'enter_wallet_state_inline_button_cancel':
                self._bot.delete_message(user.user_id, call.message.message_id)
                self._go_to_state(message, 'choose_wallets_state')

    def _buy_history_state(self, message, entry=False, call: types.CallbackQuery = None, current_good: int = 1):
        core: Core = Core.objects.first()
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)
        share_template: str = ''

        good_history = ProductHistory.objects(user=reg_user)
        msx_pages_count = len(good_history)
        if not good_history:
            # self.delete_msgs(self._bot, user)
            self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

            text = self.locale_text(user.user_lang, 'not_good_history_msg')
            keyboard = keyboards.no_buy_history_keyboard(user_lang)
            msg_to_del = self._bot.send_message(user.user_id, text, reply_markup=keyboard, parse_mode='markdown')
            user.msgs_to_del.append(msg_to_del.message_id)
            user.state = 'cabinet_state'
            user.save()
            return None

        if entry:
            # self.delete_msgs(self._bot, user)
            self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

            good = good_history[current_good-1].good
            images: list = list()

            if good.images:
                for image in good.images:
                    src = '{0}/src/web_admin_panel/static/{1}'.format(os.getcwd(), image)
                    file = open(src, 'rb')
                    images.append(types.InputMediaPhoto(file))

            text: str = str()

            fields: dict = good.fields
            order = Order.objects(Q(user=reg_user) & Q(good=good)).first()
            print(order.date)
            print(order.counter)

            name = fields.get('name')
            description = fields.get('description')
            price = fields.get('price')
            distributed_price = fields.get('reward')

            target_field = Field.objects(Q(user=reg_user) & Q(field_tag='name')).first()
            # text += '*' + target_field.names.get(user.user_lang) + ': *'
            # text += '{0}\n\n'.format(name)
            # target_field = Field.objects(Q(user=reg_user) & Q(field_tag='description')).first()
            # text += '*' + target_field.names.get(user.user_lang) + ': *'
            # text += '{0}\n'.format(description)

            # i = 2
            text += '*' + self.locale_text(user_lang, 'name') + ': *' + name + '\n'
            text += '*' + self.locale_text(user_lang, 'amount') + ' *' + str(order.counter) + '\n'

            for field in fields:
                # i += 1
                target_field = Field.objects(Q(user=reg_user) & Q(field_tag=field)).first()
                if target_field and target_field.priority !=4 and target_field.priority !=5 \
                        and target_field.priority != 2:
                    text += '*' + target_field.names.get(user.user_lang) + ': *'
                    text += '{0}\n'.format(fields[field])

            text_2 = self.locale_text(user_lang, 'format_date'). \
                format(good_history[current_good-1].date.strftime("%Y-%m-%d, %H:%M:%S")) + '\n'

            text_2 += self.locale_text(user.user_lang, 'price_part_msg').format(str(round(order.sum, 2)))

            if good.images:
                try:
                    msg = self._bot.send_media_group(user.user_id, media=images)
                    for m in msg:
                        user.msgs_to_del.append(m.message_id)
                        user.save()
                    # user.msg_to_delete = msg[-1].message_id
                    # msg = self._bot.edit_message_media(chat_id=user.user_id, media=images,
                    #                                    message_id=user.media_msg_to_edit, parse_mode='markdown')
                    print('try 1')
                    self._bot.edit_message_caption(chat_id=user.user_id, caption=text,
                                                   message_id=msg[-1].message_id, parse_mode='markdown')
                    print('try 2')

                except Exception as e:
                    print('except')
                    msg = self._bot.send_media_group(user.user_id, media=images)
                    for m in msg:
                        user.msgs_to_del.append(m.message_id)
                        user.save()
                    user.media_msg_to_edit = msg[-1].message_id
                    user.save()
                    self._bot.edit_message_caption(chat_id=user.user_id, caption=text,
                                                   message_id=msg[-1].message_id, parse_mode='markdown')
            else:
                msg = self._bot.send_message(chat_id=user.user_id, text=text,
                                             parse_mode='markdown')
                user.msgs_to_del.append(msg.message_id)
                user.save()

            msg_to_del = self._bot.send_message(user.user_id, text_2, parse_mode='markdown',
                                                reply_markup=keyboards._buy_history_keyboard(user.user_lang, good,
                                                                                             current_page=current_good,
                                                                                             max_pages_count=msx_pages_count))
            user.msgs_to_del.append(msg_to_del.message_id)
            user.state = 'cabinet_state'
            user.save()
        else:
            if call:
                if call.data.find('_buy_history_state_inline_button_1_') != -1:
                    index = call.data.find('_buy_history_state_inline_button_1_')
                    current_page_index, max_pages_count = \
                        [int(x) for x in call.data[index + len('_buy_history_state_inline_button_1_'):].split('_')]

                    next_page_index: int = current_page_index - 1 if current_page_index != 1 else max_pages_count

                    # if user.media_msgs_to_del:
                    #     for msg_id in user.media_msgs_to_del:
                    #         self._bot.delete_message(user.user_id, msg_id)

                    user.media_msgs_to_del = list()
                    user.save()

                    self._bot.delete_message(user.user_id, call.message.message_id)

                    self._go_to_state(
                        message, '_buy_history_state', call=call,
                        current_good=next_page_index
                    )

                elif call.data.find('_buy_history_state_inline_button_2') != -1:
                    # if user.media_msgs_to_del:
                    #     for msg_id in user.media_msgs_to_del:
                    #         self._bot.delete_message(user.user_id, msg_id)

                    user.media_msgs_to_del = list()
                    user.save()
                    # self.delete_msgs(self._bot, user)
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

                    try:
                        self._bot.delete_message(chat_id=message.chat.id, message_id=call.message.message_id)
                    except Exception as e:
                        print(e)
                    user.state = 'cabinet_state'
                    user.save()

                elif call.data.find('_buy_history_state_inline_button_3_') != -1:

                    index = call.data.find('_buy_history_state_inline_button_3_')
                    current_page_index, max_pages_count = \
                        [int(x) for x in call.data[index + len('_buy_history_state_inline_button_3_'):].split('_')]

                    next_page_index: int = current_page_index + 1 if current_page_index != max_pages_count else 1

                    user.media_msgs_to_del = list()
                    user.save()

                    self._bot.delete_message(user.user_id, call.message.message_id)

                    self._go_to_state(
                        message, '_buy_history_state', call=call,
                        current_good=next_page_index)

                elif call.data.find('_buy_history_state_inline_button_repeat') != -1:
                    good_id = call.data[len('_buy_history_state_inline_button_repeat_'):]
                    good: Product = Product.objects(id=good_id).first()
                    user.target_good = good
                    user.from_cabinet = True
                    user.save()
                    self._go_to_state(message, 'shop_state')

                elif call.data.find('_buy_history_state_inline_button_share') != -1:
                    good_id = call.data[len('_buy_history_state_inline_button_share_'):]
                    good: Product = Product.objects(id=good_id).first()
                    fields: dict = good.fields

                    order = Order.objects(Q(user=reg_user) & Q(good=good)).first()

                    for field in fields:
                        target_field = Field.objects(Q(user=good.creator) & Q(field_tag=field)).first()
                        if target_field and field != 'reward':
                            if target_field.names.get(user.user_lang).find(':')!= -1:
                                share_template += '*' + target_field.names.get(user.user_lang).replace(':', '') + ': *'
                            else:
                                share_template += '*' + target_field.names.get(user.user_lang) + ': *'
                            share_template += '{0}\n'.format(fields[field])

                    text_amount = '*' + self.locale_text(user_lang, 'amount') + ' *' + str(order.counter) + '\n'

                    text_2 = self.locale_text(user.user_lang, 'price_part_msg').format(str(round(order.sum, 2)))

                    share_template += text_amount
                    share_template += text_2

                    share_template += u'\n[\u200B]({0})'.format('admin-setevik.botup.pp.ua/view/img/{0}'.format(
                        good.images[0]))

                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                       self.delete_msgs(self._bot, user))
                    user.state = 'cabinet_state'
                    user.save()

                    try: msg_to_del = self._bot.edit_message_text(self.locale_text(user_lang, 'first_share_msg'),
                                                                  user.user_id, call.message.message_id,
                                                                  parse_mode='markdown')
                    except: msg_to_del = self._bot.send_message(user.user_id,
                                                                self.locale_text(user_lang, 'first_share_msg'))
                    text = share_template + self.locale_text(user_lang, 'format_date') \
                        .format(good_history[current_good-1].date.strftime("%Y-%m-%d, %H:%M:%S")) + '\n' + \
                           self.locale_text(user_lang, 'ref_link_product_template').format(core.shop_name_text,
                                                                                           (str(reg_user.id)),
                                                                                           (str(good.id)))

                    msg_to_del_1 = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.msgs_to_del.append(msg_to_del_1.message_id)
                    user.save()

    def my_goods_state(self, message, entry=False, call: types.CallbackQuery = None, current_page: int = 1):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        goods: Product = Product.objects(Q(creator=reg_user) & Q(is_accepted=True))
        user_lang = user.user_lang
        core: Core = Core.objects().first()

        pages_count = math.ceil(
            len(goods) / float(core.category_row_num * core.category_col_num)
        )
        share_template: str = ''

        if entry:
            # self.delete_msgs(self._bot, user)
            self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

            text = self.locale_text(user_lang, 'your_goods_msg')
            if goods:
                msg_to_del = self._bot.send_message(user.user_id, text,
                                                    reply_markup=keyboards.my_goods_keyboard(
                                                        user_lang, goods,
                                                        current_page=current_page,
                                                        max_pages_count=pages_count,
                                                        col_num=core.category_col_num,
                                                        row_num=core.category_row_num))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.state = 'cabinet_state'
                user.save()

            else:
                text = self.locale_text(user_lang, 'no_goods_msg')
                msg_to_del = self._bot.send_message(user.user_id, text)
                user.msgs_to_del.append(msg_to_del.message_id)
                user.state = 'cabinet_state'
                user.save()
        else:
            if call:
                if call.data.find('my_goods_state_inline_button_1_') != -1:
                    index = call.data.find('my_goods_state_inline_button_1_')
                    current_page_index, max_pages_count = \
                        [int(x) for x in call.data[index + len('my_goods_state_inline_button_1_'):].split('_')]

                    next_page_index: int = current_page_index - 1 if current_page_index != 1 else max_pages_count

                    self._go_to_state(
                        message, 'my_goods_state', call=call,
                        current_page=next_page_index
                    )

                elif call.data.find('my_goods_state_inline_button_2') != -1:
                    self._bot.delete_message(chat_id=message.chat.id, message_id=call.message.message_id)
                    self._go_to_state(message, 'cabinet_state')

                elif call.data.find('my_goods_state_inline_button_3_') != -1:
                    index = call.data.find('my_goods_state_inline_button_3_')
                    current_page_index, max_pages_count = \
                        [int(x) for x in call.data[index + len('my_goods_state_inline_button_3_'):].split('_')]

                    next_page_index: int = current_page_index + 1 if current_page_index != max_pages_count else 1
                    self._go_to_state(
                        message, 'my_goods_state', call=call,
                        current_page=next_page_index)

                elif call.data.find('my_goods_state_inline_button_share') != -1:
                    good_id = call.data[len('my_goods_state_inline_button_share_'):]
                    good: Product = Product.objects(id=good_id).first()
                    fields: dict = good.fields

                    for field in fields:
                        target_field = Field.objects(Q(user=good.creator) & Q(field_tag=field)).first()
                        if target_field and field != 'reward':
                            share_template += '*' + target_field.names.get(user.user_lang).replace(':', '') + ': *'
                            share_template += '{0}\n'.format(fields[field])

                    share_template += u'\n[\u200B]({0})'.format('admin-setevik.botup.pp.ua/view/img/{0}'.format(
                        good.images[0]))

                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                       self.delete_msgs(self._bot, user))
                    user.state = 'cabinet_state'
                    user.save()

                    msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'first_share_msg'))
                    text = share_template + '\n' + self.locale_text(user_lang, 'ref_link_product_template'). \
                        format(core.shop_name_text, (str(reg_user.id)), (str(good.id)))
                    msg_to_del_1 = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.msgs_to_del.append(msg_to_del_1.message_id)
                    user.save()

                elif call.data.find('my_goods_state_inline_button_') != -1:
                    # self.delete_msgs(self._bot, user)
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)

                    good_id = call.data[len('my_goods_state_inline_button_'):]
                    good: Product = Product.objects(id=good_id).first()

                    images: list = list()

                    if good.images:
                        for image in good.images:
                            src = '{0}/src/web_admin_panel/static/{1}'.format(os.getcwd(), image)
                            file = open(src, 'rb')
                            images.append(types.InputMediaPhoto(file))
                            # img_check = True

                    text: str = str()

                    fields: dict = good.fields

                    name = fields.get('name')
                    description = fields.get('description')
                    price = fields.get('price')
                    distributed_price = fields.get('reward')

                    target_field = Field.objects(Q(user=reg_user) & Q(field_tag='name')).first()
                    text += '*' + target_field.names.get(user.user_lang).replace(':', '') + ': *'
                    text += '{0}\n\n'.format(name)
                    target_field = Field.objects(Q(user=reg_user) & Q(field_tag='description')).first()
                    text += '*' + target_field.names.get(user.user_lang) + ': *'
                    text += '{0}\n'.format(description)

                    for field in fields:
                        target_field = Field.objects(Q(user=reg_user) & Q(field_tag=field)).first()
                        if target_field and target_field.priority > 3:
                            text += '*' + target_field.names.get(user.user_lang) + ': *'
                            text += '{0}\n'.format(fields[field])
                    # text += self.locale_text(user.user_lang, 'price_part_msg').format(float(price) + float(distributed_price))

                    if good.images:
                        msg = self._bot.send_media_group(user.user_id, media=images)
                        for ms in msg:
                            user.msgs_to_del.append(ms.message_id)
                            user.save()
                        self._bot.edit_message_caption(chat_id=user.user_id, caption=text,
                                                       message_id=msg[-1].message_id,
                                                       parse_mode='markdown')
                        msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'send_msg'),
                                                            reply_markup=keyboards.share_keyboard(user_lang, good),
                                                            parse_mode='markdown')
                        user.msgs_to_del.append(msg_to_del.message_id)
                        user.save()
                    else:
                        msg = self._bot.send_message(user.user_id, text=text,
                                                     keyboard=keyboards.share_keyboard(user_lang, good),
                                                     parse_mode='markdown')
                        user.msgs_to_del.append(msg.message_id)
                        user.save()

                    user.state = 'cabinet_state'
                    user.save()

    def shop_state(self, message, entry=False, call: types.CallbackQuery = None, current_page: int =1):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user = UserRegister.objects(login=user.auth_login).first()
        user_lang = user.user_lang
        goods: Product = Product.objects(Q(category=user.choosed_category) & Q(is_accepted=True))
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        core: Core = Core.objects().first()

        pages_count = math.ceil(
            len(goods) / float(core.category_row_num * core.category_col_num)
        )

        if entry:
            if user.from_cabinet:
                user.state = 'cabinet_state'
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                print('if entry cabinet keyboard saved')
                user.save()
            else:
                user.state = 'main_menu_state'
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                print('if entry menu keyboard saved')
                user.save()
            if user.target_good:
                good = user.target_good
                # if call:
                #     try:
                #         self.s(user.user_id, call.message.message_id)
                #     except Exception as e:
                #         print(e)

                images: list = list()

                if good.images:
                    for image in good.images:
                        src = '{0}/src/web_admin_panel/static/{1}'.format(os.getcwd(), image)
                        file = open(src, 'rb')
                        images.append(types.InputMediaPhoto(file))

                text: str = str()

                fields: dict = good.fields

                # name = fields.get('name')
                # description = fields.get('description')
                price = fields.get('price')
                #
                # target_field = Field.objects(Q(user=good.creator) & Q(field_tag='name')).first()
                # text += '*' + target_field.names.get(user.user_lang) + ': *'
                # text += '{0}\n\n'.format(name)
                # target_field = Field.objects(Q(user=good.creator) & Q(field_tag='description')).first()
                # text += '*' + target_field.names.get(user.user_lang) + ': *'
                # text += '{0}\n'.format(description)

                for field in fields:
                    target_field = Field.objects(Q(user=good.creator) & Q(field_tag=field)).first()
                    if target_field and target_field.field_tag != 'reward':
                        text += '*' + target_field.names.get(user.user_lang).replace(':', '') + ': *'
                        text += '{0}\n'.format(fields[field])

                # price = self.locale_text(user_lang, 'price_part').format(float(price))

                if good.images:
                    msg = self._bot.send_media_group(user.user_id, media=images)
                    for ms in msg:
                        user.msgs_to_del.append(ms.message_id)
                        user.save()

                    self._bot.edit_message_caption(chat_id=user.user_id, caption=text,
                                                   message_id=msg[-1].message_id, parse_mode='markdown')
                else:
                    msg_to_del = self._bot.send_message(user.user_id, text,
                                                        parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

                msg_to_del = self._bot.send_message(user.user_id, price,
                                                    reply_markup=keyboards.buy_keyboard(user_lang, good, user),
                                                    parse_mode='markdown')
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()
                print('msgs_to_del.append(buy_keyboard)')
            else:
                # try:
                #     self._bot.delete_message(user.user_id, user.msg_to_delete)
                # except Exception as e:
                #     print(e)
                if user.from_cabinet:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    print('!user.target_good cabinet keyboard saved')
                else:
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    print('!user.target_good menu keyboard saved')

                text = self.locale_text(user_lang, 'your_goods_msg')
                if goods:
                    try:
                        self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                                    reply_markup=keyboards.shop_state_keyboard(
                                                        user_lang, goods,
                                                        current_page=current_page,
                                                        max_pages_count=pages_count,
                                                        col_num=core.category_col_num,
                                                        row_num=core.category_row_num))
                    except:
                        msg_to_del = self._bot.send_message(user.user_id, text,
                                                            reply_markup=keyboards.shop_state_keyboard(
                                                                user_lang, goods,
                                                                current_page=current_page,
                                                                max_pages_count=pages_count,
                                                                col_num=core.category_col_num,
                                                                row_num=core.category_row_num))
                        user.msgs_to_del.append(msg_to_del.message_id)
                        user.save()

                else:
                    text = self.locale_text(user_lang, 'no_goods_msg')
                    msg_to_del = self._bot.send_message(user.user_id, text)
                    user.choosed_category = None
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                    self._go_to_state(message, '_category_state', is_del=False)
        else:
            if call.data.find('shop_state_inline_button_to_cart_') != -1:
                # good_id = call.data[len('shop_state_inline_button_buy_'):]
                # good: Product = Product.objects(id=good_id).first()
                # self._bot.delete_message(user.user_id, call.message.message_id)
                # self.delete_msgs(self._bot, user)
                if user.from_cabinet:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    print('inline to cart cabinet keyboard saved')
                else:
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    print('inline to cart menu keyboard saved')

                user.target_good = None
                user.save()
                self._go_to_state(message, 'v_a_c_s')

            elif call.data.find('shop_state_inline_button_add_to_cart_') != -1:
                good_id = call.data[len('shop_state_inline_button_add_to_cart_'):]
                good: Product = Product.objects(id=good_id).first()
                # self._bot.delete_message(user.user_id, call.message.message_id)
                # self.delete_msgs(self._bot, user)
                # self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                text = self.locale_text(user_lang, 'add_good_answer').format(good.fields.get('name'))
                self._bot.answer_callback_query(call.id, text=text)

                user.cart.append(good)
                # user.target_good = None
                user.save()
                self._go_to_state(message, 'shop_state', call=call)

            elif call.data.find('shop_state_inline_button_back') != -1:
                if user.from_cabinet:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                else:
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

                user.target_good = None
                user.save()
                self._go_to_state(message, 'shop_state')

            elif call.data.find('shop_state_inline_button_1_') != -1:
                index = call.data.find('shop_state_inline_button_1_')
                current_page_index, max_pages_count = \
                    [int(x) for x in call.data[index + len('shop_state_inline_button_1_'):].split('_')]

                next_page_index: int = current_page_index - 1 if current_page_index != 1 else max_pages_count

                self._go_to_state(
                    message, 'shop_state', call=call,
                    current_page=next_page_index
                )

            elif call.data.find('shop_state_inline_button_2') != -1:
                self._bot.delete_message(chat_id=message.chat.id, message_id=call.message.message_id)
                if user.target_good:
                    user.target_good = None
                    user.save()
                    self._go_to_state(message, 'shop_state')
                else:
                    # user.state = 'main_menu_state'
                    user.category = user.choosed_category
                    user.choosed_category = None
                    user.save()
                    self._go_to_state(message, '_category_state')

            elif call.data.find('shop_state_inline_button_3_') != -1:
                index = call.data.find('shop_state_inline_button_3_')
                current_page_index, max_pages_count = \
                    [int(x) for x in call.data[index + len('shop_state_inline_button_3_'):].split('_')]

                next_page_index: int = current_page_index + 1 if current_page_index != max_pages_count else 1
                self._go_to_state(
                    message, 'shop_state', call=call,
                    current_page=next_page_index)

            elif call.data.find('shop_state_inline_button_') != -1:
                good_id = call.data[len('shop_state_inline_button_'):]
                good: Product = Product.objects(id=good_id).first()
                user.target_good = good
                user.save()
                self._go_to_state(message, 'shop_state')

    def settings_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        user_lang = user.user_lang
        if entry:
            user.is_in_settings = True
            user.save()
            self.delete_msgs(self._bot, user)
            # if reg_user:
            adress = reg_user.address if reg_user.address else ''
            phone = reg_user.phone if reg_user.phone else ''
            text = self.locale_text(user_lang, 'settings_main_msg').format(adress, phone)
            msg_to_del = self._bot.send_message(user.user_id, text,
                                                reply_markup=keyboards.settings_keyboard(user_lang),
                                                parse_mode='markdown')

            user.msgs_to_del.append(msg_to_del.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'change_adres_btn'):
                user.change_address = True
                user.save()
                self._go_to_state(message, 'log_password_state')
            elif message.text == self.locale_text(user_lang, 'change_phone_btn'):
                user.change_phone = True
                user.save()
                self._go_to_state(message, 'log_password_state')
            elif message.text == self.locale_text(user_lang, 'save_btn'):
                user.is_in_settings = False
                user.save()
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                   self.delete_msgs(self._bot, user))
                msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'settings_save_msg'))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()
                self._go_to_state(message, 'cabinet_state')
            elif message.text == self.locale_text(user_lang, 'back_btn'):
                self._go_to_state(message, 'cabinet_state')
                user.is_in_settings = False
                user.save()
            elif message.text == self.locale_text(user_lang, 'cancel_btn'):
                self._go_to_state(message, 'cabinet_state')
                user.is_in_settings = False
                user.save()
            elif message.text == self.locale_text(user_lang, 'buy_place_in_structure_btn'):
                if not reg_user.is_main_structure:
                    if not reg_user.is_registered:
                        self._go_to_state(message, 'register_state')
                    referrals_indent.referrals_indent(user, reg_user)
                    # self.create_default_fields(reg_user, self.locale_text)
                    core: Core = Core.objects.first()

                    referrals_indent.referrals_indent(user, reg_user)
                    reg_user.is_main_structure = True
                    reg_user.save()
                    #   todo balance check
                    data = reg_user.univers_distribute_general_pack(core.subscribe_price + reg_user.frozen_distribute_sum)
                    for par in data:
                        parent = UserRegister.objects(id=par).first()
                        tgs = User.objects(auth_login=parent.login)
                        for tg in tgs:
                            msg_to_del = self._bot.send_message(tg.user_id,
                                                              Text.objects(tag='destributed_cash').first().\
                                                                values.get(tg.user_lang).\
                                                                format(parent.login, data[par]))
                            tg.msgs_to_del.append(msg_to_del.message_id)
                            tg.save()

                    self._go_to_state(message, 'cabinet_state')
                else:
                    self._go_to_state(message, 'cabinet_state')

        # view/apply cart state
    def v_a_c_s(self, message, entry=False, call: types.CallbackQuery = None, current_page: int = 1):
        core: Core = Core.objects.first()
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
        user_lang = user.user_lang
        full_price: float = 0
        share_template: str = ''
        if user.from_cabinet:
            user.state = 'cabinet_state'
            user.save()
        else:
            user.state = 'main_menu_state'
            user.save()

        if entry:
            # if user.cart:
            print(user.state)
            if not call:
                if user.from_cabinet:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    user.state = 'cabinet_state'
                    user.save()
                else:
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    user.state = 'main_menu_state'
                    user.save()

            if user.cart:
                unique_basket: list = list()
                for i in user.cart:
                    if i not in unique_basket:
                        unique_basket.append(i)

                for i in unique_basket:
                    full_price += user.cart.count(i) * float(i.fields.get('price'))

                pages_count = math.ceil(len(unique_basket))
                good: Product = unique_basket[current_page - 1]

                text: str = str()

                fields: dict = good.fields

                # name = fields.get('name')
                # description = fields.get('description')
                # price = fields.get('price')
                #
                # target_field = Field.objects(Q(user=good.creator) & Q(field_tag='name')).first()
                # text += '*' + target_field.names.get(user.user_lang) + ': *'
                # text += '{0}\n\n'.format(name)
                # target_field = Field.objects(Q(user=good.creator) & Q(field_tag='description')).first()
                # text += '*' + target_field.names.get(user.user_lang) + ': *'
                # text += '{0}\n'.format(description)

                for field in fields:
                    target_field = Field.objects(Q(user=good.creator) & Q(field_tag=field)).first()
                    if target_field and field != 'reward':
                        text += '*' + target_field.names.get(user.user_lang).replace(':', '') + ': *'
                        text += '{0}\n'.format(fields[field])
                if len(good.images) != 0:
                    text += u'\n[\u200B]({0})'.format('admin-setevik.botup.pp.ua/view/img/{0}'.format(
                        good.images[0]))
                print(text)
                # text += '\n' + good.fields.get('description')
                # text += price
                address = reg_user.address if reg_user.address else self.locale_text(user_lang, 'does_not_exist_msg')
                phone = reg_user.phone if reg_user.phone else self.locale_text(user_lang, 'does_not_exist_msg')
                text += '\n' + self.locale_text(user_lang, 'settings_main_msg').format(address, phone)

                if call:

                    msg_to_del = self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                                             reply_markup=keyboards.view_basket_keyboard(user, good, full_price,
                                                                                                         current_page, pages_count),
                                                             parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()

                    if user.from_cabinet:
                        user.state = 'cabinet_state'
                        user.save()
                    else:
                        user.state = 'main_menu_state'
                        user.save()
                else:

                    msg_to_del = self._bot.send_message(user.user_id, text,
                                                        reply_markup=keyboards.view_basket_keyboard(user, good, full_price,
                                                                                                    current_page, pages_count),
                                                        parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                    if user.from_cabinet:
                        user.state = 'cabinet_state'
                        user.save()
                    else:
                        user.state = 'main_menu_state'
                        user.save()

            else:
                text = self.locale_text(user_lang, 'empty_cart_msg')
                keyboard = keyboards.no_buy_history_keyboard(user_lang)
                msg_to_del = self._bot.send_message(user.user_id, text, reply_markup=keyboard, parse_mode='markdown')
                user.msgs_to_del.append(msg_to_del.message_id)
                if user.from_cabinet:
                    user.state = 'cabinet_state'
                    user.save()
                else:
                    user.state = 'main_menu_state'
                    user.save()
            # else:
            #     self._go_to_state(message, 'main_menu_state')
            #     return None

        else:
            if call.data.find('v_a_c_s_inline_button_del_good_') != -1:
                good_id = call.data[len('v_a_c_s_inline_button_del_good_'):]
                good: Product = Product.objects(id=good_id).first()
                # print(user.cart)

                while user.cart.count(good) != 0:
                    user.cart.remove(good)
                    user.save()
                # self._bot.delete_message(chat_id=message.chat.id, message_id=call.message.message_id)
                self._go_to_state(message, 'v_a_c_s', call=call)

            elif call.data == 'v_a_c_s_inline_button_count':
                self._bot.answer_callback_query(call.id, text=self.locale_text(user_lang, 'count_msg'))
                if user.from_cabinet:
                    user.state = 'cabinet_state'
                    user.save()
                else:
                    user.state = 'main_menu_state'
                    user.save()

            elif call.data == 'v_a_c_s_inline_button_number':
                self._bot.answer_callback_query(call.id, text=self.locale_text(user_lang, 'number'))
                if user.from_cabinet:
                    user.state = 'cabinet_state'
                    user.save()
                else:
                    user.state = 'main_menu_state'
                    user.save()

            elif call.data == 'v_a_c_s_inline_button_change_address':
                user.change_address = True
                user.save()
                self._go_to_state(message, 'log_password_state')

            elif call.data == 'v_a_c_s_inline_button_change_phone':
                user.change_phone = True
                user.save()
                self._go_to_state(message, 'log_password_state')

            elif call.data.find('v_a_c_s_inline_button_share_') != -1:
                good_id = call.data[len('v_a_c_s_inline_button_share_'):]
                good: Product = Product.objects(id=good_id).first()
                fields: dict = good.fields

                for field in fields:
                    target_field = Field.objects(Q(user=good.creator) & Q(field_tag=field)).first()
                    if target_field and field != 'reward':
                        share_template += '*' + target_field.names.get(user.user_lang).replace(':', '') + ': *'
                        share_template += '{0}\n'.format(fields[field])

                share_template += u'\n[\u200B]({0})'.format('admin-setevik.botup.pp.ua/view/img/{0}'.format(
                    good.images[0]))

                if user.from_cabinet:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user,
                                       self.delete_msgs)
                    user.state = 'cabinet_state'
                    user.save()
                else:
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user,
                                       self.delete_msgs)
                    user.state = 'main_menu_state'
                    user.save()

                try:
                    msg_to_del = self._bot.edit_message_text(self.locale_text(user_lang, 'first_share_msg'),
                                                             user.user_id, call.message.message_id, parse_mode='markdown')
                except:
                    msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'first_share_msg'),
                                                        parse_mode='markdown')
                text = share_template + '\n' + self.locale_text(user_lang, 'ref_link_product_template'). \
                    format(core.shop_name_text, (str(reg_user.id)), (str(good.id)))
                msg_to_del_1 = self._bot.send_message(user.user_id, text, parse_mode='markdown')
                user.msgs_to_del.append(msg_to_del.message_id)
                user.msgs_to_del.append(msg_to_del_1.message_id)
                user.save()

            elif call.data.find('v_a_c_s_inline_button_up_') != -1:
                good_id, current_page = call.data[len('v_a_c_s_inline_button_up_'):].split('_')
                good: Product = Product.objects(id=good_id).first()
                user.cart.append(good)
                user.save()
                self._go_to_state(message, 'v_a_c_s', call=call, current_page=int(current_page))

            elif call.data.find('v_a_c_s_inline_button_down_') != -1:
                good_id, current_page = call.data[len('v_a_c_s_inline_button_down_'):].split('_')
                good: Product = Product.objects(id=good_id).first()
                if user.cart.count(good) == 1:
                    self._bot.answer_callback_query(call.id, text=self.locale_text(user_lang, 'low_count'))
                    if user.from_cabinet:
                        user.state = 'cabinet_state'
                        user.save()
                    else:
                        user.state = 'main_menu_state'
                        user.save()
                else:
                    user.cart.remove(good)
                    user.save()
                    self._go_to_state(message, 'v_a_c_s', call=call, current_page=int(current_page))

            elif call.data.find('v_a_c_s_inline_button_accept') != -1:
                if reg_user.address and reg_user.address != '':
                    for i in user.cart:
                        full_price += float(i.fields.get('price'))
                    if reg_user.balance >= full_price:
                        reg_user.balance -= full_price
                        reg_user.save()
                        # NOTIFICATION FOR GOOD OWNER
                        for i in user.catr:
                            creator = UserRegister.objects(id=i.creator.id).first()
                            text = self.locale_text(user.user_lang, 'buy_good')
                            text = text.format(i.fields['name'])
                            users = User.objects(auth_login=creator.login)
                            for user in users:
                                msg_to_del = self._bot.send_message(user.user_id, text)
                                user.msgs_to_del.append(msg_to_del.message_id)
                                user.save()
                        self._go_to_state(message, 'order_finale_state')
                    else:
                        self._bot.answer_callback_query(call.id, self.locale_text(user_lang, 'low_balance'))
                else:
                    self._bot.answer_callback_query(call.id, self.locale_text(user_lang, 'address_required_msg'))

            elif call.data.find('v_a_c_s_inline_button_1_') != -1:

                index = call.data.find('v_a_c_s_inline_button_1_')
                current_page_index, max_pages_count = \
                    [int(x) for x in call.data[index + len('v_a_c_s_inline_button_1_'):].split('_')]

                next_page_index: int = current_page_index - 1 if current_page_index != 1 else max_pages_count

                self._go_to_state(
                    message, 'v_a_c_s', call=call,
                    current_page=next_page_index
                )

            elif call.data.find('v_a_c_s_inline_button_2') != -1:
                self._bot.delete_message(user.user_id, call.message.message_id)
                if user.from_cabinet:
                    user.from_cabinet = False
                    user.save()
                    self._go_to_state(message, 'cabinet_state')
                else:
                    self._go_to_state(message, 'shop_state')

            elif call.data.find('v_a_c_s_inline_button_3_') != -1:
                index = call.data.find('v_a_c_s_inline_button_3_')
                current_page_index, max_pages_count = \
                    [int(x) for x in call.data[index + len('v_a_c_s_inline_button_3_'):].split('_')]

                next_page_index: int = current_page_index + 1 if current_page_index != max_pages_count else 1

                self._go_to_state(
                    message, 'v_a_c_s', call=call,
                    current_page=next_page_index)

    def order_finale_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
        core = Core.objects.first()
        unique_cart = list()

        date = datetime.datetime.now(self.Zone(3, False, 'GMT'))
        for product in Product.objects():
            print('product id: {0}'.format(product.id))
        for good in user.cart:
            if good not in unique_cart:
                unique_cart.append(good)

        for good in unique_cart:
            order = Order()
            order.good = good
            order.sum = round(float(good.fields.get('price'))*user.cart.count(good), 2)
            order.reward = round(float(good.fields.get('reward'))*user.cart.count(good), 2)
            order.user = reg_user
            order.order_id = core.order_counter
            order.adres = reg_user.address
            order.phone = reg_user.phone
            order.date = date
            order.sailer = good.creator
            order.counter = user.cart.count(good)
            order.status = Text.objects(tag='moderate_order_status').first().values
            order.save()

            core.order_counter += 1
            core.save()

        user.is_in_shop = False
        user.choosed_category = None
        user.cart = list()
        user.save()

        text = self.locale_text(user.user_lang, 'order_accepted_msg')
        if user.from_cabinet:
            self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
        else:
            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

        msg_to_del = self._bot.send_message(user.user_id, text, parse_mode='Markdown')
        user.msgs_to_del.append(msg_to_del.message_id)
        if user.from_cabinet:
            user.state = 'cabinet_state'
        else:
            user.state = 'main_menu_state'
        user.save()
        # self._go_to_state(message, 'main_menu_state')
        # statuses

    def enter_adres_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        if entry:
            self.delete_msgs(self._bot, user)

            text = self.locale_text(user_lang, 'enter_adres_msg')
            msg_to_del = self._bot.send_message(user.user_id, text,
                                                reply_markup=keyboards.reply_back_keyboard(user_lang))
            user.msgs_to_del.append(msg_to_del.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'back_btn'):
                if user.is_in_settings:
                    self._go_to_state(message, 'settings_state')
                else:
                    self._go_to_state(message, 'v_a_c_s')

            elif message.text:
                user.adress = message.text
                reg_user.address = message.text
                user.save()
                reg_user.save()
                if user.is_in_settings:
                    self._go_to_state(message, 'settings_state')
                else:
                    self._go_to_state(message, 'v_a_c_s')

    def enter_phone_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        core: Core = Core.objects.first()
        reg_user = UserRegister.objects(login=user.auth_login).first()
        if not reg_user:
            reg_user = user.defaul_unregister_user
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        if entry:
            for msg_to_del in user.msgs_to_del:
                try:
                    self._bot.delete_message(user.user_id, msg_to_del)
                except Exception as e:
                    pass
            user.msgs_to_del = list()
            user.save()
            text = self.locale_text(user_lang, 'request_phone_msg')
            msg_to_del = self._bot.send_message(
                user.user_id, text,
                reply_markup=keyboards.phone_request_keyboard(user_lang),
                parse_mode='Markdown'
            )
            user.msgs_to_del.append(msg_to_del.message_id)
            user.save()
        else:
            if message.contact:
                user.phone = message.contact.phone_number
                user.save()
                reg_user.phone = message.contact.phone_number
                reg_user.save()
                user.order_phone = message.contact.phone_number
                user.save()
                if user.is_in_settings:
                    self._go_to_state(message, 'settings_state')
                else:
                    self._go_to_state(message, 'v_a_c_s')

            else:
                if message.text == self.locale_text(user_lang, 'cancel_msg'):
                    if user.is_in_settings:
                        self._go_to_state(message, 'settings_state')
                    else:
                        self._go_to_state(message, 'v_a_c_s')

                else:
                    number = message.text
                    try:
                        if carrier._is_mobile(number_type(phonenumbers.parse(number))):
                            user.phone = number
                            user.save()
                            reg_user.phone = number
                            reg_user.save()
                            if user.is_in_settings:
                                self._go_to_state(message, 'settings_state')
                            else:
                                self._go_to_state(message, 'v_a_c_s')
                        else:
                            text = self.locale_text(user_lang, 'phone_validation_error_msg')
                            msg_to_del = self._bot.send_message(
                                message.chat.id,
                                text,
                                reply_markup=keyboards.phone_request_keyboard(user_lang),
                                parse_mode='Markdown')
                            user.msgs_to_del.append(msg_to_del.message_id)
                            user.save()
                    except phonenumbers.NumberParseException:
                        text = self.locale_text(user_lang, 'phone_validation_error_msg')
                        msg_to_del = self._bot.send_message(message.chat.id, text,
                                                            reply_markup=keyboards.phone_request_keyboard(user_lang),
                                                            parse_mode='Markdown')
                        user.msgs_to_del.append(msg_to_del.message_id)
                        user.save()

    def request_phone_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang

        if entry:
            for msg_to_del in user.msgs_to_del:
                try:
                    self._bot.delete_message(user.user_id, msg_to_del)
                except Exception as e:
                    pass
            user.msgs_to_del = list()
            user.save()
            text = self.locale_text(user_lang, 'request_phone_msg')
            self._bot.send_message(
                user.user_id, text,
                reply_markup=keyboards.phone_request_keyboard(user_lang),
                parse_mode='Markdown'
            )
        else:
            if message.contact:
                user.phone = message.contact.phone_number
                user.save()
                self._go_to_state(message, 'cabinet_state')
            else:
                number = message.text
                try:
                    if carrier._is_mobile(number_type(phonenumbers.parse(number))):
                        user.phone = number
                        user.save()

                        self._go_to_state(message, 'cabinet_state')
                    else:
                        text = self.locale_text(user_lang, 'phone_validation_error_msg')
                        self._bot.send_message(
                            message.chat.id,
                            text,
                            reply_markup=keyboards.phone_request_keyboard(user_lang),
                            parse_mode='Markdown'
                        )
                except phonenumbers.NumberParseException:
                    text = self.locale_text(user_lang, 'phone_validation_error_msg')
                    self._bot.send_message(
                        message.chat.id,
                        text,
                        reply_markup=keyboards.phone_request_keyboard(user_lang),
                        parse_mode='Markdown'
                    )

    def _category_state(self, message, entry=False, call: types.CallbackQuery = None, current_page: int = 1,
                        is_del: bool = True, search: dict = None):

        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)
        goods = None
        core: Core = Core.objects.first()
        if not search:
            if not user.category:
                if user.is_in_shop:
                    categories = self.categories_validate(Category.objects(Q(parent_category=None) &
                                                                           Q(is_moderated=True) &
                                                                           Q(goods_num__gte=0)))
                else:
                    categories = Category.objects(Q(parent_category=None) & Q(is_moderated=True) & Q(goods_num__gte=0))

                pages_count = math.ceil(
                    len(categories) / float(core.category_row_num * core.category_col_num)
                )

                if user.is_in_shop:
                    text = self.locale_text(user.user_lang, 'user_in_shop_msg')

                else:
                    text = self.locale_text(user_lang, 'category_msg')

            else:
                if user.is_in_shop:
                    categories = self.categories_validate(Category.objects(Q(parent_category=user.category)
                                                                           & Q(is_moderated=True)))
                    goods: Product = Product.objects(Q(category=user.category) & Q(is_accepted=True)
                                                     & Q(is_active=True))

                else:
                    categories = Category.objects(Q(parent_category=user.category) & Q(is_moderated=True))
                    goods = list()

                pages_count = math.ceil(
                    len(categories) + len(goods) / float(core.category_row_num * core.category_col_num)
                )

                if len(categories) + len(goods) == 0:
                    user.choosed_category = user.category
                    user.category = None
                    user.save()
                    if user.is_in_shop:
                        self._go_to_state(message, 'shop_state', call=call)
                        return None
                    else:
                        field = user.fields_without_value.pop(0)

                        user.current_field = field
                        user.save()
                        # try:
                        self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                        # except Exception as e:
                        #     print(e)
                        self._go_to_state(message, 'enter_field_state', field=user.current_field)
                        return None

                text = self.locale_text(user_lang, 'categories_msg')
        else:
            text = self.locale_text(user_lang, 'result_of_search')
            categories = search.get('categories')
            goods = search.get('goods')

            pages_count = math.ceil(
                len(categories) + len(goods) / float(core.category_row_num * core.category_col_num)
            )

        if entry:
            if user.is_in_shop:
                if user.from_cabinet:
                    user.state = 'cabinet_state'
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                    user.save()
                else:
                    user.state = 'main_menu_state'
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    user.save()
            else:
                user.state = 'cabinet_state'
                self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user, self.delete_msgs)
                user.save()
            #
            # if user.is_in_shop:
            #     self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user)
            # else:
            #     self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user)

            if user.category:
                cat_text = '\n' + self.locale_text(user_lang,
                                                   'current_category').format(user.category.values.get(user_lang))
                text += cat_text

            try:
                self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                            reply_markup=keyboards.category_keyboard(
                                                user_lang, categories,
                                                current_page=current_page,
                                                max_pages_count=pages_count,
                                                col_num=core.category_col_num,
                                                row_num=core.category_row_num,
                                                user=user, goods=goods
                                            ))
            except Exception as e:
                print(e)
                try:
                    self._bot.delete_message(user.user_id, call.message.message_id)
                except Exception as e:
                    print(e)
                msg = self._bot.send_message(user.user_id, text,
                                             reply_markup=keyboards.category_keyboard(
                                                 user_lang, categories,
                                                 current_page=current_page,
                                                 max_pages_count=pages_count,
                                                 col_num=core.category_col_num,
                                                 row_num=core.category_row_num,
                                                 user=user, goods=goods
                                             ))
                user.msgs_to_del.append(msg.message_id)
                user.save()
        else:
            if call:
                if call.data.find('_category_state_inline_button_1_') != -1:
                    index = call.data.find('_category_state_inline_button_1_')
                    current_page_index, max_pages_count = \
                        [int(x) for x in call.data[index + len('_category_state_inline_button_1_'):].split('_')]

                    next_page_index: int = current_page_index - 1 if current_page_index != 1 else max_pages_count

                    self._go_to_state(
                        message, '_category_state', call=call,
                        current_page=next_page_index
                    )

                elif call.data.find('_category_state_inline_button_2') != -1:
                    # self._bot.delete_message(chat_id=message.chat.id, message_id=call.message.message_id)

                    if user.category:
                        user.category = None
                        user.save()
                        self._go_to_state(message, '_category_state', call=call)
                    else:
                        if user.is_in_shop:
                            user.is_in_shop = False
                            user.save()
                            self._go_to_state(message, 'new_shop_state')
                        else:
                            user.fields_without_value = None
                            user.save()
                            self._go_to_state(message, 'cabinet_state')

                elif call.data.find('_category_state_inline_button_3_') != -1:
                    index = call.data.find('_category_state_inline_button_3_')
                    current_page_index, max_pages_count = \
                        [int(x) for x in call.data[index + len('_category_state_inline_button_3_'):].split('_')]

                    next_page_index: int = current_page_index + 1 if current_page_index != max_pages_count else 1
                    self._go_to_state(
                        message, '_category_state', call=call,
                        current_page=next_page_index
                    )
                elif call.data == '_category_state_inline_button_apply':
                    user.choosed_category = user.category
                    user.category = None
                    user.save()

                    field = user.fields_without_value.pop(0)

                    user.current_field = field
                    user.save()
                    # try:
                    self.save_keyboard(self._bot, keyboards.cabinet_keyboard(user_lang, user), user)

                    # except Exception as e:
                    #     print(e)
                    self._go_to_state(message, 'enter_field_state', field=user.current_field)
                    return None
                elif call.data.find('_category_state_inline_button_good_') != -1:
                    good_id = call.data[len('_category_state_inline_button_good_'):]
                    good: Product = Product.objects(id=good_id).first()
                    user.target_good = good
                    # user.category = None
                    user.save()
                    self._go_to_state(message, 'shop_state')

                elif call.data.find('_category_state_inline_button_') != -1:
                    id = call.data[len('_category_state_inline_button_'):]
                    category: Category = Category.objects(id=id).first()
                    user.category = category
                    user.save()
                    self._go_to_state(message, '_category_state', call=call, current_page=1)

            # else:

            #     self._bot.send_message(user.user_id, text=self.locale_text(user_lang, 'error_msg'))

    # for take field's name to enter use self.local_field_name(lang, field)
    def enter_field_state(self, message, entry=False, call: types.CallbackQuery = None, field: Field = None):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        if not field:
            field = user.current_field

        if entry:
            self.save_keyboard(self._bot, keyboards.back_pass_keyboard(user_lang), user, self.delete_msgs)
            if user.low_price:
                msg_to_del = self._bot.send_message(user.user_id,
                                                    self.locale_text(user_lang, 'low_price_warning'))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()
            # field_name: str = self.local_field_name(user_lang, field).lower()
            text = field.message.get(user_lang) if field.is_required else \
                self.locale_text(user_lang, 'enter_msg').format(field.names.get(user_lang))
            msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.back_pass_keyboard(user_lang))
            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'back_btn'):

                if user.entered_fields:
                    previous_field = user.entered_fields.pop()
                    user.fields_without_value.insert(0, user.current_field)
                    user.current_field = previous_field
                    user.save()

                    self._go_to_state(message, 'enter_field_state', field=user.current_field)
                else:
                    user.fields_without_value = None
                    user.entered_fields = None
                    user.current_field = None
                    user.save()
                    self._go_to_state(message, 'cabinet_state')
            elif message.text == self.locale_text(user_lang, 'pass_btn_2'):
                if user.current_field.is_required:
                    msg = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'requirement_field_msg'))
                    user.msgs_to_del.append(msg.message_id)
                    user.save()
                else:
                    if len(user.fields_without_value) == 0:
                        user.current_field.value = None
                        user.current_field.save()
                        user.entered_fields.append(user.current_field)
                        user.current_field = None
                        user.save()
                        self._go_to_state(message, 'pin_photo_to_advert')
                    else:
                        user.current_field.value = None
                        user.current_field.save()
                        user.entered_fields.append(user.current_field)
                        user.current_field = user.fields_without_value.pop(0)
                        user.save()
                        self._go_to_state(message, 'enter_field_state', field=user.current_field)
            elif message.text == self.locale_text(user_lang, 'cancel_msg'):
                user.fields_without_value = None
                user.current_field = None
                user.entered_fields = None
                user.low_price = None
                user.save()
                self._go_to_state(message, 'cabinet_state')
            elif message.text:
                if user.current_field.field_tag == "price" or user.current_field.field_tag == "reward":
                    value = message.text
                    # field_tag = user.current_field.field_tag
                    try:
                        value = round(float(value), 2)
                        value_check = math.sqrt(1/value)

                        user.current_field.value = str(value)
                        if user.current_field.field_tag == 'price':
                            if round(float(user.entered_fields[-1].value),2) >= value:
                                user.low_price = True
                                user.save()
                                # self._go_to_state(message, 'enter_field_state', field=user.current_field)
                            else:
                                user.low_price = False
                                user.save()
                                user.current_field.save()
                                user.entered_fields.append(user.current_field)
                                user.current_field = user.fields_without_value.pop(0) if len(user.fields_without_value) \
                                                                                         != 0 else None
                                user.save()
                        else:
                            user.current_field.save()
                            user.entered_fields.append(user.current_field)
                            user.current_field = user.fields_without_value.pop(0) if len(user.fields_without_value)!= 0 \
                                else None
                            user.save()

                        try:
                            self._bot.delete_message(user.user_id, user.msg_to_delete)
                        except Exception as e:
                            print(e)

                        if user.current_field:
                            self._go_to_state(message, 'enter_field_state', field=user.current_field)
                        else:
                            self._go_to_state(message, 'pin_photo_to_advert')

                    except ValueError:
                        msg = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'enter_number'))
                        user.msgs_to_del.append(msg.message_id)
                        user.save()
                else:
                    user.current_field.value = message.text
                    user.current_field.save()
                    user.entered_fields.append(user.current_field)
                    user.current_field = user.fields_without_value.pop(0) if len(user.fields_without_value) != 0 \
                        else None
                    user.save()
                    # try:
                    #     self._bot.delete_message(user.user_id, user.msg_to_delete)
                    # except Exception as e:
                    #     print(e)
                    if user.current_field:
                        self._go_to_state(message, 'enter_field_state', field=user.current_field)
                    else:
                        self._go_to_state(message, 'pin_photo_to_advert')
                # else:
                #     if user.current_field.field_tag == "price" or user.current_field.field_tag == "reward":
                #         value = message.text
                #         try:
                #             value = float(value)
                #             user.current_field.value = str(value)
                #             user.current_field.save()
                #             user.entered_fields.append(user.current_field)
                #             user.current_field = user.fields_without_value.pop(0)
                #             user.save()
                #             # try:
                #             #     self._bot.delete_message(user.user_id, user.msg_to_delete)
                #             # except Exception as e:
                #             #     print(e)
                #             self._go_to_state(message, 'enter_field_state', field=user.current_field)
                #         except ValueError:
                #             msg = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'enter_number'))
                #             user.msgs_to_del.append(msg.message_id)
                #             user.save()
                #     else:
                #         user.current_field.value = message.text
                #         user.current_field.save()
                #         user.entered_fields.append(user.current_field)
                #         user.current_field = user.fields_without_value.pop(0)
                #         user.save()
                #         # try:
                #         #     self._bot.delete_message(user.user_id, user.msg_to_delete)
                #         # except Exception as e:
                #         #     print(e)
                #         self._go_to_state(message, 'enter_field_state', field=user.current_field)

    # add button to pass and create final_advert_state
    def pin_photo_to_advert(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)


        if entry:
            self.delete_msgs(self._bot, user)

            text = self.locale_text(user_lang, 'pin_photo_msg')
            msg = self._bot.send_message(user.user_id, text, reply_markup=keyboards.send_keyboard(user_lang))
            user.msgs_to_del.append(msg.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user_lang, 'send_btn'):
                self.delete_msgs(self._bot, user)
                msg = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'request_accepted_msg'))
                user.msgs_to_del.append(msg.message_id)
                user.save()
                self._go_to_state(message, 'advert_finale')
            elif message.text == self.locale_text(user_lang, 'cancel_msg'):
                photo = Photo.objects(user=reg_user).first()
                user.fields_without_value = None
                user.current_field = None
                user.entered_fields = None
                user.save()
                photo.paths = None
                photo.save()
                self._go_to_state(message, 'cabinet_state')
            elif message.content_type == 'photo' or message.content_type == 'document':
                photo = Photo.objects(user=reg_user).first()

                doc = self._bot.get_file(message.photo[-1].file_id) if message.content_type == 'photo' else \
                    self._bot.get_file(message.document.thumb.file_id)
                path = doc.file_path
                image = self._bot.download_file(path)
                src = '{}/src/web_admin_panel/static/tg_documents/photos/{}{}'.format(
                    os.getcwd(),
                    str(doc.file_id),
                    path[7:] if message.content_type == 'photo' else path[11:]
                )
                src_2 = '{}/src/web_personal_cabinet/static/tg_documents/photos/{}{}'.format(
                    os.getcwd(),
                    str(doc.file_id),
                    path[7:] if message.content_type == 'photo' else path[11:]
                )

                with open(src, 'wb') as new_file:
                    new_file.write(image)
                with open(src_2, 'wb') as new_file_2:
                    new_file_2.write(image)

                image_path = 'tg_documents/photos/' + str(doc.file_id) + path[7:] if message.content_type == 'photo'\
                    else 'tg_documents/photos/' + str(doc.file_id) + path[11:]
                photo.update(add_to_set__paths=image_path)
                photo.reload()

    def company_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        core: Core = Core.objects.first()
        user_lang = user.user_lang

        if entry:

            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
            msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user.user_lang, 'company'),
                                                reply_markup=keyboards.company_keyboard(user.user_lang))
            # try:
            #     self._bot.delete_message(user.user_id, user.txt_msg_to_edit)
            #     print('company deleted')
            # except:
            #     print('nothing to del company')
            # user.msgs_to_del.append(msg_to_del.message_id)
            # self.delete_msgs(self._bot, user)

            user.msgs_to_del.append(msg_to_del.message_id)
            user.state = 'main_menu_state'
            user.save()
        else:
            if call:
                if call.data == 'company_state_inline_button_1_option':
                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    msg = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'company_history_msg').\
                                                 format(core.shop_name_text, core.shop_name_text))

                    text = self.locale_text(user_lang, 'company_history_msg_2').format(core.shop_name_text)
                    msg_2 = self._bot.send_message(user.user_id, text, parse_mode='markdown',
                                                   reply_markup=keyboards.history_keyboard(user_lang))
                    # self.delete_msgs(self._bot, user)
                    user.msgs_to_del.append(msg.message_id)
                    user.msgs_to_del.append(msg_2.message_id)
                    user.state = 'main_menu_state'
                    user.save()
                elif call.data == 'company_state_inline_button_5_option':
                    # self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    self._bot.delete_message(user.user_id, call.message.message_id)
                    # self.delete_msgs(self._bot, user)
                    self._go_to_state(message, 'feedback_state')
                elif call.data == 'company_state_inline_button_4_option':

                    self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                    # self.delete_msgs(self._bot, user)
                    self._go_to_state(message, 'company_state')
                    # self._bot.delete_message(user.user_id, call.message.message_id)

                    user.state = 'main_menu_state'
                    user.save()
                elif call.data == 'company_state_inline_button_2_option':
                    text = self.locale_text(user_lang, 'mission_button_msg').format(core.shop_name_text)
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id)
                    user.state = 'main_menu_state'
                    user.save()
                elif call.data == 'company_state_inline_button_3_option':
                    text = self.locale_text(user.user_lang, 'whitepaper_button_msg')
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id)
                    user.state = 'main_menu_state'
                    user.save()
                elif call.data == 'company_state_inline_button_6_option':
                    src = '{0}/src/web_admin_panel/static/tg_documents/files/{1}'.format(os.getcwd(),
                                                                                         'presentation.pdf')
                    data = open(src, 'rb')

                    msg_to_del = self._bot.send_document(user.user_id, data)
                    data.close()
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.state = 'main_menu_state'
                    user.save()

                elif call.data == 'company_state_inline_button_7_option':
                    text = self.locale_text(user.user_lang, 'sup_project').format(
                        core.bitcoin_wallet,
                        core.bip_minter_wallet,
                        core.ethereum_wallet,
                        core.perfectmoney_wallet,
                        core.sber_wallet
                    )
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id, parse_mode='markdown')
                    user.state = 'main_menu_state'
                    user.save()

    def contacts_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        faq: Frequent = Frequent.objects
        user_lang = user.user_lang

        if entry:
            # self.delete_msgs(self._bot, user)
            text = self.locale_text(user.user_lang, 'contacts_menu_msg')
            # main_menu_keyboard = keyboards.main_menu_keyboard(user_lang)
            # try:
            #     print(user.msgs_to_del)
            #     print('---')
            #     print(user.txt_msg_to_edit)
            #     msg_to_del = self._bot.edit_message_text(text, user.user_id, message_id=user.txt_msg_to_edit, reply_markup=main_menu_keyboard)
            #     user.msgs_to_del.append(msg_to_del.message_id)
            #     user.save()
            #     print('contacts edited')
            # except:
            #     print('contacts edit not worked')
            #     pass
            try:
                self._bot.delete_message(user.user_id, user.txt_msg_to_edit)
            except:
                print('nothing to del')

            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

            msg_to_del = self._bot.send_message(user.user_id, text,
                                                reply_markup=keyboards.contacts_keyboard(user.user_lang))
            user.msgs_to_del.append(msg_to_del.message_id)
            # user.txt_msg_to_edit = msg_to_del.message_id
            user.state = 'main_menu_state'
            user.save()
        else:

            if call.data == 'contacts_state_inline_button_1_option':
                self._go_to_state(message, 'feedback_state')
            elif call.data == 'contacts_state_inline_button_2_option':
                if faq:
                    text = ''
                    question_text = self.locale_text(user_lang, 'faq_question')
                    answer_text = self.locale_text(user_lang, 'faq_answer')
                    for question in faq:
                        new_text = question_text + question.question_lang.get(user_lang) + answer_text + \
                                   question.answer_lang.get(user_lang) + '\n'
                        text += new_text
                else:
                    text = self.locale_text(user.user_lang, 'nothing_to_show')
                # self.delete_msgs(self._bot, user)
                res = list(text[i:i + 4000] for i in range(0, len(text), 4000))
                for i in res:
                    msg_to_del = self._bot.send_message(user.user_id, i)

                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.state = 'main_menu_state'
                    user.save()
            elif call.data == 'contacts_state_inline_button_3_option':
                text = self.locale_text(user.user_lang, 'comments_msg')
                self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                            reply_markup=keyboards.comments_keyboard(user.user_lang))
                user.state = 'main_menu_state'
                user.save()
            elif call.data == 'contacts_state_inline_button_1_option_comment':

                # self.delete_msgs(self._bot, user)
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

                self._go_to_state(message, 'leave_comment_state')
            elif call.data == 'contacts_state_inline_button_2_option_comment':
                self._go_to_state(message, 'comments_state')

    def leave_comment_state(self, message, entry=False, call: types.CallbackQuery = None):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        user_lang = user.user_lang

        if entry:
            # self.delete_msgs(self._bot, user)
            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

            msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user.user_lang, 'leave_comment_msg'))

            user.msgs_to_del.append(msg_to_del.message_id)
            user.save()
        else:
            if message.text == self.locale_text(user.user_lang, 'user_cabinet'):
                self._go_to_state(message, 'cabinet_state')
            elif message.text == self.locale_text(user.user_lang, 'company'):
                self._go_to_state(message, 'company_state')
            elif message.text == self.locale_text(user.user_lang, 'contacts'):
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'contacts_state')
            elif message.text == self.locale_text(user.user_lang, 'market'):
                user.is_in_shop = True
                user.save()
                self._go_to_state(message, '_category_state')
            elif message.text == self.locale_text(user.user_lang, 'back_btn'):
                self._go_to_state(message, 'main_menu_state')

            elif message.text:
                comment = Comment()
                comment.user = user
                comment.comment = message.text
                comment.reg_user = reg_user
                comment.date = datetime.datetime.now(self.Zone(3, False, 'GMT'))
                comment.save()
                # self.delete_msgs(self._bot, user)
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)

                msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user.user_lang,
                                                                                   'thnk_for_comment_msg'))
                user.state = 'main_menu_state'
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()

    def comments_state(self, message, entry=False, call: types.CallbackQuery = None, current_index: int = 1):
        user: User = User.objects(user_id=message.chat.id).first()
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        comments = Comment.objects(is_moderated=True)
        pages_count = math.ceil(len(comments) / float(5))
        comments = comments[(current_index-1)*5:current_index*5]

        if not comments:
            msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user.user_lang, 'nothing_to_show'))
            user.msgs_to_del.append(msg_to_del.message_id)
            user.save()
            user.state = 'main_menu_state'
            user.save()
            return None

        if entry:
            if not call:
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user.user_lang), user, self.delete_msgs)

            one_comment_text = self.locale_text(user.user_lang, 'one_comment_msg')
            if comments.count() > 1:
                text: str = str()
                # if len(comments) > 2:
                for i in comments:
                    text += one_comment_text.format(i.date.strftime("%m/%d/%Y, %H:%M:%S"),
                                                    i.comment) + '\n\n'
                if call:
                    self._bot.edit_message_text(text, user.user_id, call.message.message_id,
                                                reply_markup=keyboards.comments_control_keyboard(user.user_lang,
                                                                                              current_page=current_index,
                                                                                              max_pages_count=pages_count),
                                                parse_mode='markdown')
                else:
                    msg = self._bot.send_message(user.user_id, text, parse_mode='markdown',
                                                 reply_markup=keyboards.comments_control_keyboard(user.user_lang,
                                                                                                  current_page=current_index,
                                                                                                  max_pages_count=pages_count))
                    user.msgs_to_del.append(msg.message_id)
                    user.save()
            else:
                msg_to_del = self._bot.send_message(user.user_id,
                                                    one_comment_text.format(comments[0].strftime("%m/%d/%Y, %H:%M:%S"),
                                                                            comments[0].comment))
                user.msgs_to_del.append(msg_to_del.message_id)
                user.save()
        else:
            if message.text == self.locale_text(user.user_lang, 'user_cabinet'):
                self._go_to_state(message, 'cabinet_state')
            elif message.text == self.locale_text(user.user_lang, 'company'):
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'company_state')
            elif message.text == self.locale_text(user.user_lang, 'contacts'):
                try:
                    self._bot.delete_message(user.user_id, user.msg_to_delete)
                except Exception as e:
                    print(e)
                self._go_to_state(message, 'contacts_state')
            elif message.text == self.locale_text(user.user_lang, 'market'):
                user.is_in_shop = True
                user.save()
                self._go_to_state(message, '_category_state')

            elif call.data.find('comments_state_$$_1_') != -1:
                index = call.data.find('comments_state_$$_1_')
                current_page_index, max_pages_count = \
                    [int(x) for x in call.data[index + len('comments_state_$$_1_'):].split('_')]

                next_page_index: int = current_page_index - 1 if current_page_index != 1 else max_pages_count

                self._go_to_state(
                    message, 'comments_state', call=call,
                    current_index=next_page_index
                )

            elif call.data.find('comments_state_$$_2') != -1:
                # self.delete_msgs(self._bot, user)
                self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user.user_lang), user, self.delete_msgs)
                user.state = 'main_menu_state'
                user.save()

            elif call.data.find('comments_state_$$_3_') != -1:

                index = call.data.find('comments_state_$$_3_')
                current_page_index, max_pages_count = \
                    [int(x) for x in call.data[index + len('comments_state_$$_3_'):].split('_')]

                next_page_index: int = current_page_index + 1 if current_page_index != max_pages_count else 1
                self._go_to_state(
                    message, 'comments_state', call=call,
                    current_index=next_page_index)

    def feedback_state(self, message, entry=False):
        user: User = User.objects(user_id=message.chat.id).first()
        user_lang = user.user_lang
        reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
        self.auth_check(reg_user, self._go_to_state, message, self.user_clear, user)

        feedback = Feedback.objects(user=user).first()

        if not feedback:
            feedback = Feedback()
            feedback.user = user
            feedback.reg_user = reg_user

        gmt = self.Zone(3, False, 'GMT')
        date = datetime.datetime.now(gmt)
        feedback.date = date
        feedback.save()

        if entry:
            for msg_to_del in user.msgs_to_del:
                try:
                    self._bot.delete_message(user.user_id, msg_to_del)
                except Exception as e:
                    pass
            user.msgs_to_del = list()
            user.save()
            msg = self.locale_text(user_lang, 'feedback_msg')
            keyboard = keyboards.feedback_keyboard(user_lang)

            msg_to_del = self._bot.send_message(
                user.user_id, text=msg,
                reply_markup=keyboard,
                parse_mode='markdown'
            )
            user.msgs_to_del.append(msg_to_del.message_id)
            user.save()
        else:
            if message:
                if message.text == self.locale_text(user_lang, 'back_btn'):
                    quest = Question.objects(feedback=feedback).order_by('-date').first()
                    if quest:
                        if quest.date + datetime.timedelta(minutes=5) > datetime.datetime.now():

                            self.delete_msgs(self._bot, user)
                            msg_to_del = self._bot.send_message(user.user_id, self.locale_text(user_lang, 'thnks_for_ur_quest'))
                            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                            user.state = 'main_menu_state'
                            user.msgs_to_del.append(msg_to_del.message_id)
                            user.save()
                        else:
                            # self.delete_msgs(self._bot, user)
                            self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                            user.state = 'main_menu_state'
                            user.save()
                    else:
                        # self.delete_msgs(self._bot, user)
                        self.save_keyboard(self._bot, keyboards.main_menu_keyboard(user_lang), user, self.delete_msgs)
                        user.state = 'main_menu_state'
                        user.save()
                else:
                    if message.content_type == 'text':
                        question = Question()
                        gmt = self.Zone(3, False, 'GMT')
                        date = datetime.datetime.now(gmt)
                        question.date = date
                        question.content_type = 'text'
                        question.text = message.text
                        question.feedback = feedback
                        question.save()

                        feedback.is_new_question_exist = True
                        feedback.save()
                    elif message.content_type == 'photo':
                        print(message)
                        doc = self._bot.get_file(message.photo[-1].file_id)
                        path = doc.file_path
                        image = self._bot.download_file(path)
                        src = '{}/src/web_admin_panel/static/tg_documents/photos/{}{}'.format(
                            os.getcwd(),
                            str(doc.file_id),
                            path[7:]
                        )
                        src_2 = '{}/src/web_personal_cabinet/static/tg_documents/photos/{}{}'.format(
                            os.getcwd(),
                            str(doc.file_id),
                            path[7:]
                        )

                        with open(src, 'wb') as new_file:
                            new_file.write(image)

                        with open(src_2, 'wb') as new_file_2:
                            new_file_2.write(image)

                        question = Question()
                        gmt = self.Zone(3, False, 'GMT')
                        date = datetime.datetime.now(gmt)
                        question.date = date
                        question.content_type = 'photo'
                        question.image_path = 'tg_documents/photos/' + str(doc.file_id) + path[7:]
                        if message.caption:
                            question.text = message.caption
                        question.feedback = feedback
                        question.save()

                        feedback.is_new_question_exist = True
                        feedback.save()

    @staticmethod
    def locale_text(lang, tag):
        if not lang or not tag:
            return None

        text = Text.objects(tag=tag).first()

        if not text:
            return None

        return text.values.get(lang)

    @staticmethod
    def local_field_name(lang, field):
        if not lang or not field:
            return None

        text = field.names.get(lang)

        if not text:
            return None

        return text

    @staticmethod
    def user_clear(user: User):
        user.auth_login = None
        user.auth_password = None
        user.is_recover = False
        user.is_in_settings = False
        user.change_address = False
        user.change_phone = False
        user.is_search = False
        # user.from_cabinet = False
        user.low_price = False
        user.save()

    @staticmethod
    def user_bool_clear(user: User):
        user.is_in_settings = False
        user.change_address = False
        user.change_phone = False
        user.is_search = False
        user.from_cabinet = False
        user.low_price = False
        user.save()

    # check is correct (after buy function in shop)
    @staticmethod
    def distribute_percents(reg_user: UserRegister, bot, structure_user=None, text=None):
        core = Core.objects.first()
        distribute_user_percents = 0
        core.bot_balance += reg_user.number_to_distribute * core.bot_comission
        core.save()
        if reg_user.is_main_structure:
            if reg_user.parent:
                parent: UserRegister = reg_user.parent
                parent.balance += reg_user.number_to_distribute * core.parent_comission
                parent.earned_sum += reg_user.number_to_distribute * core.parent_comission
                parent.save()
            else:
                core.bot_balance += reg_user.number_to_distribute * core.parent_comission
                core.save()

            reg_user.number_to_distribute = reg_user.number_to_distribute - \
                                            reg_user.number_to_distribute*(core.parent_comission+core.bot_comission)
            reg_user.save()
            # parent_user = user
            if len(referrals_indent.find_structure_parents_ids(structure_user)) != 0:
                for parent in referrals_indent.find_structure_parents_ids(structure_user):
                    distribute_user_percents += parent.percent

                distribute_user_percents += structure_user.percent
                x = float(reg_user.number_to_distribute/distribute_user_percents)

                for structure_parent in referrals_indent.find_structure_parents_ids(structure_user):
                    parent_user = structure_parent.user
                    parent_user.balance += x*structure_parent.percent
                    parent_user.earned_sum += x*structure_parent.percent
                    parent_user.save()
                    user: User = User.objects(auth_login=parent_user.login).first()
                    if user:
                        bot.send_message(user.user_id, text.format(
                            x*structure_parent.percent, reg_user.login, structure_parent.structure.fields.get('name')
                        ))

                reg_user.balance += x*structure_user.percent
                reg_user.earned_sum += x*structure_user.percent
                reg_user.save()

                user: User = User.objects(auth_login=reg_user.login).first()

                bot.send_message(user.user_id, text.format(
                    x * structure_user.percent, reg_user.login, structure_user.structure.fields.get('name')
                ))

            else:
                reg_user.balance += reg_user.number_to_distribute
                reg_user.earned_sum += reg_user.number_to_distribute
                reg_user.save()

            reg_user.number_to_distribute = 0
            reg_user.save()

        else:
            reg_user.number_to_distribute = reg_user.number_to_distribute - \
                                            reg_user.number_to_distribute*core.bot_comission
            reg_user.save()
            if len(referrals_indent.find_parents_ids(reg_user)) != 0:

                for parent_id in referrals_indent.find_parents_ids(reg_user):
                    parent_user: UserRegister = UserRegister.objects(id=parent_id).first()
                    distribute_user_percents += parent_user.percent

                x = float(reg_user.number_to_distribute / distribute_user_percents)

                for parent_id in referrals_indent.find_parents_ids(reg_user):
                    parent_user: UserRegister = UserRegister.objects(id=parent_id).first()
                    # if parent_user.parent_referrals_user_id:
                    # parent_user = User.objects(user_id=parent_user.parent_referrals_user_id).first()
                    parent_user.balance += x * parent_user.percent
                    parent_user.earned_sum += x * parent_user.percent
                    parent_user.structure_earned_sum += x * parent_user.percent
                    parent_user.save()
                    users: User = User.objects(auth_login=parent_user.login)
                    for user in users:
                        try:
                            if user.is_authed:
                                msg_to_del = bot.send_message(user.user_id,
                                                              keyboards.locale_text(user.user_lang,
                                                                                    'destributed_cash').format(parent_user.login,
                                                                                                               x * parent_user.percent))
                                user.msgs_to_del.append(msg_to_del.message_id)
                                user.save()
                        except Exception as e:
                            print(e)

            else:
                reg_user.balance += reg_user.number_to_distribute
                reg_user.earned_sum += reg_user.number_to_distribute
                reg_user.structure_earned_sum += reg_user.number_to_distribute
                reg_user.save()


    @staticmethod
    def secret_generator(size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    # ???
    @staticmethod
    def user_unlock(user):
        time.sleep(900)
        user.password_three_wrong = False
        user.save()


    @staticmethod
    def search_in_categories(str_to_find: str, categories):
        str_to_find = str_to_find.lower()
        result = list()
        for category in categories:
            for lang in category.values:
                if category.values.get(lang).lower().find(str_to_find) != -1:
                    result.append(category)
                    break
        return result

    @staticmethod
    def search_in_products(str_to_find: str, products):
        str_to_find = str_to_find.lower()
        result = list()
        for product in products:
            for field in product.fields:
                if product.fields.get(field).lower().find(str_to_find) != -1:
                    result.append(product)
                    break
        return result

    @staticmethod
    def auth_check(reg_user, go_state, msg, user_clear, user):
        if not reg_user:
            user_clear(user)
            go_state(msg, 'auth_state')

    # fix for multi-languages using core for defaults parameters
    @staticmethod
    def create_default_fields(reg_user, locale_text):
        counter = 1
        for field in config.DEFAULT_FIELDS_TAG:
            counter += 1
            new_field = Field()
            new_field.user = reg_user
            new_field.field_tag = field
            new_field.is_required = True

            for lang in Language.objects:
                new_field.names[lang.tag] = locale_text(lang.tag, field)
                new_field.message[lang.tag] = locale_text(lang.tag, field + '_msg')

            new_field.priority = counter

            new_field.save()

        photo = Photo()
        photo.user = reg_user
        photo.field_tag = 'photo'
        for lang in Language.objects:
            photo.names[lang.tag] = locale_text(lang.tag, 'photo')

        photo.save()

    @staticmethod
    def buy_good_take_place(structure, reg_user):
        """ Method pushed reg user in good structure """
        structure_user = ProductStructureUser.objects(Q(user=reg_user) & Q(structure=structure)).first()
        if structure_user:
            pass
        else:
            structure_user: ProductStructureUser = ProductStructureUser()
            structure_user.user = reg_user
            structure_user.structure = structure
            structure_user.save()
            i = 1
            while True:
                us: ProductStructureUser = ProductStructureUser.objects(Q(positional_id=i)
                                                                        & Q(structure=structure)).first()
                if us:
                    i += 1
                else:
                    structure_user.positional_id = i
                    structure_user.save()
                    parent_positional_id = structure_user.positional_id // 2
                    parent: structure = ProductStructureUser.objects(Q(positional_id=parent_positional_id)
                                                                     & Q(structure=structure)).first()
                    if parent:
                        if structure_user.user != parent:
                            structure_user.parent = parent
                            structure_user.save()
                            if structure_user.positional_id % 2 == 0:
                                parent.left_referrals_branch = structure_user
                                parent.save()
                            else:
                                parent.right_referrals_branch = structure_user
                                parent.save()
                    lvl = len(referrals_indent.find_structure_parents_ids(structure_user))
                    if lvl < 1:
                        structure_user.percent = 1.99
                        structure_user.level = lvl + 1
                        structure_user.save()
                    else:
                        structure_user.percent = (1 / lvl) * 2 - 0.01
                        structure_user.level = lvl + 1
                        structure_user.save()
                    break

            structure.update(push__structure_users=structure_user)
            structure.reload()

        return structure_user

    @staticmethod
    def delete_msgs(bot, user):
        for msg_to_del in user.msgs_to_del:
            try:
                #     if msg_to_del == user.txt_msg_to_edit:
                #         pass
                #     else:
                bot.delete_message(user.user_id, msg_to_del)
            except Exception as e:
                pass
        user.msgs_to_del = list()
        user.save()

    @staticmethod
    def save_keyboard(bot, keyboard, user, delete_msgs=None):
        msg = bot.send_message(user.user_id, '...', reply_markup=keyboard, parse_mode='markdown')
        if delete_msgs:
            delete_msgs(bot, user)
        user.msgs_to_del.append(msg.message_id)
        # user.txt_msg_to_edit = msg.message_id
        user.save()
        # print(user.msgs_to_del)

    class Zone(tzinfo):
        def __init__(self, offset, isdst, name):
            self.offset = offset
            self.isdst = isdst
            self.name = name

        def utcoffset(self, dt):
            return timedelta(hours=self.offset) + self.dst(dt)

        def dst(self, dt):
            return timedelta(hours=1) if self.isdst else timedelta(0)

        def tzname(self, dt):
            return self.name

    @staticmethod
    def balance_format(user, reg_user, lang, locale_text, bot):
        # input_sum, balance_sum, earned_sum, goods_structures_earned_sum, structure_earned_sum

        text = str()

        text += locale_text(lang, 'balance_sum').format('%.2f' % reg_user.balance) + '\n'
        text += locale_text(lang, 'input_sum').format('%.2f' % reg_user.input_sum) + '\n'
        text += locale_text(lang, 'output_sum').format('%.2f' % reg_user.input_sum) + '\n'
        text += locale_text(lang, 'earned_sum').format('%.2f' % reg_user.earned_sum) + '\n'
        text += locale_text(lang, 'structure_earned_sum').format('%.2f' % reg_user.structure_earned_sum) + '\n'

        if reg_user.my_goods_earned_sum:
            text += locale_text(lang, 'my_goods_earned_sum') + '\n'

            for good_id in reg_user.my_goods_earned_sum:
                good: Product = Product.objects(id=good_id).first()
                name = good.fields.get('name')
                good_str = '    {0}: {1}'.format(name, '%.2f' % reg_user.my_goods_earned_sum.get(good_id))
                text += good_str + '\n'

                if len(text) >= 3500:
                    msg_to_del = bot.send_message(user.user_id, text, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                    text = str()

        if reg_user.goods_structures_earned_sum:
            text += locale_text(lang, 'goods_structures_earned_sum') + '\n'

            for good_id in reg_user.goods_structures_earned_sum:
                good: Product = Product.objects(id=good_id).first()
                name = good.fields.get('name')
                good_str = '    {0}: {1}'.format(name, '%.2f' % reg_user.goods_structures_earned_sum.get(good_id))
                text += good_str + '\n'

                if len(text) >= 3500:
                    msg_to_del = bot.send_message(user.user_id, text, parse_mode='markdown')
                    user.msgs_to_del.append(msg_to_del.message_id)
                    user.save()
                    text = str()

        return text

    @staticmethod
    def structure_info_format_format(user, reg_user, lang, locale_text, bot):
        text = str()
        if reg_user.parent:

            l_users_tgs = User.objects(auth_login=reg_user.parent.login)
            print(l_users_tgs)
            txt = str()
            if l_users_tgs:
                for tg in l_users_tgs:
                    if tg.username and not tg.username == 'None':
                        link = 't.me/{0}'.format(str(tg.username).replace('_', '\_')) + '\n'
                        txt += link
                    else:
                        link = locale_text(lang, 'link_msg').format(tg.user_id) + '\n'
                        txt += link

            parent = locale_text(lang, 'structure_data_msg').format(reg_user.positional_id,
                                                                    reg_user.level, txt) + '\n'

        else:
            parent = locale_text(lang, 'structure_data_msg').format(reg_user.positional_id, reg_user.level,
                                                                    locale_text(lang, 'does_not_exist_msg')) + '\n'

        text += parent
        if reg_user.referral_link[7:]:
            invite = UserRegister.objects(id=reg_user.referral_link[7:]).first()
            l_users_tgs = User.objects(auth_login=invite.login)

            txt = str()
            if l_users_tgs:
                for tg in l_users_tgs:
                    if tg.username:
                        link = 't.me/{0}'.format(str(tg.username).replace('_', '\_')) + '\n'
                        txt += link
                    else:
                        link = locale_text(lang, 'link_msg').format(tg.user_id) + '\n'
                        txt += link

            text += locale_text(lang, 'invite').format(txt) if txt \
                else locale_text(lang, 'invite').format(locale_text(lang, 'does_not_exist_msg'))

        # text += locale_text(lang, 'my_structure').format(reg_user.id)

        return text

    @staticmethod
    def categories_validate(categories):
        result: list = list()
        for cat in categories:
            if cat.goods_num > 0:
                result.append(cat)
        return result

    @staticmethod
    def format_line_information(reg_user, deep):
        # for i in range(deep):
        pass