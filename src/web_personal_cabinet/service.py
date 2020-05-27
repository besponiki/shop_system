import hashlib
import random
import time
import datetime
import phonenumbers

from math import ceil
from phonenumbers import carrier
from phonenumbers.phonenumberutil import number_type
from flask import Flask, render_template, request, make_response, redirect
from flask_bootstrap import Bootstrap
from flask_mongoengine import MongoEngine
from mongoengine.queryset.visitor import Q

from .. import config

from datetime import timedelta, tzinfo
from ..core.db_model.structure import ProductHistory, Product
from ..tg_bot import keyboards
from ..core.db_model.structure import ProductStructureUser
from ..binary_referral_system import referrals_indent
from ..core.db_model.core import Core

from ..tg_bot.db_model.user_register import UserRegister as User
from ..tg_bot.db_model.user import User as TgUser

from ..core.db_model.category import Category
from ..core.db_model.order import Order
from ..core.db_model.field import Field
from ..core.db_model.text.language import Language
from telebot import TeleBot
from ..config import BOT_TOKEN
from ..tg_bot.keyboards import locale_text
from shutil import copyfile
import os
from ..core.db_model.feedback import Feedback, Answer, Question
from ..core.db_model.text.text import Text
from werkzeug.utils import secure_filename
# from ..tg_bot.db_model.user_register import UserRegister

bot = TeleBot(BOT_TOKEN)

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = config.PROJECT_NAME

app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

app.config['MONGODB_SETTINGS'] = {
    'db': config.PROJECT_NAME,
    'alias':  'default'
}


Bootstrap(app=app)
MongoEngine(app=app)
NavbarTextsTags = ('my_profile', 'categories', 'fields', 'menu_new_order', 'menu_in_work_order',
                   'menu_done_orders', 'menu_cancel_orders', 'my_goods_lk', 'feedback', 'graph')
IndexTextsTags = ('my_profile', 'save', 'old_password', 'login', 'new_password', 'addres', 'order_phone')
CategoriesTextsTags = ('add_new_category', 'categories', 'tag', 'text', 'parent_category', 'message', 'add_subcategory',
                       'subcategories', 'edit', 'delete', 'back', 'next', 'pages', 'yes', 'no', 'is_moderated', 'passed_moderation_msg')
FieldsTextsTags = ('fields', 'add_new_field', 'tag', 'value_lang', 'edit', 'delete', 'pages', 'back', 'next',
                   'moderation', 'passed_moderation_msg', 'no_moderation', 'add')
CategoryTextsTags = ('category', 'general_info', 'parent_category', 'tag', 'text', 'message', 'save', 'name', 'nothing_to_do',
                     'nothing')
FieldTextsTags = ('field', 'tag', 'general_info', 'value', 'save')
OrderTextsTags = ('order_good', 'order_price', 'order_user', 'order_id', 'order_status', 'order_adress', 'order_date',
                  'order_phone', 'add_to_work_order', 'add_to_cancel_order', 'add_to_done_order')
MyGoodsTextsTags = ('my_goods_lk', 'back', 'next')
NewProductTextsTags = ()
DialogTextsTags = ('message', 'img', 'send', 'answer', 'dialogue_history_with', 'admin_answer')


def get_pages_text(lang, tags):
    result: dict = dict()
    for tag in tags:
        result[tag] = locale_text(lang, tag)

    return result


@app.route('/', methods=['GET', 'POST'])
def index():
    result = make_response(redirect('/login'))
    # core: Core = Core.objects.first()
    # core.positional_id = 58572
    # core.save()
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        langs = Language.objects
        if not user:
            return None

        if request.method == 'POST':
            lang = request.form.get('lang')
            if lang:
                user.partner_pannel_lang = lang

            login = str(request.form.get('login')).lower()
            if login:
                user.login = login

            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')
            if new_password and old_password and old_password == user.password:
                user.password = new_password
            elif not old_password:
                error = locale_text(user.partner_pannel_lang, 'enter_old_pw_msg_error')
                return make_response(render_template(template_name_or_list='index.html', langs=langs, user=user,
                                 navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                 index=get_pages_text(user.partner_pannel_lang, IndexTextsTags),
                                                     error=error))
            elif old_password != user.password:
                error = locale_text(user.partner_pannel_lang, ' Incorrect_pw_error_msg')
                return make_response(render_template(template_name_or_list='index.html', langs=langs, user=user,
                                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                                     index=get_pages_text(user.partner_pannel_lang, IndexTextsTags),
                                                     error=error))

            phone = request.form.get('phone')
            if phone:
                number = phone
                try:
                    if carrier._is_mobile(number_type(phonenumbers.parse(number))):
                        user.phone = number
                    else:
                        error = locale_text(user.partner_pannel_lang, 'phone_validation_lk_error_msg')
                        return make_response(render_template(template_name_or_list='index.html', langs=langs, user=user,
                                                             navbar=get_pages_text(user.partner_pannel_lang,
                                                                                   NavbarTextsTags),
                                                             index=get_pages_text(user.partner_pannel_lang,
                                                                                  IndexTextsTags),
                                                             error=error))
                except phonenumbers.NumberParseException:
                    error = locale_text(user.partner_pannel_lang, 'phone_validation_lk_error_msg')
                    return make_response(render_template(template_name_or_list='index.html', langs=langs, user=user,
                                                         navbar=get_pages_text(user.partner_pannel_lang,
                                                                               NavbarTextsTags),
                                                         index=get_pages_text(user.partner_pannel_lang, IndexTextsTags),
                                                         error=error))


            address = request.form.get('address')
            if address:
                user.address = address

            user.save()

        result = render_template(template_name_or_list='index.html', langs=langs, user=user,
                                 navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                 index=get_pages_text(user.partner_pannel_lang, IndexTextsTags))

    return result


@app.route('/login', methods=['GET', 'POST'])
def login():
    result = make_response(render_template('login.html'))
    if request.method == 'POST':
        user_login = str(request.form['login']).lower()
        password = request.form['password']

        user = User.objects(login=user_login).first()

        if user and user.password == password:
            hash_str = (user_login + password + str(random.randrange(111, 999))).encode('utf-8')
            hashed_pass = hashlib.md5(hash_str).hexdigest()
            session_id = hashed_pass
            time_alive = time.time() + (86400 * 7)

            user.session_id = session_id
            user.time_alive = time_alive
            user.save()

            result = make_response(redirect('/'))
            result.set_cookie('personal_shop_cabinet_session_id', session_id)
        else:
            error = locale_text('rus', 'login_error')
            error += '\n'+locale_text('eng', 'login_error')
            result = make_response(render_template('login.html', error=error))
    else:
        if auth_check():
            result = make_response(redirect('/'))

    return result


@app.route('/logout')
def logout():
    result = make_response(redirect('login'))

    session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
    if session_id:
        result.set_cookie('personal_shop_cabinet_session_id', 'deleted', expires=time.time()-100)

    return result


def auth_check():
    result = False

    session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
    if session_id:
        user = User.objects(session_id=session_id).first()
        if user:
            result = True

    return result


@app.route('/new_orders', methods=['GET', 'POST'])
def new_orders_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            order_len = Order.objects(Q(sailer=user) & Q(is_accept=False) & Q(is_cancel=False) & Q(is_done=False)).count()

            p_all = ceil(order_len / 20) if ceil(order_len / 20) != 0 else 1

            if start > order_len:
                start = order_len

            if end > order_len:
                end = order_len

            orders = Order.objects(Q(sailer=user) & Q(is_accept=False) & Q(is_cancel=False) & Q(is_done=False))[start:end]

            tgs_dict: dict = dict()
            for i in orders:
                reg = i.user
                if reg.is_registered:
                    tgs = TgUser.objects(auth_login=reg.login)
                else:
                    tgs = TgUser.objects(defaul_unregister_user=reg)
                txt: list = list()

                for j in tgs:
                    if j.username and not j.username == 'None':
                        link = 't.me/{0}'.format(str(j.username))
                        txt.append(link)
                    else:
                        link = locale_text(user.partner_pannel_lang, 'link_msg_lk').format(j.user_id)
                        txt.append(link)

                tgs_dict[i.id] = txt

                # text_2 += txt if len(text_2) == 0 else ', {0}'.format(txt)

            result = render_template(template_name_or_list='new_orders.html', p=page, rows=orders, p_all=p_all,
                                     u_all=order_len, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, OrderTextsTags), tgs=tgs_dict,
                                     user=user)

    return result


from ..binary_referral_system.referrals_indent import graph_data
@app.route('/graph', methods=['GET', 'POST'])
def graph_method():
    session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
    user_id = request.args.get('id')
    if user_id:
        user = User.objects(id=user_id).first()
    else:
        user = User.objects(session_id=session_id).first()
    data = graph_data(user, admin_panel=False)
    children_count = str(data).count("children")
    result = render_template(template_name_or_list='graph.html',  data=data, children_count=children_count,
                             navbar=get_pages_text(user.partner_pannel_lang,
                                                   NavbarTextsTags)
                             )
    return result


@app.route('/in_work_orders', methods=['GET', 'POST'])
def in_work_orders_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            order_len = Order.objects(Q(sailer=user) & Q(is_accept=True) & Q(is_cancel=False) & Q(is_done=False)).count()

            p_all = ceil(order_len / 20) if ceil(order_len / 20) != 0 else 1

            if start > order_len:
                start = order_len

            if end > order_len:
                end = order_len

            orders = Order.objects(Q(sailer=user) & Q(is_accept=True) & Q(is_cancel=False) & Q(is_done=False))[start:end]

            tgs_dict: dict = dict()
            for i in orders:
                reg = i.user
                tgs = TgUser.objects(auth_login=reg.login)
                txt: list = list()

                for j in tgs:
                    if j.username and not j.username == 'None':
                        link = 't.me/{0}'.format(str(j.username))
                        txt.append(link)
                    else:
                        link = locale_text(user.partner_pannel_lang, 'link_msg_lk').format(j.user_id)
                        txt.append(link)

                tgs_dict[i.id] = txt

            result = render_template(template_name_or_list='in_work_orders.html', p=page, rows=orders, p_all=p_all,
                                     u_all=order_len, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, OrderTextsTags), tgs=tgs_dict,
                                     user=user)

    return result


@app.route('/done_orders', methods=['GET', 'POST'])
def done_orders_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            order_len = Order.objects(Q(sailer=user) & Q(is_accept=False) & Q(is_cancel=False) & Q(is_done=True)).count()

            p_all = ceil(order_len / 20) if ceil(order_len / 20) != 0 else 1

            if start > order_len:
                start = order_len

            if end > order_len:
                end = order_len

            orders = Order.objects(Q(sailer=user) & Q(is_accept=False) & Q(is_cancel=False) & Q(is_done=True))[start:end]

            tgs_dict: dict = dict()
            for i in orders:
                reg = i.user
                tgs = TgUser.objects(auth_login=reg.login)
                txt: list = list()

                for j in tgs:
                    if j.username and not j.username == 'None':
                        link = 't.me/{0}'.format(str(j.username))
                        txt.append(link)
                    else:
                        link = locale_text(user.partner_pannel_lang, 'link_msg_lk').format(j.user_id)
                        txt.append(link)

                tgs_dict[i.id] = txt

            result = render_template(template_name_or_list='done_orders.html', p=page, rows=orders, p_all=p_all,
                                     u_all=order_len, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, OrderTextsTags), tgs=tgs_dict,
                                     user=user)

    return result


@app.route('/cancel_orders', methods=['GET', 'POST'])
def cancel_orders_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            order_len = Order.objects(Q(user=user) & Q(is_accept=False) & Q(is_cancel=True) & Q(is_done=False)).count()

            p_all = ceil(order_len / 20) if ceil(order_len / 20) != 0 else 1

            if start > order_len:
                start = order_len

            if end > order_len:
                end = order_len

            orders = Order.objects(Q(user=user) & Q(is_accept=False) & Q(is_cancel=True) & Q(is_done=False))[start:end]

            tgs_dict: dict = dict()
            for i in orders:
                reg = i.user
                tgs = TgUser.objects(auth_login=reg.login)
                txt: str = str()

                for j in tgs:
                    if j.username and not j.username == 'None':
                        link = 't.me/{0}'.format(str(j.username))
                        txt += link if len(txt) == 0 else ', {0}'.format(link)
                    else:
                        link = locale_text(user.partner_pannel_lang, 'link_msg_lk').format(j.user_id)
                        txt += link if len(txt) == 0 else ', {0}'.format(link)

                tgs_dict[i.id] = txt

            result = render_template(template_name_or_list='cancel_orders.html', p=page, rows=orders, p_all=p_all,
                                     u_all=order_len, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, OrderTextsTags), tgs=tgs_dict,
                                     user=user)

    return result


@app.route('/done_add/<string:order_id>', methods=['GET', 'POST'])
def done_add(order_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/in_work_orders'))

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not order_id:
            return result

        target_order: Order = Order.objects(id=order_id).first()

        if target_order:
            target_order.is_accept = False
            target_order.is_done = True
            target_order.status = Text.objects(tag='done_status').first().values
            target_order.save()

            good = target_order.good
            reg_user = target_order.user

            user.balance += (float(good.fields.get('price')) - float(good.fields.get('reward'))) * target_order.counter
            user.earned_sum += (float(good.fields.get('price')) - float(good.fields.get('reward'))) * target_order.counter
            if user.my_goods_earned_sum.get(str(good.id)):
                user.my_goods_earned_sum[str(good.id)] += (float(good.fields.get('price')) - float(good.fields.get('reward'))) * target_order.counter
            else:
                user.my_goods_earned_sum[str(good.id)] = (float(good.fields.get('price')) - float(good.fields.get('reward'))) * target_order.counter
            user.save()

            result = make_response(redirect('/in_work_orders'))

            # user_lang = TgUser.objects(auth_login=reg_user.login).first().user_lang
            sum = float(good.fields.get('reward')) * target_order.counter
            # reg_user.save()
            # text = locale_text(user_lang, 'destribute_msg')
            structure_user: ProductStructureUser = buy_good_take_place(good, reg_user)
            data = structure_user.univers_distribute_trading_pack(sum)
            if data:
                for par in data:
                    parent = User.objects(id=par).first()
                    if parent:
                        tgs = User.objects(auth_login=parent.login)
                        for tg in tgs:
                            msg_to_del = bot.send_message(tg.user_id, Text.objects(tag='destributed_cash').first().\
                                                                        values.get(tg.user_lang).format(parent.login, data[par]))
                            tg.msgs_to_del.append(msg_to_del.message_id)
                            tg.save()
            # distribute_percents(reg_user, bot, structure_user, text=text)

            good_history = ProductHistory()
            good_history.user = reg_user
            good_history.good = good
            good_history.structure_user = structure_user
            date = datetime.datetime.now(Zone(3, False, 'GMT'))
            good_history.date = date
            good_history.save()

            # else:
            #     distribute_percents(reg_user, bot, text=text, structure=good)
            #     good_history = ProductHistory()
            #     good_history.user = reg_user
            #     good_history.good = good
            #     date = datetime.datetime.now(Zone(3, False, 'GMT'))
            #     good_history.date = date
            #     good_history.save()

    return result


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


@app.route('/in_work_add/<string:order_id>', methods=['GET', 'POST'])
def in_work_add(order_id):
    result = make_response(redirect('/new_orders'))

    if not order_id:
        return result

    target_order = Order.objects(id=order_id).first()

    if target_order:
        target_order.is_accept = True
        target_order.status = Text.objects(tag='in_work_status').first().values
        target_order.save()
        result = make_response(redirect('/new_orders'))

    return result


@app.route('/cancel_add/<string:order_id>', methods=['GET', 'POST'])
def cancel_add(order_id):
    result = make_response(redirect('/new_orders'))

    if not order_id:
        return result

    target_order = Order.objects(id=order_id).first()
    user = target_order.user
    user.balance += target_order.sum
    user.save()

    if target_order:
        target_order.is_cancel = True
        target_order.status = Text.objects(tag='cancel_status').first().values
        target_order.save()
        result = make_response(redirect('/new_orders'))

    return result


# @app.route('/my_good/view/<string:good_id>', methods=['GET', 'POST'])
# def view_good_method(good_id):
#     result = make_response(redirect('/login'))
#     if auth_check():
#         session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
#         user = User.objects(session_id=session_id).first()
#
#         if request.method == 'POST':
#             pass
#         else:
#             result = make_response(render_template(template_name_or_list='view_good.html'))
#
#     return result


@app.route('/my_goods', methods=['GET', 'POST'])
def my_goods():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        languages = Language.objects
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        if not user:
            return None
        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            order_len = Product.objects(Q(creator=user) & Q(is_active=True)).count()

            p_all = ceil(order_len / 20) if ceil(order_len / 20) != 0 else 1

            if start > order_len:
                start = order_len

            if end > order_len:
                end = order_len

            my_goods: Product = Product.objects(creator=user)[start:end]
            fields: Field = Field.objects(Q(user=user) & Q(is_moderated=True) & Q(in_active=True))
            result = render_template(template_name_or_list='my_goods.html',
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, MyGoodsTextsTags),
                                     languages=languages, rows=my_goods,
                                     p=page, p_all=p_all, fields=fields, user=user)
    return result


# todo choosed category and images
@app.route('/new_product', methods=['GET', 'POST'])
def new_product():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        languages = Language.objects
        fields: Field = Field.objects(Q(user=user) & Q(is_moderated=True)).order_by('priority')
        categories = Category.objects(is_moderated=True)

        if not user:
            return None

        if request.method == 'POST':
            new_prod = Product()
            for field in fields:
                tag = request.form.get(field.field_tag)
                if not tag and field.is_required:
                    error = str(locale_text(user.partner_pannel_lang, 'bad_enter_error_msg'))+\
                            ' {0}'.format(field.names.get(user.partner_pannel_lang))
                    return make_response(render_template(template_name_or_list='my_good.html', languages=languages,
                                                         navbar=get_pages_text(user.partner_pannel_lang,
                                                                               NavbarTextsTags),
                                                         texts=get_pages_text(user.partner_pannel_lang,
                                                                              NewProductTextsTags),
                                                         fields=fields, user=user, error=error,
                                                         categories=categories))
                else:
                    if field.field_tag == 'reward' or field.field_tag == 'price':
                        try:
                            price = float(tag)
                            if price > 0:
                                new_prod.fields[field.field_tag] = tag
                            else:

                                error = locale_text(user.partner_pannel_lang, 'negative_price_warning')
                                return make_response(
                                    render_template(template_name_or_list='my_good.html', languages=languages,
                                                    navbar=get_pages_text(user.partner_pannel_lang,
                                                                          NavbarTextsTags),
                                                    texts=get_pages_text(user.partner_pannel_lang,
                                                                         NewProductTextsTags),
                                                    fields=fields, user=user, error=error,
                                                    categories=categories))
                        except ValueError:
                            error = locale_text(user.partner_pannel_lang, 'enter_num_error_msg')
                            return make_response(
                                render_template(template_name_or_list='my_good.html', languages=languages,
                                                navbar=get_pages_text(user.partner_pannel_lang,
                                                                      NavbarTextsTags),
                                                texts=get_pages_text(user.partner_pannel_lang,
                                                                     NewProductTextsTags),
                                                fields=fields, user=user, error=error,
                                                categories=categories))
                    else:
                        new_prod.fields[field.field_tag] = tag

            if float(new_prod.fields.get('reward')) >= float(new_prod.fields.get('price')):
                error = locale_text(user.partner_pannel_lang, 'bad_reward_error_msg')
                return make_response(
                    render_template(template_name_or_list='my_good.html', languages=languages,
                                    navbar=get_pages_text(user.partner_pannel_lang,
                                                          NavbarTextsTags),
                                    texts=get_pages_text(user.partner_pannel_lang,
                                                         NewProductTextsTags),
                                    fields=fields, user=user, error=error,
                                    categories=categories))

            category = request.form.get('category')
            if category:
                category = Category.objects(id=category).first()

                new_prod.category = category
            else:
                error = locale_text(user.partner_pannel_lang, 'choose_category_error_msg')
                return make_response(render_template(template_name_or_list='my_good.html', languages=languages,
                                                     navbar=get_pages_text(user.partner_pannel_lang,
                                                                           NavbarTextsTags),
                                                     texts=get_pages_text(user.partner_pannel_lang,
                                                                          NewProductTextsTags),
                                                     fields=fields, user=user, error=error,
                                                     categories=categories))

            images = request.files.getlist('image')
            print(images)
            if len(images) != 0:
                for image in images:
                    filename = secure_filename(image.filename)
                    # name, formatt = filename.split('.')
                    if filename:
                        src = '{0}/src/web_admin_panel/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)
                        src_2 = '{0}/src/web_personal_cabinet/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)

                        with open(src, 'wb') as f:
                            f.write(image.read())
                            f.close()

                        copyfile(src, src_2)

                        new_prod.images.append('tg_documents/photos/{0}'.format(filename))

            new_prod.creator = user
            new_prod.save()

            result = make_response(redirect('/my_goods'))

        else:
            result = render_template(template_name_or_list='my_good.html', languages=languages,
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, NewProductTextsTags),
                                     fields=fields, user=user, categories=categories)

    return result


@app.route('/my_good/del/<string:good_id>', methods=['GET', 'POST'])
def del_good_method(good_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        if not user:
            return None

        good: Product = Product.objects(id=good_id).first()

        if good:

            category = good.category
            while category:
                category.goods_num -= 1
                category.save()
                category = category.parent_category

            good.is_active = False
            good.save()
        else:
            return None

        result = make_response(redirect('/my_goods'))

    return result


@app.route('/my_good/view/<string:good_id>', methods=['GET', 'POST'])
def view_good_method(good_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        fields: Field = Field.objects(user=user).order_by('priority')
        categories = Category.objects(is_moderated=True)
        languages = Language.objects

        if not user:
            return None

        good: Product = Product.objects(id=good_id).first()

        if not good:
            return None

        if request.method == 'POST':
            pass
        else:
            result = render_template(template_name_or_list='my_good.html', languages=languages,
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, NewProductTextsTags),
                                     fields=fields, user=user, categories=categories, target_good=good)

        # result = make_response(redirect('/my_goods'))

    return result


@app.route('/fields', methods=['GET', 'POST'])
def fields_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            # for f in Field.objects():
            #     f.in_active = True
            #     f.save()
            #     print('{0}: {1}'.format(f.id, f.in_active))

            end = page * 20
            start = end - 20
            fields_len = Field.objects(user=user).count()

            p_all = ceil(fields_len / 20) if ceil(fields_len / 20) != 0 else 1

            if start > fields_len:
                start = fields_len

            if end > fields_len:
                end = fields_len

            texts = Field.objects(user=user)[start:end]
            result = render_template(template_name_or_list='fields.html', p=page, rows=texts, p_all=p_all,
                                     u_all=fields_len, navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, FieldsTextsTags))

    return result


@app.route('/field/del/<string:field_id>', methods=['GET', 'POST'])
def del_field(field_id):
    result = make_response(redirect('/'))

    if not field_id:
        return result

    target_field = Field.objects(id=field_id).first()

    if target_field:
        target_field.in_active = False
        target_field.save()
        result = make_response(redirect('/fields'))

    return result


@app.route('/field/add/<string:field_id>', methods=['GET', 'POST'])
def add_field(field_id):
    result = make_response(redirect('/'))

    if not field_id:
        return result

    target_field = Field.objects(id=field_id).first()

    if target_field:
        target_field.in_active = True
        target_field.save()
        result = make_response(redirect('/fields'))

    return result


@app.route('/field', methods=['GET', 'POST'])
def field_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        languages = Language.objects

        if not user:
            return None

        if request.method == 'POST':
            new_field = Field()

            tag = request.form.get('tag')
            if tag:
                old_fields = Field.objects(Q(user=user) & Q(field_tag=tag)).first()
                if not old_fields:
                    new_field.field_tag = tag
                else:
                    old_fields.in_active = True
                    old_fields.save()
                    # error = locale_text(user.partner_pannel_lang, 'tag_not_unique_error')
                    # result = make_response(render_template('field.html', languages=languages, error=error,
                    #                                        navbar=get_pages_text(user.partner_pannel_lang,
                    #                                                              NavbarTextsTags),
                    #                                        texts=get_pages_text(user.partner_pannel_lang,
                    #                                                             FieldTextsTags)))
                    # return result
                    return make_response(redirect('/fields'))
            else:
                error = locale_text(user.partner_pannel_lang, 'tag_error')
                result = make_response(render_template('field.html', languages=languages, error=error,
                                                       navbar=get_pages_text(user.partner_pannel_lang,
                                                                             NavbarTextsTags),
                                                       texts=get_pages_text(user.partner_pannel_lang, FieldTextsTags)))
                return result

            for language in languages:
                value = request.form.get(language.tag + '_value')
                if value:
                    new_field.names[language.tag] = value
                else:
                    error = locale_text(user.partner_pannel_lang, 'lang_error') + language.name + '!'
                    result = make_response(render_template('field.html', languages=languages, error=error,
                                                           navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                                           texts=get_pages_text(user.partner_pannel_lang, FieldTextsTags
                                                                                )))
                    return result
            new_field.is_moderated = False
            new_field.user = user
            new_field.save()
            result = make_response(redirect('/fields'))
        else:
            result = render_template(template_name_or_list='field.html', languages=languages,
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, FieldTextsTags))

    return result


@app.route('/field/edit/<string:field_id>', methods=['GET', 'POST'])
def edit_field(field_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        result = make_response(redirect('/fields'))

        if not field_id:
            return result

        languages = Language.objects

        target_field = Field.objects(id=field_id).first()

        if not target_field:
            return None

        if request.method == 'POST':
            tag = request.form.get('tag')
            if tag:
                target_field.field_tag = tag
            else:
                error = locale_text(user.partner_pannel_lang, 'tag_error')
                result = make_response(render_template('field.html', target_text=target_field, languages=languages,
                                                       error=error, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                          NavbarTextsTags),
                                                       texts=get_pages_text(user.partner_pannel_lang, FieldTextsTags)))
                return result

            for language in languages:
                value = request.form.get(language.tag + '_value')
                if value:
                    target_field.names[language.tag] = value
                else:
                    error = locale_text(user.partner_pannel_lang, 'lang_error') + language.name + '!'
                    result = make_response(render_template('field.html', target_text=target_field, languages=languages,
                                                           error=error, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                              NavbarTextsTags),
                                                           texts=get_pages_text(user.partner_pannel_lang, FieldTextsTags)))
                    return result
            target_field.save()
            result = make_response(redirect('/fields'))
        else:
            result = render_template(template_name_or_list='field.html',
                                     target_text=target_field,
                                     languages=languages,
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, FieldTextsTags))

    return result


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
        if reg_user.structure_referrals.get(str(structure.id)):
            parent_reg_user = User.objects(id=reg_user.structure_referrals.get(str(structure.id))).first()

            if parent_reg_user != reg_user:
                try:
                    parent_structure = ProductStructureUser.objects(Q(user=parent_reg_user) & Q(structure=structure)).first()
                    if parent_structure:
                        structure_user.referral_parent = parent_structure
                        structure_user.save()
                        parent_l = parent_structure
                        parent_r = parent_structure
                        i = 0
                        while True:
                            if i % 2 == 0:
                                if parent_l.left_referrals_branch:
                                    parent_l: User = parent_l.left_referrals_branch
                                else:
                                    parent_l.left_referrals_branch = structure_user
                                    parent_l.save()
                                    structure_user.parent = parent_l
                                    structure_user.positional_id = parent_l.positional_id * 2
                                    lvl = parent_l.level
                                    if lvl < 1:
                                        structure_user.percent = 1.99
                                        structure_user.level = lvl
                                        structure_user.save()
                                    else:
                                        structure_user.percent = (1 / lvl) * 2 - 0.01
                                        structure_user.level = lvl + 1
                                        structure_user.save()
                                    break
                            elif i % 2 == 1:
                                if parent_r.right_referrals_branch:
                                    parent_r: User = parent_r.right_referrals_branch
                                else:
                                    parent_r.right_referrals_branch = structure_user
                                    parent_r.save()
                                    structure_user.parent = parent_r
                                    structure_user.positional_id = parent_r.positional_id * 2 + 1
                                    lvl = parent_r.level
                                    if lvl < 1:
                                        structure_user.percent = 1.99
                                        structure_user.level = lvl
                                        structure_user.save()
                                    else:
                                        structure_user.percent = 2 / lvl - 0.01
                                        structure_user.level = lvl + 1
                                        structure_user.save()
                                    break
                            i += 1
                        return structure_user
                    else:
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
                except Exception as e:
                    print(e)
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


def distribute_percents(reg_user: User, bot, structure_user=None, text=None, structure=None):
    core = Core.objects.first()
    distribute_user_percents = 0
    bot_comisssion = reg_user.number_to_distribute * core.bot_comission
    core.bot_balance += bot_comisssion
    core.save()
    text_2 = 'Комиссия бота: {0}\n\n'.format('%.2f' % bot_comisssion)
    if structure_user:
        if reg_user.referral_parent:
            parent: User = reg_user.referral_parent
            parent.balance += reg_user.number_to_distribute * core.parent_comission
            parent.earned_sum += reg_user.number_to_distribute * core.parent_comission
            parent.save()
            num = reg_user.number_to_distribute * core.parent_comission
            text_2 += 'Parents comission: {0}\n\n'.format('%.2f' % num)
        elif reg_user.parent:
            parent: User = reg_user.parent
            parent.balance += reg_user.number_to_distribute * core.parent_comission
            parent.earned_sum += reg_user.number_to_distribute * core.parent_comission
            parent.save()
            num = reg_user.number_to_distribute * core.parent_comission
            text_2 += 'Parents comission: {0}\n\n'.format('%.2f' % num)

        else:
            core.bot_balance += reg_user.number_to_distribute * core.parent_comission
            core.save()
            num = reg_user.number_to_distribute * core.parent_comission
            text_2 += 'Parents comission + on bot balance: {0}\n\n'.format('%.2f' % num)

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
                if parent_user.goods_structures_earned_sum.get(str(structure_user.structure.id)):
                    print(parent_user.goods_structures_earned_sum)
                    parent_user.goods_structures_earned_sum[str(structure_user.structure.id)] += x*structure_parent.percent
                    print(parent_user.goods_structures_earned_sum)
                else:
                    print(parent_user.goods_structures_earned_sum)
                    parent_user.goods_structures_earned_sum[str(structure_user.structure.id)] = x*structure_parent.percent
                    print(parent_user.goods_structures_earned_sum)

                num = x*structure_parent.percent
                text_2 += 'Кешбек пользователю:{0} Номер в сетке товара: {1}, Уровень: {2}, Сумма:{3}\n'.format(
                    structure_parent.user.login, structure_parent.positional_id, structure_parent.level,
                    '%.2f' % num
                )
                parent_user.save()

                user: TgUser = TgUser.objects(auth_login=parent_user.login).first()
                if user:
                    msg = bot.send_message(user.user_id, text.format(
                        x*structure_parent.percent, reg_user.login, structure_parent.structure.fields.get('name')
                    ))
                    user.msgs_to_del.append(msg.message_id)
                    user.save()

            reg_user.balance += x*structure_user.percent
            reg_user.earned_sum += x*structure_user.percent
            if reg_user.goods_structures_earned_sum.get(str(structure_user.structure.id)):
                print(reg_user.goods_structures_earned_sum)
                reg_user.goods_structures_earned_sum[str(structure_user.structure.id)] += x*structure_user.percent
                print(reg_user.goods_structures_earned_sum)
            else:
                print(reg_user.goods_structures_earned_sum)
                reg_user.goods_structures_earned_sum[str(structure_user.structure.id)] = x * structure_user.percent
                print(reg_user.goods_structures_earned_sum)

            num = x * structure_user.percent
            text_2 += 'Кешбек пользователю:{0} Номер в сетке товара: {1}, Уровень: {2}, Сумма:{3}\n'.format(
                structure_user.user.login, structure_user.positional_id, structure_user.level,
                '%.2f' % num
            )
            reg_user.save()

            user: TgUser = TgUser.objects(auth_login=reg_user.login).first()
            if user:
                msg = bot.send_message(user.user_id, text.format(
                    x * structure_user.percent, reg_user.login, structure_user.structure.fields.get('name')
                ))
                user.msgs_to_del.append(msg.message_id)
                user.save()
        else:
            reg_user.balance += reg_user.number_to_distribute
            reg_user.earned_sum += reg_user.number_to_distribute
            if reg_user.goods_structures_earned_sum.get(str(structure_user.structure.id)):
                print(reg_user.goods_structures_earned_sum)
                reg_user.goods_structures_earned_sum[str(structure_user.structure.id)] += reg_user.number_to_distribute
                print(reg_user.goods_structures_earned_sum)
            else:
                print(reg_user.goods_structures_earned_sum)
                reg_user.goods_structures_earned_sum[str(structure_user.structure.id)] = reg_user.number_to_distribute
                print(reg_user.goods_structures_earned_sum)
            text_2 += 'Кешбек пользователю:{0} Номер в сетке товара: {1}, Уровень: {2}, Сумма:{3}\n'.format(
                structure_user.user.login, structure_user.positional_id, structure_user.level,
                '%.2f' % reg_user.number_to_distribute
            )
            reg_user.save()

        reg_user.number_to_distribute = 0
        reg_user.save()

    else:
        reg_user.number_to_distribute = reg_user.number_to_distribute - \
                                        reg_user.number_to_distribute*core.bot_comission
        reg_user.save()
        num = reg_user.number_to_distribute * core.bot_comission
        text_2 += 'Комиссия бота: {0}\n\n'.format('%.2f' % num)

        if len(ProductStructureUser.objects(structure=structure)) != 0:

            for struc_user in ProductStructureUser.objects(structure=structure):
                distribute_user_percents += struc_user.percent

            x = float(reg_user.number_to_distribute / distribute_user_percents)

            for struc_user in ProductStructureUser.objects(structure=structure):
                r_user = struc_user.user
                r_user.balance += x * struc_user.percent
                r_user.earned_sum += x * struc_user.percent
                if r_user.goods_structures_earned_sum.get(str(structure.id)):
                    print(r_user.goods_structures_earned_sum)
                    r_user.goods_structures_earned_sum[str(structure.id)] += x * struc_user.percent
                    print(r_user.goods_structures_earned_sum)

                else:
                    print(r_user.goods_structures_earned_sum)
                    r_user.goods_structures_earned_sum[str(structure.id)] = x * struc_user.percent
                    print(r_user.goods_structures_earned_sum)
                num = x * struc_user.percent
                text_2 += 'Кешбек пользователю:{0} Номер в сетке товара: {1}, Уровень: {2}, Сумма:{3}\n'.format(
                    struc_user.user.login, struc_user.positional_id, struc_user.level,
                    '%.2f' % num
                )
                r_user.save()
                user: TgUser = TgUser.objects(auth_login=struc_user.user.login).first()
                if user:
                    msg = bot.send_message(user.user_id, text.format(
                        x * struc_user.percent, reg_user.login, struc_user.structure.fields.get('name')
                    ))
                    user.msgs_to_del.append(msg.message_id)
                    user.save()
        else:
            core.bot_balance += reg_user.number_to_distribute
            text_2 += 'Кешбек ушел боту: {0}\n\n'.format('%.2f' % reg_user.number_to_distribute)

            core.save()
    return text_2


@app.route('/categories', methods=['GET', 'POST'])
def categories_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            categories_len = Category.objects(parent_category=None).count()

            p_all = ceil(categories_len / 20) if ceil(categories_len / 20) != 0 else 1

            if start > categories_len:
                start = categories_len

            if end > categories_len:
                end = categories_len

            categories = Category.objects(parent_category=None).order_by('-priority')[start:end]

            result = render_template(template_name_or_list='categories.html', p=page, rows=categories, p_all=p_all,
                                     u_all=categories_len, navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, CategoriesTextsTags))

    return result


@app.route('/sub_categories/category/edit/<string:category_id>', methods=['GET', 'POST'])
def edit_subcategory(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        result = make_response(redirect('/categories'))

        if not category_id:
            return result

        target_category = Category.objects(id=category_id).first()
        categories = Category.objects(Q(is_good=False) & Q(is_end=False)).order_by('-priority')

        if not target_category:
            return None

        if request.method == 'POST':

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    target_category.name[language.tag] = name
                else:
                    error = locale_text(user.partner_pannel_lang, 'bad_enter_lang_error_msg') + language.name + '!'
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', languages=languages,
                                        error=error, categories=categories))
                    return result

            for language in languages:
                description = request.form.get(language.tag + '_description')
                if description:
                    target_category.description[language.tag] = description

            price = request.form.get('price')
            if price:
                try:
                    price = price.replace(',', '.')
                    price = float(price)
                    target_category.price = price
                except ValueError:
                    error = locale_text(user.partner_pannel_lang, ' incorrect_entry_price_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result

            priority = request.form.get('priority')
            if priority:
                try:
                    priority = int(priority)
                    target_category.priority = priority
                except ValueError:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_enter_priority_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result

            image = request.files.get('image')

            if image:
                filename = secure_filename(image.filename)
                # image.save(os.path.join(app.root_path, 'static', 'tg_documents', 'photos', filename))
                src = '{0}/src/web_admin_panel/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)
                src_2 = '{0}/src/web_personal_cabinet/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)

                with open(src, 'wb') as f:
                    f.write(image.read())
                    f.close()

                copyfile(src, src_2)

                target_category.img_path = 'tg_documents/photos/' + filename

            category_col_num = request.form.get('category_col_num')
            if category_col_num:
                try:
                    category_col_num = int(category_col_num)
                    target_category.category_col_num = category_col_num
                except Exception as e:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_entry_num_col_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result
            category_row_num = request.form.get('category_row_num')
            if category_row_num:
                try:
                    category_row_num = int(category_row_num)
                    target_category.category_row_num = category_row_num
                except Exception:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_entry_num_str_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result

            parent = request.form.get('parent')
            if parent == '0':
                pass
            elif parent == '1':
                if target_category.parent_category:
                    old_parent = target_category.parent_category
                    old_parent.update(pull__sub_categories=target_category)
                    old_parent.reload()
                    if len(old_parent.sub_categories) == 0:
                        old_parent.is_last = True
                        old_parent.save()
                    for category in target_category.sub_categories:
                        old_parent.update(pull__sub_categories=category)
                        old_parent.reload()

                    while old_parent.parent_category:
                        old_parent = old_parent.parent_category
                        old_parent.update(pull__sub_categories=target_category)
                        old_parent.reload()
                        for category in target_category.sub_categories:
                            old_parent.update(pull__sub_categories=category)
                            old_parent.reload()
                target_category.parent_category = None
                target_category.save()
            elif parent:
                parent: Category = Category.objects(id=parent).first()
                if parent:
                    old_parent = target_category.parent_category
                    if old_parent:
                        old_parent.update(pull__sub_categories=target_category)
                        old_parent.reload()
                        if len(old_parent.sub_categories) == 0:
                            old_parent.is_last = True
                            old_parent.save()
                        for category in target_category.sub_categories:
                            old_parent.update(pull__sub_categories=category)
                            old_parent.reload()
                        while old_parent.parent_category:
                            old_parent = old_parent.parent_category
                            old_parent.update(pull__sub_categories=target_category)
                            old_parent.reload()
                            for category in target_category.sub_categories:
                                old_parent.update(pull__sub_categories=category)
                                old_parent.reload()

                        # res: bool = False
                        # if old_parent.sub_categories:
                        #     for category in old_parent.sub_categories:
                        #         if category.is_good:
                        #             res = True

                            # old_parent.is_show = res
                            # old_parent.save()
                        if not old_parent.sub_categories:
                            old_parent.is_last = True
                            old_parent.save()

                        # while old_parent.parent_category:
                        #     old_parent = old_parent.parent_category
                        #     res_2: bool = False
                        #
                        #     for category in old_parent.sub_categories:
                        #         if category.is_good:
                        #             res_2 = True

                            # old_parent.is_show = res_2
                            # old_parent.save()

                    target_category.parent_category = parent
                    target_category.save()
                    parent.update(add_to_set__sub_categories=target_category)
                    parent.reload()
                    for category in target_category.sub_categories:
                        parent.update(add_to_set__sub_categories=category)
                        parent.reload()

                    if parent.is_last:
                        parent.is_last = False
                        parent.save()

                    # res: bool = False
                    # for category in parent.sub_categories:
                    #     if category.is_good:
                    #         res = True
                    # # parent.is_show = res
                    # # parent.save()
                    #
                    # while parent.parent_category:
                    #     parent = parent.parent_category
                    #     res: bool = False
                    #     for category in parent.sub_categories:
                    #         if category.is_good:
                    #             res = True
                        # parent.is_show = res
                        # parent.save()

            target_category.save()
            result = make_response(redirect('/categories'))
        else:
            result = render_template(user=user, template_name_or_list='category.html',
                                     target_category=target_category, languages=languages, categories=categories)

    return result


@app.route('/sub_categories/<string:category_id>', methods=['GET', 'POST'])
def subcategories_method(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        category = Category.objects(id=category_id).first()
        languages = Language.objects
        if not category:
            return None

        if not user:
            return None

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            categories_len = Category.objects(parent_category=category).count()

            p_all = ceil(categories_len / 20) if ceil(categories_len / 20) != 0 else 1

            if start > categories_len:
                start = categories_len

            if end > categories_len:
                end = categories_len

            categories = Category.objects(parent_category=category).order_by('-priority')[start:end]
            result = render_template(user=user, template_name_or_list='categories.html', p=page, rows=categories, p_all=p_all,
                                     u_all=categories_len,
                                     navbar = get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts = get_pages_text(user.partner_pannel_lang, CategoriesTextsTags),
                                     languages = languages)

    return result


@app.route('/category', methods=['GET', 'POST'])
def category_method():
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user: User = User.objects(session_id=session_id).first()

        if not user:
            return None

        if request.method == 'POST':
            new_category = Category()

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    new_category.values[language.tag] = name
                else:
                    error =  locale_text(user.partner_pannel_lang, 'bad_enter_lang_error_msg') + language.name + '!'
                    result = make_response(render_template(template_name_or_list='category.html',
                                                           navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                                           texts=get_pages_text(user.partner_pannel_lang,
                                                                                CategoryTextsTags),
                                                           languages=languages,
                                                           error=error))
                    return result
            new_category.creator = user
            new_category.save()
            result = make_response(redirect('/categories'))
        else:
            result = render_template(template_name_or_list='category.html',
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, CategoryTextsTags),
                                     languages=languages)
    #
        return result
    return result


# todo otverstat html
@app.route('/feedback', methods=['GET', 'POST'])
def feedback_method():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        tg_user: TgUser = TgUser.objects(auth_login=user.login).first()
        feedback = Feedback.objects(reg_user=user).first()

        if not user or not tg_user:
            return redirect('/')

        if not feedback:
            feedback = Feedback()
            feedback.user = tg_user
            feedback.reg_user = user
            feedback.date = datetime.datetime.now() + datetime.timedelta(hours=3)
            feedback.save()

        questions = Question.objects(feedback=feedback)
        answers = Answer.objects(feedback=feedback)

        lst: list = list()
        rows: list = list()

        for i in questions:
            lst.append(i)

        for i in answers:
            lst.append(i)

        lst.sort(key=lambda r: r.date, reverse=True)

        for i in range(len(lst)):
            if isinstance(lst[i], Question):
                rows.append({'class': lst[i],
                             'type': 'in'})

            elif isinstance(lst[i], Answer):
                rows.append({'class': lst[i],
                             'type': 'out'})

        if request.method == 'POST':
            text = request.form.get('message')
            if not text:
                error = locale_text('rus', 'no_enter_message')
                result = render_template(template_name_or_list='dialog.html', error=error, rows=rows, feedback=feedback,
                                         user=user,
                                         navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                         texts=get_pages_text(user.partner_pannel_lang, DialogTextsTags))
                return result
            # else:
            #     question = Question()
            #     question.feedback = feedback
            #     question.date = datetime.datetime.now(Zone(3, False, 'GMT'))
            #     question.content_type = 'text'
            #
            #     question.save()
            #
            #     feedback.is_new_question_exist = True
            #     feedback.save()

            image = request.files.get('image')
            # image_2 = request.files.get('image')

            if image:
                try:
                    filename = secure_filename(image.filename)

                    src = '{0}/src/web_admin_panel/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)
                    src_2 = '{0}/src/web_personal_cabinet/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)



                    with open(src, 'wb') as f:
                        f.write(image.read())
                        f.close()

                    copyfile(src, src_2)


                    # # image.save(os.path.join(app.root_path.replace('web_personal_cabinet', 'web_admin_panel'), 'static', 'tg_documents',
                    # #                         'photos', filename))
                    # image.save(os.path.join(app.root_path, 'static', 'tg_documents',
                    #                           'photos', filename))


                    # msg = bot.send_photo(chat_id=feedback.user.user_id, photo=f, caption=text)
                    question = Question()
                    question.feedback = feedback
                    question.date = datetime.datetime.now(Zone(3, False, 'GMT'))
                    question.content_type = 'photo'
                    question.text = text
                    question.image_path = 'tg_documents/photos/' + filename
                    question.save()

                    feedback.is_new_question_exist = True
                    feedback.save()

                except Exception as e:
                    print(e)
                    error = locale_text(user.partner_pannel_lang, 'attach_picture_error_msg')
                    result = render_template(template_name_or_list='dialog.html', error=error, rows=rows,
                                             feedback=feedback, user=user,
                                             navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                             texts=get_pages_text(user.partner_pannel_lang, DialogTextsTags))
                    return result
            else:
                try:
                    # bot.send_message(feedback.user.user_id, text)
                    question = Question()
                    question.feedback = feedback
                    question.date = datetime.datetime.now(Zone(3, False, 'GMT'))
                    question.text = text
                    question.save()

                    feedback.is_new_question_exist = True
                    feedback.save()
                except Exception as e:
                    error = locale_text(user.partner_pannel_lang, 'block_user_error_msg')
                    result = render_template(template_name_or_list='dialog.html', error=error, rows=rows,
                                             feedback=feedback, user=user,
                                             navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                             texts=get_pages_text(user.partner_pannel_lang, DialogTextsTags))
                    return result

            result = make_response(redirect('/feedback'))
        else:
            result = render_template(template_name_or_list='dialog.html', user=user, rows=rows, feedback=feedback,
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, DialogTextsTags))

    return result


@app.route('/sub_category/<string:category_id>', methods=['GET', 'POST'])
def subcategory_method(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        category = Category.objects(id=category_id).first()

        if request.method == 'POST':
            new_category = Category()

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    new_category.values[language.tag] = name
                else:
                    error =  locale_text(user.partner_pannel_lang, 'bad_enter_lang_error_msg') + language.name + '!'
                    result = make_response(render_template(user=user, template_name_or_list='category.html',
                                                           languages=languages,
                                                           navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                                           texts=get_pages_text(user.partner_pannel_lang,
                                                                                CategoryTextsTags),
                                                           error=error))
                    return result

            new_category.parent_category = category
            new_category.creator = user
            new_category.save()

            result = make_response(redirect('/categories'))
        else:
            result = render_template(template_name_or_list='category.html',
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, CategoryTextsTags),
                                     languages=languages, parent_category=category)

    return result


@app.route('/sub_categories/sub_category/<string:category_id>', methods=['GET', 'POST'])
def subcategory_method_2(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        category = Category.objects(id=category_id).first()

        if request.method == 'POST':
            new_category = Category()

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    new_category.values[language.tag] = name
                else:
                    error =  locale_text(user.partner_pannel_lang, 'bad_enter_lang_error_msg') + language.name + '!'
                    result = make_response(render_template(user=user, template_name_or_list='category.html',
                                                           languages=languages,
                                                           navbar=get_pages_text(user.partner_pannel_lang,
                                                                                 NavbarTextsTags),
                                                           texts=get_pages_text(user.partner_pannel_lang,
                                                                                CategoryTextsTags),
                                                           error=error))
                    return result

            new_category.parent_category = category
            new_category.creator = user
            new_category.save()

            result = make_response(redirect('/categories'))
        else:
            result = render_template(template_name_or_list='category.html',
                                     navbar=get_pages_text(user.partner_pannel_lang, NavbarTextsTags),
                                     texts=get_pages_text(user.partner_pannel_lang, CategoryTextsTags),
                                     languages=languages, parent_category=category)

    return result


@app.route('/category/edit/<string:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('personal_shop_cabinet_session_id', None)
        user = User.objects(session_id=session_id).first()
        result = make_response(redirect('/categories'))

        if not category_id:
            return result

        target_category = Category.objects(id=category_id).first()

        if not target_category:
            return None
        categories = Category.objects(Q(is_end=False) & Q(is_good=False)).order_by('-priority')
        res: list = list()
        for category in categories:
            if category != target_category and category not in target_category.sub_categories:
                res.append(category)

        categories = res
        if request.method == 'POST':

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    target_category.name[language.tag] = name
                else:
                    error =  locale_text(user.partner_pannel_lang, 'bad_enter_lang_error_msg') + language.name + '!'
                    result = make_response(render_template(user=user, template_name_or_list='category.html',
                                                           languages=languages,
                                                           error=error, categories=categories))
                    return result

            for language in languages:
                description = request.form.get(language.tag + '_description')
                if description:
                    target_category.description[language.tag] = description

            parent = request.form.get('parent')
            if parent == '0':
                pass
            elif parent == '1':
                if target_category.parent_category:
                    old_parent = target_category.parent_category
                    old_parent.update(pull__sub_categories=target_category)
                    old_parent.reload()
                    if len(old_parent.sub_categories) == 0:
                        old_parent.is_last = True
                        old_parent.save()
                    for category in target_category.sub_categories:
                        old_parent.update(pull__sub_categories=category)
                        old_parent.reload()

                    while old_parent.parent_category:
                        old_parent = old_parent.parent_category
                        old_parent.update(pull__sub_categories=target_category)
                        old_parent.reload()
                        for category in target_category.sub_categories:
                            old_parent.update(pull__sub_categories=category)
                            old_parent.reload()

                target_category.parent_category = None
                target_category.save()
            elif parent:
                parent: Category = Category.objects(id=parent).first()
                if parent:
                    old_parent = target_category.parent_category
                    if old_parent:
                        old_parent.update(pull__sub_categories=target_category)
                        old_parent.reload()
                        if len(old_parent.sub_categories) == 0:
                            old_parent.is_last = True
                            old_parent.save()
                        for category in target_category.sub_categories:
                            old_parent.update(pull__sub_categories=category)
                            old_parent.reload()
                        while old_parent.parent_category:
                            old_parent = old_parent.parent_category
                            old_parent.update(pull__sub_categories=target_category)
                            old_parent.reload()
                            for category in target_category.sub_categories:
                                old_parent.update(pull__sub_categories=category)
                                old_parent.reload()
                        # res: bool = False
                        # if old_parent.sub_categories:
                        #     for category in old_parent.sub_categories:
                        #         if category.is_good:
                        #             res = True

                            # old_parent.is_show = res
                            # old_parent.save()
                        if not old_parent.sub_categories:
                            old_parent.is_last = True
                            old_parent.save()

                        # while old_parent.parent_category:
                        #     old_parent = old_parent.parent_category
                            # res_2: bool = False
                            #
                            # for category in old_parent.sub_categories:
                            #     if category.is_good:
                            #         res_2 = True

                            # old_parent.is_show = res_2
                            # old_parent.save()

                    target_category.parent_category = parent
                    target_category.save()
                    parent.update(add_to_set__sub_categories=target_category)
                    parent.reload()
                    for category in target_category.sub_categories:
                        parent.update(add_to_set__sub_categories=category)
                        parent.reload()

                    if parent.is_last:
                        parent.is_last = False
                        parent.save()

                    # res: bool = False
                    # for category in parent.sub_categories:
                    #     if category.is_good:
                    #         res = True
                    # parent.is_show = res
                    # parent.save()

                    # while parent.parent_category:
                    #     parent = parent.parent_category
                    #     res: bool = False
                    #     for category in parent.sub_categories:
                    #         if category.is_good:
                    #             res = True
                        # parent.is_show = res
                        # parent.save()

                else:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_category_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result

            price = request.form.get('price')
            if price:
                try:
                    price = price.replace(',', '.')
                    price = float(price)
                    target_category.price = price
                except ValueError:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_enter_error_msg')
                    result = make_response(render_template(user=user, template_name_or_list='category.html',
                                                           error=error,
                                                           languages=languages, categories=categories))
                    return result

            priority = request.form.get('priority')
            if priority:
                try:
                    priority = int(priority)
                    target_category.priority = priority
                except ValueError:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_enter_priority_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html',
                                        error=error,
                                        languages=languages, categories=categories))
                    return result

            image = request.files.get('image')

            if image:
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.root_path, 'static', 'tg_documents', 'photos', filename))
                src = '{0}/src/web_admin_panel/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)
                f = open(src, 'rb')
                target_category.img_path = 'tg_documents/photos/' + filename

            category_col_num = request.form.get('category_col_num')
            if category_col_num:
                try:
                    category_col_num = int(category_col_num)
                    target_category.category_col_num = category_col_num
                except Exception as e:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_entry_num_col_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result
            category_row_num = request.form.get('category_row_num')
            if category_row_num:
                try:
                    category_row_num = int(category_row_num)
                    target_category.category_row_num = category_row_num
                except Exception as e:
                    error = locale_text(user.partner_pannel_lang, 'incorrect_entry_num_str_error_msg')
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories))
                    return result

            target_category.save()
            result = make_response(redirect('/categories'))
        else:
            result = render_template(user=user, template_name_or_list='category.html',
                                     target_category=target_category, languages=languages, categories=categories)

    return result


