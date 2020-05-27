import hashlib
import re
import string
import random
import threading
import time
import os
import datetime
import smtplib
from email.mime.text import MIMEText
from datetime import timedelta, tzinfo
from math import ceil
from typing import List

from flask import Flask, render_template, request, make_response, redirect, jsonify, send_from_directory
from flask_bootstrap import Bootstrap
from flask_mongoengine import MongoEngine
from flask.helpers import send_file
from werkzeug.utils import secure_filename
from shutil import copyfile
from multiprocessing import Pool
from mongoengine.queryset.visitor import Q

from .. import config

from .db_model.user import User
from ..tg_bot.db_model.user_register import UserRegister

from ..tg_bot.db_model.user import User as TgUser


from ..core.db_model.core import Core

from ..core.db_model.structure import Product, ProductStructureUser

from ..core.db_model.text.text import Text
from ..core.db_model.text.language import Language
from ..core.db_model.message import Message
from ..core.db_model.category import Category
from ..core.db_model.currency import Currency
from ..core.db_model.feedback import Feedback, Answer, Question
from ..core.db_model.faq import Frequent
from ..core.db_model.comment import Comment
from ..core.db_model.field import Field
from telebot import TeleBot
from telebot import types
from telebot.types import InputMediaPhoto
from telebot.types import InputTextMessageContent
from ..config import BOT_TOKEN
from ..tg_bot.keyboards import locale_text
from ..binary_referral_system.referrals_indent import referrals_indent, find_parents_ids, graph_product_data

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


@app.route('/currencies', methods=['GET', 'POST'])
def currencies_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/currencies')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            currencies_len = Currency.objects.count()

            p_all = ceil(currencies_len / 20) if ceil(currencies_len / 20) != 0 else 1

            if start > currencies_len:
                start = currencies_len

            if end > currencies_len:
                end = currencies_len

            currencies = Currency.objects[start:end]
            result = render_template(template_name_or_list='currencies.html', p=page, rows=currencies, p_all=p_all,
                                     u_all=currencies_len, user=user)

    return result


@app.route('/currency', methods=['GET', 'POST'])
def currency_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        languages = Language.objects

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/currencies')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            new_currency = Currency()

            tag = request.form.get('tag')
            if tag:
                new_currency.tag = tag
            else:
                error = 'Вы не ввели тег!'
                result = make_response(render_template('currency.html', languages=languages, error=error, user=user))
                return result

            for language in languages:
                value = request.form.get(language.tag + '_value')
                if value:
                    new_currency.values[language.tag] = value
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template('currency.html', languages=languages, error=error, user=user))
                    return result
            new_currency.save()
            result = make_response(redirect('/currencies'))
        else:
            result = render_template(template_name_or_list='currency.html', languages=languages, user=user)

    return result


@app.route('/currency/edit/<string:currency_id>', methods=['GET', 'POST'])
def edit_currency(currency_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/currencies'))

        if not currency_id:
            return result

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/currencies')
            if result:
                return make_response(redirect(result))

        languages = Language.objects

        target_currency = Currency.objects(id=currency_id).first()

        if not target_currency:
            return None

        if request.method == 'POST':
            tag = request.form.get('tag')
            if tag:
                target_currency.tag = tag
            else:
                error = 'Вы не ввели тег!'
                result = make_response(render_template('currency.html', target_text=target_currency, languages=languages,
                                                       error=error, user=user))
                return result

            for language in languages:
                value = request.form.get(language.tag + '_value')
                if value:
                    target_currency.values[language.tag] = value
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template('currency.html', target_text=target_currency, languages=languages,
                                                           error=error, user=user))
                    return result
            target_currency.save()
            result = make_response(redirect('/currencies'))
        else:
            result = render_template(template_name_or_list='currency.html',
                                     target_text=target_currency,
                                     languages=languages, user=user)

    return result


@app.route('/currency/del/<string:text_id>', methods=['GET', 'POST'])
def del_currency(text_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/'))

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/currencies')
            if result:
                return make_response(redirect(result))

        if not text_id:
            return result

        target_currency = Currency.objects(id=text_id).first()

        for user in TgUser.objects:
            user.choose_wallet = str()
            user.wallets.pop(target_currency.tag)
            user.save()

        if target_currency:
            target_currency.delete()
            result = make_response(redirect('/currrencies'))

    return result


@app.route('/feedbacks', methods=['GET', 'POST'])
def feedbacks():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/feedbacks')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            feedabcks_len = Feedback.objects.count()

            p_all = ceil(feedabcks_len / 20) if ceil(feedabcks_len / 20) != 0 else 1

            if start > feedabcks_len:
                start = feedabcks_len

            if end > feedabcks_len:
                end = feedabcks_len

            feedbacks = Feedback.objects[start:end].order_by('date', 'is_new_question_exist')
            result = render_template(template_name_or_list='feedbacks.html', p=page, rows=feedbacks, p_all=p_all,
                                     u_all=feedabcks_len, user=user)
    return result


@app.route('/feedback/del/<string:feedback_id>', methods=['GET', 'POST'])
def feedback_del(feedback_id):
    result = make_response(redirect('/login'))
    if auth_check():

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        feedback = Feedback.objects(id=feedback_id).first()
        if user.rank != 0:
            result = user.get_access('/feedbacks')
            if result:
                return make_response(redirect(result))

        if not feedback:
            return redirect('feedbacks')

        feedback.delete()

        result = make_response(redirect('/feedbacks'))

    return result


@app.route('/feedback/view/<string:feedback_id>', methods=['GET', 'POST'])
def feedback_view(feedback_id):
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/feedbacks')
            if result:
                return make_response(redirect(result))

        feedback = Feedback.objects(id=feedback_id).first()

        if not feedback:
            return redirect('feedbacks')

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
                result = render_template(template_name_or_list='dialog.html', error=error, rows=rows, feedback=feedback, user=user)
                return result
            image = request.files.get('image')

            if image:
                try:
                    filename = secure_filename(image.filename)

                    src = '{0}/src/web_admin_panel/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)
                    src_2 = '{0}/src/web_personal_cabinet/static/tg_documents/photos/{1}'.format(os.getcwd(), filename)

                    with open(src, 'wb') as f:
                        f.write(image.read())
                        f.close()

                    copyfile(src, src_2)

                    answer = Answer()
                    answer.feedback = feedback
                    answer.date = datetime.datetime.now(Zone(3, False, 'GMT'))
                    answer.text = text
                    answer.image_path = 'tg_documents/photos/' + filename
                    answer.save()

                    feedback.is_new_question_exist = False
                    feedback.save()
                    with open(src, 'rb') as f:
                        bot.send_photo(chat_id=feedback.user.user_id, photo=f, caption=text)

                except Exception as e:
                    print(e)
                    error = 'Прикрепите картинку'
                    result = render_template(template_name_or_list='dialog.html', error=error, rows=rows,
                                             feedback=feedback, user=user)
                    return result
            else:
                try:
                    bot.send_message(feedback.user.user_id, text)
                    answer = Answer()
                    answer.feedback = feedback
                    answer.date = datetime.datetime.now(Zone(3, False, 'GMT'))
                    answer.text = text
                    answer.save()

                    feedback.is_new_question_exist = False
                    feedback.save()
                except Exception as e:
                    error = 'Пользователь заблокирован'
                    result = render_template(template_name_or_list='dialog.html', error=error, rows=rows,
                                             feedback=feedback, user=user)
                    return result

            result = make_response(redirect('/feedback/view/{0}'.format(feedback_id)))
        else:
            result = render_template(template_name_or_list='dialog.html', user=user, rows=rows, feedback=feedback)

    return result


@app.route('/web_admins', methods=['GET', 'POST'])
def web_admin():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/web_admins')
            if result:
                return make_response(redirect(result))
        search = request.args.get('search')
        if not search:
            search = ''
        if request.method == 'POST':

            search = request.form.get('search')

            if search:
                return make_response(redirect('/web_admins?search={0}'.format(search)))

            page = request.form.get('page')
            if page:
                try:
                    page = int(page)
                    return make_response(redirect('/web_admins?p={0}'.format(page)))
                except ValueError:
                    return make_response(redirect('/web_admins'))

        else:
            end = page * 20
            start = end - 20
            web_admins_len = User.objects(login__icontains=search).count()

            p_all = ceil(web_admins_len / 20) if ceil(web_admins_len / 20) != 0 else 1

            if start > web_admins_len:
                start = web_admins_len

            if end > web_admins_len:
                end = web_admins_len

            web_admins = User.objects[start:end].order_by('positional_id') if not search else \
                User.objects(login__icontains=search)
            result = render_template(template_name_or_list='web_admins.html', p=page, rows=web_admins, p_all=p_all,
                                     u_all=web_admins_len, user=user, search=search)
    return result


@app.route('/web_admins/edit/<string:user_id>', methods=['GET', 'POST'])
def edit_web_admin(user_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/web_admins'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user_id or not user:
            return result

        if user.rank != 0:
            result = user.get_access('/web_admins')
            if result:
                return make_response(redirect(result))

        web_admin = User.objects(id=user_id).first()

        if request.method == 'POST':
            login = request.form.get('login')
            if login:
                web_admin.login = login
            else:
                error = 'Вы не ввели логин!'
                result = make_response(render_template('web_admin.html', user=user, web_admin=web_admin))
                return result

            rank = request.form.get('rank')
            if rank:
                web_admin.rank = int(rank)

            password = request.form.get('password')
            if password:
                web_admin.password_text = password
                web_admin.password = hashlib.md5(password.encode('utf-8')).hexdigest()
            # else:
            #     error = 'Вы не ввели пароль!'
            #     result = make_response(render_template('web_admin.html', error=error, user=user))
            #     return result


            web_admin.save()
            result = make_response(redirect('/web_admins'))
        else:
            if web_admin:
                result = render_template(template_name_or_list='web_admin.html',
                                         user=user, web_admin=web_admin)

    return result


@app.route('/web_admin', methods=['GET', 'POST'])
def add_web_admin():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/web_admins')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            new_web_admin = User()

            login = request.form.get('login')
            if login:
                new_web_admin.login = login
            else:
                error = 'Вы не ввели логин!'
                result = make_response(render_template('web_admin.html', error=error, user=user))
                return result

            rank = request.form.get('rank')
            if rank:
                web_admin.rank = float(rank)
            password = request.form.get('password')
            if password:
                new_web_admin.password_text = password
                new_web_admin.password = hashlib.md5(password.encode('utf-8')).hexdigest()
            else:
                error = 'Вы не ввели логин!'
                result = make_response(render_template('web_admin.html', error=error, user=user))
                return result

            new_web_admin.save()
            result = make_response(redirect('/web_admins'))
        else:
            result = render_template(template_name_or_list='web_admin.html', user=user)

    return result


@app.route('/web_admins/del/<string:text_id>', methods=['GET', 'POST'])
def web_admin_del(text_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        result = make_response(redirect('/'))
        if not user:
            return None
        if user.rank != 0:
            result = user.get_access('/web_admins')
            if result:
                return make_response(redirect(result))

        if not text_id:
            return result

        web_admin = User.objects(id=text_id).first()

        if web_admin:
            web_admin.delete()
            result = make_response(redirect('/web_admins'))

    return result


@app.route('/<string:any>', methods=['GET'])
def error_page(any):
    return make_response(render_template('error.html'))


@app.route('/', methods=['GET', 'POST'])
def index():
    result = make_response(redirect('/login'))
    # categories = Category.objects(goods_num__gt=0)
    #     # for category in categories:
    #     #     category.goods_num=0
    #     #     category.save()
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/')
            if result:
                return make_response(redirect(result))

        core: Core = Core.objects.first()
        if request.method == 'POST':
            bot_comission = request.form.get('bot_comission')
            if bot_comission:
                core.bot_comission = float(bot_comission)
            else:
                error = 'Вы не ввели комиссию бота!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            parent_comission = request.form.get('parent_comission')
            if parent_comission:
                core.parent_comission = float(parent_comission)
            else:
                error = 'Вы не ввели процент, который уходить родителю!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            structure_comission = request.form.get('structure_comission')
            if structure_comission:
                core.structure_comission = float(structure_comission)
            else:
                error = 'Вы не ввели процент роспределения по сетке!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            bot_balance = request.form.get('bot_balance')
            if bot_balance:
                core.bot_balance = float(bot_balance)
            else:
                error = 'Вы не ввели баланс бота!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            category_row_num = request.form.get('category_row_num')
            if category_row_num:
                core.category_row_num = int(category_row_num)
            else:
                error = 'Вы не ввели кол-во строк бота!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            category_col_num = request.form.get('category_col_num')
            if category_col_num:
                core.category_col_num = int(category_col_num)
            else:
                error = 'Вы не ввели кол-во столбцов бота!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            subscribe_price = request.form.get('subscribe_price')
            if subscribe_price:
                core.subscribe_price = float(subscribe_price)
            else:
                error = 'Вы не ввели цену подписки бота!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            shop_name_text = request.form.get('shop_name_text')
            if shop_name_text:
                core.shop_name_text = str(shop_name_text)
            else:
                error = 'Вы не ввели название магазина!'
                result = make_response(render_template('index.html', core=core, error=error, user=user))
                return result

            presentation = request.files.get('presentation')

            if presentation:
                filename = secure_filename(presentation.filename)
                presentation.save(os.path.join(app.root_path, 'static', 'tg_documents', 'files', 'presentation.pdf'))
                src = '{0}/src/web_admin_panel/static/tg_documents/files/{1}'.format(os.getcwd(), 'presentation.pdf')
                f = open(src, 'rb')
                print(f)
                f.close()
                core.presentation_path = 'tg_documents/files/' + 'presentation.pdf'

            core.save()
            print(core.presentation_path)

        result = render_template(template_name_or_list='index.html',
                                 core=core, user=user)

    return result


@app.route('/error', methods=['GET', 'POST'])
def error():
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        return make_response(render_template(template_name_or_list='error.html', user=user))
    else:
        return make_response(redirect('/login'))


@app.route('/finances', methods=['GET', 'POST'])
def finances():
    result = make_response(redirect('/finances'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/finances')
            if result:
                return make_response(redirect(result))
        core: Core = Core.objects.first()
        if request.method == 'POST':
            bitcoin_wallet = request.form.get('bitcoin_wallet')
            if bitcoin_wallet:
                core.bitcoin_wallet = bitcoin_wallet
                core.save()
            else:
                error = 'Вы не ввели BITCOIN кошелёк'
                result = make_response(render_template('finances.html', error=error, user=user, core=core))
                return result
            bip_minter_wallet = request.form.get('bip_minter_wallet')
            if bip_minter_wallet:
                core.bip_minter_wallet = bip_minter_wallet
                core.save()
            else:
                error = 'Вы не ввели BIP MINTER кошелёк'
                result = make_response(render_template('finances.html', error=error, user=user, core=core))
                return result
            ethereum_wallet = request.form.get('ethereum_wallet')
            if ethereum_wallet:
                core.ethereum_wallet = ethereum_wallet
                core.save()
            else:
                error = 'Вы не ввели ETHEREUM кошелёк'
                result = make_response(render_template('finances.html', error=error, user=user, core=core))
                return result
            perfectmoney_wallet = request.form.get('perfectmoney_wallet')
            if perfectmoney_wallet:
                core.perfectmoney_wallet = perfectmoney_wallet
                core.save()
            else:
                error = 'Вы не ввели PERFECTMONEY кошелёк'
                result = make_response(render_template('finances.html', error=error, user=user, core=core))
                return result
            sber_wallet = request.form.get('sber_wallet')
            if sber_wallet:
                core.sber_wallet = sber_wallet
                core.save()
            else:
                error = 'Вы не ввели СБЕР кошелёк'
                result = make_response(render_template('finances.html', error=error, user=user, core=core))
                return result
        result = render_template(template_name_or_list='finances.html',
                                 core=core, user=user)
    return result


@app.route('/marketing', methods=['GET', 'POST'])
def marketing():
    result = make_response(redirect('/marketing'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/marketing')
            if result:
                return make_response(redirect(result))
        result = render_template(template_name_or_list='marketing.html', user=user)
    return result


@app.route('/users', methods=['GET', 'POST'])
def users():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/users')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            users_len = TgUser.objects.count()

            p_all = ceil(users_len / 20) if ceil(users_len / 20) != 0 else 1

            if start > users_len:
                start = users_len

            if end > users_len:
                end = users_len

            tg_users = TgUser.objects[start:end].order_by('positional_id')
            result = render_template(template_name_or_list='users.html', p=page, rows=tg_users, p_all=p_all,
                                     u_all=users_len, user=user)
    return result


@app.route('/user/edit/<string:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/users'))
        if not user_id:
            return result
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if user.rank != 0:
            result = user.get_access('/users')
            if result:
                return make_response(redirect(result))
        target_user = TgUser.objects(id=user_id).first()
        reg_user = UserRegister.objects(login=target_user.auth_login).first()
        if request.method == 'POST':
            # balance = request.form.get('balance')
            # if balance:
            #     target_user.balance = float(balance)
            # else:
            #     error = 'Вы не ввели баланс!'
            #     result = make_response(render_template('user.html', error=error, user=user, user=target_user))
            #     return result

            username = request.form.get('username')
            if username:
                target_user.username = username
            first_name = request.form.get('first_name')
            if first_name:
                target_user.first_name = first_name
            last_name = request.form.get('last_name')
            if last_name:
                target_user.last_name = last_name

            target_user.save()
            result = make_response(redirect('/users'))
        else:
            if target_user:
                result = render_template(template_name_or_list='user.html',
                                         target_user=target_user, reg_user=reg_user, user=user)

    return result


@app.route('/shops/viev/<string:market_id>', methods=['GET', 'POST'])
def market_viev(market_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/shops'))
        if not market_id:
            return result
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/shops')
            if result:
                return make_response(redirect(result))

        admin_panel = True
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        target_market = UserRegister.objects(id=market_id).first()

        if request.method == 'POST':
            balance = request.form.get('balance').replace(',', '.')
            try:
                target_market.balance = float(balance)
                target_market.save()
            except Exception as e:
                print(e)

            result = make_response(redirect('/shops/viev/{0}'.format(target_market.id)))
            return result

        if target_market:
            data = graph_data(target_market, admin_panel) if target_market.is_main_structure else None
            children_count = str(data).count("children") if data else None
            result = render_template(template_name_or_list='shop.html', market=target_market, user=user,
                                     data=data, children_count=children_count)
        else:
            result = make_response(redirect('/shops'))
    return result


@app.route('/user/find', methods=['POST'])
def find_user():
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/users'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/users')
            if result:
                return make_response(redirect(result))

        user_id = request.form.get('user_id')
        try:
            target_user: TgUser = TgUser.objects(user_id=int(user_id)).first()

            if user_id:
                result = make_response(redirect('/user/edit/'+str(target_user.id)))
        except:
            pass

    return result


@app.route('/user/del/<string:user_id>', methods=['GET', 'POST'])
def del_user(user_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/users'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/users')
            if result:
                return make_response(redirect(result))

        if not user_id:
            return result

        target_user: TgUser = TgUser.objects(id=user_id).first()
        target_user.delete()

    return result


# language adding and editing
@app.route('/languages', methods=['GET', 'POST'])
def languages_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/languages')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            languages_len = Language.objects.count()

            p_all = ceil(languages_len / 20) if ceil(languages_len / 20) != 0 else 1

            if start > languages_len:
                start = languages_len

            if end > languages_len:
                end = languages_len

            languages = Language.objects[start:end]
            result = render_template(template_name_or_list='languages.html', p=page, rows=languages, p_all=p_all,
                                     u_all=languages_len, user=user)
    return result


@app.route('/language', methods=['GET', 'POST'])
def language_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/languages')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            new_language = Language()

            name = request.form['name']
            if name:
                new_language.name = name
            else:
                error = 'Вы не ввели название!'
                result = make_response(render_template('language.html', error=error, user=user))
                return result

            tag = request.form['tag']
            if tag:
                new_language.tag = tag
            else:
                error = 'Вы не ввели тег!'
                result = make_response(render_template('language.html', error=error, user=user))
                return result

            button_text = request.form['button_text']
            if tag:
                new_language.button_text = button_text
            else:
                error = 'Вы не ввели текст кнопки!'
                result = make_response(render_template('language.html', error=error, user=user))
                return result

            new_language.save()
            result = make_response(redirect('/languages'))
        else:
            result = render_template(template_name_or_list='language.html', user=user)

    return result


@app.route('/language/edit/<string:language_id>', methods=['GET', 'POST'])
def edit_language(language_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/languages'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/shops')
            if result:
                return make_response(redirect(result))

        target_language = Language.objects(id=language_id).first()

        if request.method == 'POST':
            name = request.form['name']
            if name:
                target_language.name = name
            else:
                error = 'Вы не ввели название!'
                result = make_response(render_template('language.html', error=error, user=user))
                return result

            tag = request.form['tag']
            if tag:
                target_language.tag = tag
            else:
                error = 'Вы не ввели тег!'
                result = make_response(render_template('language.html', error=error, user=user))
                return result

            button_text = request.form['button_text']
            if tag:
                target_language.button_text = button_text
            else:
                error = 'Вы не ввели текст кнопки!'
                result = make_response(render_template('language.html', error=error, user=user))
                return result

            target_language.save()
            result = make_response(redirect('/languages'))
        else:
            if target_language:
                result = render_template(template_name_or_list='language.html',
                                         target_language=target_language, user=user)

    return result


@app.route('/language/del/<string:language_id>')
def del_language(language_id):
    result = make_response(redirect('/login'))
    if auth_check():

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if user.rank != 0:
            result = user.get_access('/languages')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/languages'))

        if not language_id:
            return result

        target_language = Language.objects(id=language_id).first()

        if target_language:
            target_language.delete()

    return result


# text adding and editing
@app.route('/texts', methods=['GET', 'POST'])
def texts_method():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if user.rank != 0:
            result = user.get_access('/texts')
            if result:
                return make_response(redirect(result))

        if not user:
            return None
        if request.method == 'POST':
            pass
        else:
            texts = Text.objects
            result = render_template(template_name_or_list='texts.html', rows=texts, user=user)

    return result


@app.route('/ajax/texts', methods=['GET'])
def ajax_texts_method():
    texts: List[Text] = Text.objects()
    data = list()

    edit_button_html = '<a href="text/edit/{identifier}">Просмотр/Редактирование</a>'
    delete_button_html = '<button type="button" class="btn btn-danger" ' \
                         'data-toggle="modal" data-target="#applying_modal" ' \
                         'data-id="{identifier}">Удалить</button>'

    for text in texts:
        text_data = dict()

        text_data['tag'] = text.tag
        text_data['applying_way'] = text.applying_way

        for lang in Language.objects:
            text_data[lang.tag] = text.values.get(lang.tag)

        text_data['edit_button_html'] = edit_button_html.format(identifier=str(text.id))
        text_data['delete_button_html'] = delete_button_html.format(identifier=str(text.id))

        data.append(text_data)

    return jsonify(data)


@app.route('/ajax/generate_logs', methods=['GET'])
def ajax_generate_logs_method():
    logs = GenerateLogs.objects.order_by('-date')
    data = list()

    for log in logs:
        text_data = dict()

        text_data['date'] = log.date
        text_data['result'] = log.result

        data.append(text_data)

    return jsonify(data)


@app.route('/ajax/categories', methods=['GET'])
def ajax_categories_method():
    categories: Category = Category.objects(parent_category=None)

    data = list()

    delete_button_html = '<button type="button" class="btn btn-danger" ' \
                         'data-toggle="modal" data-target="#applying_modal" ' \
                         'data-id="{0}">Удалить</button>'

    for category in categories:
        category_data = dict()

        category_data['text'] = category.values['rus']
        category_data['parent_category'] = category.parent_category.values['rus'] if category.parent_category else ''

        # for lang in Language.objects:
        #     text_data[lang.tag] = category.values.get(lang.tag)

        category_data['edit_button_html'] = '<a href="category/edit/{0}">Редактировать</a>'.format(category.id)
        category_data['add_sub_button_html'] = '<a href="sub_category/{0}">Добавить подкатегорию</a>'.format(category.id)
        category_data['subcategories'] = '<a href="{0}"'.format(category.id) + '>Подкатегории</a>' if category.parent_category else '<a href="sub_categories/{0}"'.format(category.id) + '>Подкатегории</a>'
        category_data['moderation'] = '''<a href="/category/moderate_off/{0}">Удалить из бота</a>'''.format(category.id) if category.is_moderated \
        else '''<a href="/category/moderate_on/{0}">Добавить в бота</a>'''.format(category.id)

        category_data['delete_button_html'] = delete_button_html.format(category.id) if category.goods_num == 0 else 'Невозможно удалить'

        data.append(category_data)

    return jsonify(data)


@app.route('/ajax/subcategories/<string:parent_id>', methods=['GET'])
def ajax_subcategories_method(parent_id):
    parent: Category = Category.objects(id=parent_id).first()

    if not parent:
        return None

    categories: Category = Category.objects(parent_category=parent)

    data = list()
    delete_button_html = '<button type="button" class="btn btn-danger" ' \
                         'data-toggle="modal" data-target="#applying_modal" ' \
                         'data-id="{0}">Удалить</button>'

    for category in categories:
        category_data = dict()

        category_data['text'] = category.values['rus']
        category_data['parent_category'] = category.parent_category.values['rus'] if category.parent_category else ''

        # for lang in Language.objects:
        #     text_data[lang.tag] = category.values.get(lang.tag)

        category_data['edit_button_html'] = '<a href="category/edit/{0}">Редактировать</a>'.format(category.id)
        category_data['add_sub_button_html'] = '<a href="sub_category/{0}">Добавить подкатегорию</a>'.format(category.id)
        category_data['subcategories'] = '<a href="{0}"'.format(category.id) + '>Подкатегории</a>' if category.parent_category else '<a href="sub_categories/{0}"'.format(category.id) + '>Подкатегории</a>'
        category_data['moderation'] = '''<a href="/category/moderate_off/{0}">Удалить из бота</a>'''.format(category.id) if category.is_moderated \
        else '''<a href="/category/moderate_on/{0}">Добавить в бота</a>'''.format(category.id)
        category_data['delete_button_html'] = delete_button_html.format(category.id) if category.goods_num == 0 else 'Невозможно удалить'

        data.append(category_data)

    return jsonify(data)


@app.route('/ajax/text/del/<string:text_id>', methods=['POST'])
def ajax_del_user_method(text_id):
    result = 'error'

    if not text_id and auth_check():
        return result

    target_text: Text = Text.objects(id=text_id).first()
    if target_text:
        target_text.delete()

    result = 'ok'

    return result


@app.route('/shops', methods=['GET', 'POST'])
def shops_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        search = request.args.get('search')
        if not search:
            search = ''

        if user.rank != 0:
            result = user.get_access('/shops')
            if result:
                return make_response(redirect(result))

        if not user:
            return None

        if request.method == 'POST':

            search = request.form.get('search')

            if search:
                return make_response(redirect('/shops?search={0}'.format(search)))

            page = request.form.get('page')
            if page:
                try:
                    page = int(page)
                    return make_response(redirect('/shops?p={0}'.format(page)))
                except ValueError:
                    return make_response(redirect('/shops'))

        else:
            end = page * 20
            start = end - 20
            shops_len = UserRegister.objects(is_reserved=False).count() if not search else \
                UserRegister.objects(login__icontains=search).count()

            p_all = ceil(shops_len / 20) if ceil(shops_len / 20) != 0 else 1

            if start > shops_len:
                start = shops_len

            if end > shops_len:
                end = shops_len

            shops = UserRegister.objects(is_reserved=False)[start:end].order_by('positional_id') if not search else \
                UserRegister.objects(login__icontains=search)
            result = render_template(template_name_or_list='shops.html', p=page, rows=shops, p_all=p_all,
                                     u_all=shops_len, user=user, search=search)

    return result


@app.route('/nullify_balance', methods=['GET', 'POST'])
def nullify_balance():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if user.rank != 0:
            result = user.get_access('/nullify_balance')
            if result:
                return make_response(redirect(result))

        reg_users = UserRegister.objects(Q(balance__gt=0) | Q(input_sum__gt=0) | Q(output_sum__gt=0)
                                         | Q(earned_sum__gt=0) | Q(structure_earned_sum__gt=0))

        print(reg_users.count())
        for reg in reg_users:
            reg.balance = 0
            reg.input_sum = 0
            reg.output_sum = 0
            reg.earned_sum = 0
            reg.structure_earned_sum = 0
            reg.my_goods_earned_sum = dict()
            reg.goods_structures_earned_sum = dict()
            reg.save()
        core: Core = Core.objects.first()
        core.bot_balance = 0
        core.save()
        result = make_response(redirect('/'))
    return result


from ..core.db_model.order import Order
from ..core.db_model.field import Photo
from ..core.db_model.structure import ProductHistory


@app.route('/drop_structure', methods=['GET', 'POST'])
def drop_structure():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if user.rank != 0:
            result = user.get_access('/drop_structure')
            if result:
                return make_response(redirect(result))

        core: Core = Core.objects.first()
        core.bot_counter = 1
        core.bot_counter_2 = 1
        core.tgs_bot_counter = 0
        core.positional_id = 1
        core.save()
        UserRegister.drop_collection()

        # Category.drop_collection()

        Field.drop_collection()
        Frequent.drop_collection()
        Order.drop_collection()
        Photo.drop_collection()
        Product.drop_collection()
        ProductHistory.drop_collection()
        ProductStructureUser.drop_collection()
        TgUser.drop_collection()

        result = make_response(redirect('/'))
    return result


from ..binary_referral_system.referrals_indent import graph_data


@app.route('/graph', methods=['GET', 'POST'])
def graph_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if user.rank != 0:
            result = user.get_access('/graph')
            if result:
                return make_response(redirect(result))

        if not user:
            return None

        user_id = request.args.get('id')
        if user_id:
            reg_user = UserRegister.objects(id=user_id).first()
        else:
            reg_user = UserRegister.objects(positional_id=1).first()

        admin_panel = True

        data = graph_data(reg_user, admin_panel) if reg_user else None
        children_count = str(data).count("children")

        result = render_template(template_name_or_list='graph.html',  data=data, children_count=children_count, user=user)

    return result


@app.route('/frequents', methods=['GET', 'POST'])
def frequents_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/frequents')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            frequents_len = Frequent.objects.count()

            p_all = ceil(frequents_len / 20) if ceil(frequents_len / 20) != 0 else 1

            if start > frequents_len:
                start = frequents_len

            if end > frequents_len:
                end = frequents_len

            frequents = Frequent.objects[start:end]
            result = render_template(template_name_or_list='frequents.html', p=page, rows=frequents, p_all=p_all,
                                     u_all=frequents_len, user=user)

    return result


@app.route('/frequent', methods=['GET', 'POST'])
def frequent_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        frequents = Frequent.objects
        languages = Language.objects

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/frequents')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            new_text = Frequent()

            for lang in languages:
                question = request.form.get('question_lang_{0}'.format(lang.tag))
                if question:
                    new_text.question_lang[lang.tag] = question
                else:
                    error = 'Вы не ввели вопрос!'
                    result = make_response(render_template('frequent.html', error=error, user=user, languages=languages))
                    return result

                answer = request.form.get('answer_lang_{0}'.format(lang.tag))
                if answer:
                    new_text.answer_lang[lang.tag] = answer
                else:
                    error = 'Вы не ввели ответ!'
                    result = make_response(render_template('frequent.html', error=error, user=user, languages=languages))
                    return result
            new_text.save()
            result = make_response(redirect('/frequents'))
        else:
            result = render_template(template_name_or_list='frequent.html', user=user, languages=languages)

    return result


@app.route('/comments', methods=['GET', 'POST'])
def comments_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/comments')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:

            end = page * 20
            start = end - 20
            comments_len = Comment.objects.count()

            p_all = ceil(comments_len / 20) if ceil(comments_len / 20) != 0 else 1

            if start > comments_len:
                start = comments_len

            if end > comments_len:
                end = comments_len

            comments = Comment.objects()
            result = render_template(template_name_or_list='comments.html', rows=comments, p=page, p_all=p_all,
                                     u_all=comments_len, user=user)

    return result


@app.route('/comment/send/<string:comment_id>')
def send_comment(comment_id):
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/comments')
            if result:
                return make_response(redirect(result))

        target_comment = Comment.objects(id=comment_id).first()
        if not target_comment:
            return None
        target_comment.is_moderated = True
        target_comment.save()
        result = make_response(redirect('/comments'))

    return result


@app.route('/comment/del/<string:comment_id>', methods=['GET', 'POST'])
def del_comment(comment_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/comments')
            if result:
                return make_response(redirect(result))
        result = make_response(redirect('/'))

        if not comment_id:
            return result

        target_comment = Comment.objects(id=comment_id).first()

        if target_comment:
            target_comment.delete()
            result = make_response(redirect('/comments'))

    return result


@app.route('/frequent/edit/<string:frequent_id>', methods=['GET', 'POST'])
def edit_frequent(frequent_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/frequents')
            if result:
                return make_response(redirect(result))

        target_frequent = Frequent.objects(id=frequent_id).first()

        if not target_frequent:
            return None

        if request.method == 'POST':
            for lang in Language.objects:
                question = request.form.get('question_lang_{0}'.format(lang.tag))
                if question:
                    target_frequent.question_lang[lang.tag] = question
                else:
                    error = 'Вы не ввели вопрос!({0})'.format(lang.name)
                    result = make_response(render_template('frequent.html', target_frequent=target_frequent, error=error, user=user,
                                                           languages=Language.objects))
                    return result

                answer = request.form.get('answer_lang_{0}'.format(lang.tag))
                if answer:
                    target_frequent.answer_lang[lang.tag] = answer
                else:
                    error = 'Вы не ввели ответ!({0})'.format(lang.name)
                    result = make_response(render_template('frequent.html', target_frequent=target_frequent,
                                                           error=error, user=user,
                                                           languages=Language.objects))
                    return result
            target_frequent.save()
            result = make_response(redirect('/frequents'))
        else:
            result = render_template(template_name_or_list='frequent.html',
                                     target_frequent=target_frequent,
                                     languages=Language.objects, user=user)

    return result


@app.route('/frequent/del/<string:frequent_id>', methods=['GET', 'POST'])
def del_frequent(frequent_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/frequents')
            if result:
                return make_response(redirect(result))

        if not frequent_id:
            return result

        target_frequent = Frequent.objects(id=frequent_id).first()

        if target_frequent:
            target_frequent.delete()
            result = make_response(redirect('/frequents'))

    return result


@app.route('/text', methods=['GET', 'POST'])
def text_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        languages = Language.objects

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/texts')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            new_text = Text()

            tag = request.form.get('tag')
            if tag:
                new_text.tag = tag
            else:
                error = 'Вы не ввели тег!'
                result = make_response(render_template('text.html', languages=languages, error=error, user=user,
                                                       applying_ways=config.APPLYING_WAYS))
                return result

            for language in languages:
                value = request.form.get(language.tag + '_value')
                if value:
                    new_text.values[language.tag] = value
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template('text.html', languages=languages, error=error, user=user,
                                                           applying_ways=config.APPLYING_WAYS))
                    return result

            applying_way = request.form.get('applying_way')
            new_text.applying_way = applying_way
            new_text.save()
            result = make_response(redirect('/texts'))
        else:
            result = render_template(template_name_or_list='text.html', languages=languages,
                                     applying_ways=config.APPLYING_WAYS, user=user)

    return result


@app.route('/text/edit/<string:text_id>', methods=['GET', 'POST'])
def edit_text(text_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/languages'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if not text_id or not user:
            return result

        if user.rank != 0:
            result = user.get_access('/texts')
            if result:
                return make_response(redirect(result))

        languages = Language.objects

        target_text = Text.objects(id=text_id).first()

        if not target_text:
            return None

        if request.method == 'POST':
            tag = request.form.get('tag')
            if tag:
                target_text.tag = tag
            else:
                error = 'Вы не ввели тег!'
                result = make_response(render_template('text.html', target_text=target_text, languages=languages,
                                                       error=error, user=user))
                return result

            for language in languages:
                value = request.form.get(language.tag + '_value')
                if value:
                    target_text.values[language.tag] = value
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template('text.html', target_text=target_text, languages=languages,
                                                           error=error, user=user))
                    return result
            target_text.save()
            result = make_response(redirect('/texts'))
        else:
            result = render_template(template_name_or_list='text.html',
                                     target_text=target_text,
                                     languages=languages, user=user)

    return result


@app.route('/text/del/<string:text_id>', methods=['GET', 'POST'])
def del_text(text_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/texts'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/texts')
            if result:
                return make_response(redirect(result))

        if not text_id:
            return result

        target_text = Text.objects(id=text_id).first()

        if target_text:
            target_text.delete()
            result = make_response(redirect('/texts'))

    return result


@app.route('/mailing', methods=['GET', 'POST'])
def mailing():
    result = make_response(redirect('/login'))
    session_id = request.cookies.get('session_id', None)
    user = User.objects(session_id=session_id).first()
    if auth_check():
        error = None
        if request.method == 'POST':
            core = Core.objects.first()
            if core:
                message = Message()
                message.status = request.form.get('status')
                message.text = request.form.get('message')
                message.save()

                core.update(push__messages=message)
                core.reload()

        tg_users = TgUser.objects
        result = render_template(template_name_or_list='mailing.html',
                                 users=tg_users,
                                 error=error)

    return result


@app.route('/login', methods=['GET', 'POST'])
def login():
    result = make_response(render_template('login.html'))

    if not User.objects().first():
        user: User = User()
        user.login = 'admin'
        user.password = hashlib.md5('qwerty12345'.encode('utf-8')).hexdigest()
        user.save()

    if request.method == 'POST':
        user_login = request.form['login']
        password = request.form['password']

        user = User.objects(login=user_login).first()

        if user and user.password == hashlib.md5(password.encode('utf-8')).hexdigest():
            hash_str = (user_login + password + str(random.randrange(111, 999))).encode('utf-8')
            hashed_pass = hashlib.md5(hash_str).hexdigest()
            session_id = hashed_pass
            time_alive = time.time() + (86400 * 7)

            user.session_id = session_id
            user.time_alive = time_alive
            user.save()

            result = make_response(redirect('/'))
            result.set_cookie('session_id', session_id)
        else:
            error = 'Пользователь с таким логином/паролем не найден!'
            result = make_response(render_template('login.html', error=error, user=user))
    else:
        if auth_check():
            result = make_response(redirect(''))

    return result


@app.route('/logout')
def logout():
    result = make_response(redirect('/login'))

    session_id = request.cookies.get('session_id', None)
    if session_id:
        result.set_cookie('session_id', 'deleted', expires=time.time()-100)

    return result


def auth_check():
    result = False

    session_id = request.cookies.get('session_id', None)
    if session_id:
        user = User.objects(session_id=session_id).first()
        if user:
            result = True

    return result


@app.route('/categories', methods=['GET', 'POST'])
def categories_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:

            categories = Category.objects(parent_category=None)
            result = render_template(template_name_or_list='categories.html', p=page, rows=categories, user=user)

    return result


@app.route('/category', methods=['GET', 'POST'])
def category_method():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        languages = Language.objects

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            new_category = Category()

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    new_category.values[language.tag] = name
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template(template_name_or_list='category.html',
                                                           languages=languages,
                                                           error=error, user=user))
                    return result

            new_category.is_moderated = True
            new_category.save()
            result = make_response(redirect('/categories'))
        else:
            result = render_template(template_name_or_list='category.html', user=user, languages=languages)

    return result


@app.route('/category/moderate_off/<string:category_id>', methods=['GET', 'POST'])
def moderate_off(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/languages'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        if not category_id:
            return result

        target_category: Category = Category.objects(id=category_id).first()

        target_category.is_moderated = False
        target_category.save()
        for p in Product.objects(category=target_category):
            p.is_active = False
            p.save()

        if not target_category.parent_category:
            result = make_response(redirect('/categories'))
        else:
            result = make_response(redirect('/sub_categories/{0}'.format(target_category.parent_category.id)))

    return result


@app.route('/category/moderate_on/<string:category_id>', methods=['GET', 'POST'])
def moderate_on(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/categories'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        if not category_id:
            return result

        target_category: Category = Category.objects(id=category_id).first()

        target_category.is_moderated = True
        target_category.save()
        if target_category.creator:
            tg_users: TgUser = TgUser.objects(auth_login=target_category.creator.login)
            for tg in tg_users:
                msg = bot.send_message(tg.user_id, locale_text(tg.user_lang, 'category_moderate_msg').
                                       format(target_category.values.get(tg.user_lang)), parse_mode='markdown')
                tg.msgs_to_del.append(msg.message_id)
                tg.save()

        if not target_category.parent_category:
            result = make_response(redirect('/categories'))
        else:
            result = make_response(redirect('/sub_categories/{0}'.format(target_category.parent_category.id)))

    return result


@app.route('/category/edit/<string:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/categories'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if not category_id:
            return result

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        target_category = Category.objects(id=category_id).first()
        languages = Language.objects
        categories = Category.objects.order_by('-priority')
        # categories.remove(target_category)
        if not target_category:
            return None

        if request.method == 'POST':
            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    target_category.values[language.tag] = name
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template(template_name_or_list='category.html',
                                                           languages=languages,
                                                           categories=categories,
                                                           error=error, user=user,
                                                           target_category=target_category))
                    return result

            parent = request.form.get('parent')
            if parent == '0':
                pass
            elif parent == '1':
                if target_category.parent_category:
                    target_category.parent_category = None
                    target_category.save()
            elif parent:
                parent: Category = Category.objects(id=parent).first()
                if parent:
                    if all_parent_categories(parent).count(target_category) == 0:
                        target_category.parent_category = parent
                        target_category.save()

                    else:
                        error = 'Ошибка! Невозможно назначить родительскую категорию'
                        result = make_response(
                            render_template(user=user, template_name_or_list='category.html', error=error,
                                            languages=languages, categories=categories,
                                            target_category=target_category))
                        return result
                else:
                    error = 'Такой категории не сущестувет'
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories,
                                        target_category=target_category))
                    return result

            target_category.save()
            result = make_response(redirect('/categories'))
        else:
            result = render_template(template_name_or_list='category.html',
                                     target_category=target_category, user=user, languages=languages,
                                     categories=categories)

    return result


@app.route('/ajax/category/del/<string:category_id>', methods=['GET', 'POST'])
def del_category(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/categories'))

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not category_id or not user:
            return result

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        target_category: Category = Category.objects(id=category_id).first()

        for category in Category.objects(parent_category=target_category):

            category.parent_category = target_category.parent_category if target_category.parent_category else None
            category.save()

        target_category.delete()

        result = 'ok'

    return result


@app.route('/view/img/tg_documents/photos/<string:path>', methods=['GET', 'POST'])
def view_img(path):
    path = 'tg_documents/photos/'+path
    img_path = path.split('/')
    root_dir = os.path.join(app.root_path)
    return send_from_directory(os.path.join(root_dir, 'static', img_path[0], img_path[1]), img_path[2])


@app.route('/advert/good_day/<string:advert_id>', methods=['GET', 'POST'])
def good_day_method(advert_id):
    result = make_response(redirect('/login'))
    if auth_check():

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        old_good_day: Product = Product.objects(is_day_good=True).first()
        if old_good_day:
            old_good_day.is_day_good = False
            old_good_day.save()

        target_advert: Product = Product.objects(id=advert_id).first()
        target_advert.is_day_good = True
        target_advert.save()


        result = make_response(redirect('/publicated_adverts'))

    return result


@app.route('/advert/good_day_del/<string:advert_id>', methods=['GET', 'POST'])
def good_day_method_del(advert_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        target_advert: Product = Product.objects(id=advert_id).first()
        target_advert.is_day_good = False
        target_advert.save()

        result = make_response(redirect('/publicated_adverts'))

    return result


@app.route('/adverts', methods=['GET', 'POST'])
def adverts_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            adverts_len = Product.objects(Q(is_accepted=False) & Q(is_canceled=False) & Q(is_active=True)).count()

            p_all = ceil(adverts_len / 20) if ceil(adverts_len / 20) != 0 else 1

            if start > adverts_len:
                start = adverts_len

            if end > adverts_len:
                end = adverts_len

            adverts = Product.objects(Q(is_accepted=False) & Q(is_canceled=False) & Q(is_active=True))[start:end]
            result = render_template(template_name_or_list='adverts.html', p=page, rows=adverts, p_all=p_all,
                                     u_all=adverts_len, user=user)

    return result


@app.route('/advert/edit/<string:advert_id>', methods=['GET', 'POST'])
def edit_advert(advert_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/adverts'))
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if not advert_id or not user:
            return result

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        target_advert = Product.objects(id=advert_id).first()
        prod_user_id = request.args.get('id')
        if prod_user_id:
            prod_user = ProductStructureUser.objects(id=prod_user_id).first()
        else:
            prod_user = ProductStructureUser.objects(Q(structure=target_advert) & Q(positional_id=1)).first()

        data = graph_product_data(prod_user) if prod_user else None

        if request.method == 'POST':
            try:
                price = float(request.form['price'])
            except:
                error = 'Вы ввели не число!'
                result = make_response(render_template('advert.html', error=error, user=user, target_advert=target_advert,
                                                       data=data))
                return result

            if price:
                target_advert.price = price
                target_advert.save()
            else:
                error = 'Вы не ввели цену!'
                result = make_response(render_template('advert.html', error=error, user=user, target_advert=target_advert,
                                                       data=data))
                return result
            try:
                destributed_price = float(request.form['destributed_price'])
            except:
                error = 'Вы ввели не число!'
                result = make_response(render_template('advert.html', error=error, user=user, target_advert=target_advert,
                                                       data=data))
                return result

            if destributed_price:
                target_advert.destributed_price = destributed_price
                target_advert.save()
            else:
                error = 'Вы не ввели сумму распределения!'
                result = make_response(render_template('advert.html', error=error, user=user, target_advert=target_advert,
                                                       data=data))
                return result

            name = request.form['name']
            if name:
                target_advert.name = name
                target_advert.save()
            else:
                error = 'Вы не ввели названия !'
                result = make_response(render_template('advert.html', error=error, user=user, target_advert=target_advert,
                                                       data=data))
                return result

            description = request.form['description']
            if description:
                target_advert.description = description
                target_advert.save()
            else:
                error = 'Вы не ввели описание!'
                result = make_response(render_template('advert.html', error=error, user=user, target_advert=target_advert,
                                                       data=data))
                return result

            result = make_response(redirect('/adverts'))
        else:
            if target_advert:
                result = render_template(template_name_or_list='advert.html',
                                         target_advert=target_advert, user=user,
                                         data=data)

    return result


@app.route('/advert/apply/<string:advert_id>', methods=['GET', 'POST'])
def apply_advert(advert_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/adverts'))

        if not advert_id:
            return result

        advert: Product = Product.objects(id=advert_id).first()
        advert.is_accepted = True
        advert.save()

        category = advert.category

        while category:
            category.goods_num += 1
            category.save()
            category = category.parent_category

        reg_user: UserRegister = advert.creator

        tg_users: TgUser = TgUser.objects(auth_login=reg_user.login)
        for tg in tg_users:
            msg = bot.send_message(tg.user_id, locale_text(tg.user_lang, 'prod_moderate_msg').
                                   format(advert.fields.get('name')), parse_mode='markdown')
            tg.msgs_to_del.append(msg.message_id)
            tg.save()

    return result


@app.route('/advert/cencel/<string:advert_id>', methods=['GET', 'POST'])
def cencel_advert(advert_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/adverts'))
        user_lang = 'rus'
        if not advert_id:
            return result

        advert: Product = Product.objects(id=advert_id).first()
        advert.is_canceled = True
        advert.save()
    return result


@app.route('/advert/delete/<string:advert_id>', methods=['GET', 'POST'])
def del_advert(advert_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/adverts'))
        user_lang = 'rus'

        if not advert_id:
            return result

        advert: Product = Product.objects(id=advert_id).first()
        category = advert.category
        if advert.is_active:
            while category:
                category.goods_num -= 1
                category.save()
                category = category.parent_category

        advert.is_active = False
        advert.save()

    # bot.send_message(advert.user.user_id, locale_text(user_lang, 'advert_not_apply_msg'))
    # advert.delete()

    return result


@app.route('/publicated_adverts', methods=['GET', 'POST'])
def publicated_adverts_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            publicated_adverts_len = Product.objects(Q(is_accepted=True) & Q(is_canceled=False) & Q(is_active=True)).count()

            p_all = ceil(publicated_adverts_len / 20) if ceil(publicated_adverts_len / 20) != 0 else 1

            if start > publicated_adverts_len:
                start = publicated_adverts_len

            if end > publicated_adverts_len:
                end = publicated_adverts_len

            publicated_adverts = Product.objects(Q(is_accepted=True) & Q(is_canceled=False) & Q(is_active=True))[start:end]
            result = render_template(template_name_or_list='publicated_adverts.html', p=page, rows=publicated_adverts, p_all=p_all,
                                     u_all=publicated_adverts_len, user=user)

    return result


@app.route('/publicated_advert/delete/<string:publicated_advert_id>', methods=['GET', 'POST'])
def del_publicated_advert(publicated_advert_id):

    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/publicated_adverts'))
        user_lang = 'rus'

        if not publicated_advert_id:
            return result

        publicated_advert: Product = Product.objects(id=publicated_advert_id).first()
        publicated_advert.delete()

    return result


@app.route('/cancel_adverts', methods=['GET', 'POST'])
def cancel_adverts_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            cancel_adverts_len = Product.objects(Q(is_accepted=False) & Q(is_canceled=True) & Q(is_active=True)).count()

            p_all = ceil(cancel_adverts_len / 20) if ceil(cancel_adverts_len / 20) != 0 else 1

            if start > cancel_adverts_len:
                start = cancel_adverts_len

            if end > cancel_adverts_len:
                end = cancel_adverts_len

            cancel_adverts = Product.objects(Q(is_accepted=False) & Q(is_canceled=True) & Q(is_active=True))[start:end]
            result = render_template(template_name_or_list='cancel_adverts.html', p=page, rows=cancel_adverts, p_all=p_all,
                                     u_all=cancel_adverts_len, user=user)

    return result


@app.route('/cancel_advert/delete/<string:cancel_advert_id>', methods=['GET', 'POST'])
def del_cancel_advert(cancel_advert_id):
    result = make_response(redirect('/login'))
    if auth_check():
        result = make_response(redirect('/cancel_adverts'))
        user_lang = 'rus'

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/adverts')
            if result:
                return make_response(redirect(result))

        if not cancel_advert_id:
            return result

        cancel_advert: Product = Product.objects(id=cancel_advert_id).first()
        cancel_advert.delete()

    return result


@app.route('/fields', methods=['GET', 'POST'])
def fields_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/fields')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            # for f in Field.objects:
            #     f.is_moderated = False
            #     f.save()

            end = page * 20
            start = end - 20
            fields_len = Field.objects(is_moderated=False).count()

            p_all = ceil(fields_len / 20) if ceil(fields_len / 20) != 0 else 1

            if start > fields_len:
                start = fields_len

            if end > fields_len:
                end = fields_len

            fields = Field.objects(Q(is_moderated=False) & Q(in_active=True))[start:end]
            result = render_template(template_name_or_list='fields.html', p=page, rows=fields, p_all=p_all,
                                     u_all=fields_len, user=user)

    return result


@app.route('/field/moderate/<string:field_id>', methods=['GET', 'POST'])
def modarate_method(field_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        result = make_response(redirect('/fields'))

        if not field_id or not user:
            return result

        if user.rank != 0:
            result = user.get_access('/fields')
            if result:
                return make_response(redirect(result))

        target_field: Field = Field.objects(id=field_id).first()

        # categories.remove(target_category)

        if not target_field:
            return None

        if request.method == 'POST':

            for language in languages:
                name = request.form.get(language.tag + '_names')
                if name:
                    target_field.names[language.tag] = name
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template(template_name_or_list='field.html',
                                                           languages=languages,
                                                           error=error, user=user,
                                                           target_field=target_field))
                    return result

                # message = request.form.get(language.tag + '_message')
                # if name:
                #     target_field.message[language.tag] = message
                #     print(target_field.message)
                # else:
                #     error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                #     result = make_response(render_template(template_name_or_list='field.html',
                #                                            languages=languages,
                #                                            error=error, user=user,
                #                                            target_field=target_field))
                #     return result

            target_field.is_moderated = True
            target_field.save()
            print(target_field.message)

            reg_user: UserRegister = target_field.user

            tg_users: TgUser = TgUser.objects(auth_login=reg_user.login)
            for tg in tg_users:
                msg = bot.send_message(tg.user_id, locale_text(tg.user_lang, 'field_moderate_msg').
                                 format(target_field.names.get(tg.user_lang)), parse_mode='markdown')
                tg.msgs_to_del.append(msg.message_id)
                tg.save()

            result = make_response(redirect('/fields'))
        else:
            result = render_template(template_name_or_list='field.html',
                                     target_field=target_field, user=user, languages=languages)

    return result


# @app.route('/attendance', methods=['GET', 'POST'])
# def attendance_method():
#     result = make_response(redirect('/login'))
#     if auth_check():
#         page = int(request.args.get('p', None)) if request.args.get('p', None) else 1
#
#         session_id = request.cookies.get('session_id', None)
#         user = User.objects(session_id=session_id).first()
#
#         if not user:
#             return None
#
#         if request.method == 'POST':
#             pass
#         else:
#             end = page * 20
#             start = end - 20
#             attendance_len = Product.objects.count()
#
#             p_all = ceil(attendance_len / 20) if ceil(attendance_len / 20) != 0 else 1
#
#             if start > attendance_len:
#                 start = attendance_len
#
#             if end > attendance_len:
#                 end = attendance_len
#
#             attendance = Product.objects[start:end]
#             result = render_template(template_name_or_list='attendance.html', p=page, rows=attendance, p_all=p_all,
#                                      u_all=attendance_len, user=user)
#
#     return result
#
#
# @app.route('/attendance/view/<string:structure_id>', methods=['GET', 'POST'])
# def attendance_view_method(structure_id):
#     structure: Product = Product.objects(id=structure_id).first()
#     result = make_response(redirect('/login'))
#     if auth_check():
#         page = int(request.args.get('p', None)) if request.args.get('p', None) else 1
#
#         session_id = request.cookies.get('session_id', None)
#         user = User.objects(session_id=session_id).first()
#
#         if not user:
#             return None
#
#
#         if request.method == 'POST':
#             pass
#         else:
#             end = page * 20
#             start = end - 20
#             structure_users_len = ProductStructureUser.objects(structure=structure).count()
#
#             p_all = ceil(structure_users_len / 20) if ceil(structure_users_len / 20) != 0 else 1
#
#             if start > structure_users_len:
#                 start = structure_users_len
#
#             if end > structure_users_len:
#                 end = structure_users_len
#
#             attendance = ProductStructureUser.objects(structure=structure).order_by('positional_id')
#             users: dict = dict()
#             for i in attendance:
#                 tg_user: TgUser = TgUser.objects(user_id=i.user_id).first()
#                 users[tg_user.user_id] = {'username': tg_user.username,
#                                           'first_name': tg_user.first_name,
#                                           'second_name': tg_user.last_name,
#                                           'balance': tg_user.balance}
#             result = render_template(template_name_or_list='attendance_users.html', p=page, rows=attendance, p_all=p_all,
#                                      u_all=structure_users_len, users=users, user=user)
#
#     return result


@app.route('/generate_tgs_for_unlogin', methods=['GET', 'POST'])
def mega_generator_100k():
    core: Core = Core.objects.first()
    for reg_user in UserRegister.objects:
        tgs = TgUser.objects(auth_login=reg_user.login)

        if not tgs:
            core.tgs_bot_counter -= 1
            core.save()
            new_tg_bot = TgUser()

            new_tg_bot.user_id = core.tgs_bot_counter
            new_tg_bot.username = 'mrdarky'
            new_tg_bot.login = reg_user.login
            new_tg_bot.auth_login = reg_user.login
            new_tg_bot.is_authed = True
            new_tg_bot.auth_password = reg_user.password
            new_tg_bot.first_name = 'bot{0}'.format(core.tgs_bot_counter)
            new_tg_bot.last_name = 'bot{0}'.format(core.tgs_bot_counter)
            new_tg_bot.save()

    return make_response(redirect('/'))


from .db_model.logs import GenerateLogs, DistributeLogs


def generate_bots_function(num, core):
    for i in range(num):
        time_1 = datetime.datetime.now()
        core.bot_counter_2 += 1
        core.save()
        reg_user = UserRegister()
        reg_user.login = 'bot_{0}@gmail.com'.format(core.bot_counter_2)
        reg_user.password = 'qwer1234'
        reg_user.is_main_structure = True
        reg_user.save()
        referrals_indent(None, reg_user)
        log = GenerateLogs()
        log.date = datetime.datetime.now() + datetime.timedelta(hours=3)
        text = 'Пользователь: {0}, Встал на место: {1}, В линию: {2}, Процент: {3}'.format(
            reg_user.login, reg_user.positional_id, reg_user.level, "%.2f" % reg_user.percent
        )
        log.result = text
        log.save()
        time_2 = datetime.datetime.now()

        delta = time_2 - time_1

        print('timedelta seconds:{0}; microseconds: {1}'.format(delta.seconds, delta.microseconds))


from ..tg_bot.bot_states import BotStates
def reversation_users_function(num, core):
    for i in range(num):
        reg_user = UserRegister()
        reg_user.login = '---'
        reg_user.password = ''
        reg_user.is_main_structure = True
        reg_user.is_reserved = True
        reg_user.save()
        referrals_indent(None, reg_user)
        BotStates.create_default_fields(reg_user, locale_text)


@app.route('/generate_test', methods=['GET', 'POST'])
def generate_test():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        reg_user_number = UserRegister.objects.count()
        core: Core = Core.objects.first()

        if user.rank != 0:
            result = user.get_access('/generate_test')
            if result:
                return make_response(redirect(result))

        if not user:
            return None

        if request.method == 'POST':
            num = request.form.get('num')
            if num:
                try:
                    num = int(num)
                    time_1 = datetime.datetime.now()

                    generating = threading.Thread(target=generate_bots_function, args=(num, core))
                    generating.daemon = True
                    generating.start()

                    time_2 = datetime.datetime.now()
                    print('timedelta seconds: {0}, microseconds: {1}'.format((time_2-time_1).seconds, (time_2-time_1).microseconds))

                    return make_response(render_template(template_name_or_list='generate_logs.html', user=user,
                                                         reg_user_number=reg_user_number,
                                                         apply='{0} пользователей добавлено'.format(num)))
                except ValueError:
                    pass

        else:
            result = make_response(render_template(template_name_or_list='test.html', user=user,
                                                   reg_user_number=reg_user_number))

    return result


@app.route('/del_generate_logs', methods=['GET', 'POST'])
def del_generate_logs():
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/del_generate_logs')
            if result:
                return make_response(redirect(result))

        GenerateLogs.drop_collection()

        result =  make_response(redirect('/generate_test'))

    return result


@app.route('/generate_logs', methods=['GET', 'POST'])
def generate_logs():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/generate_logs')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            texts = GenerateLogs.objects
            result = render_template(template_name_or_list='generate_logs.html', rows=texts, user=user)

    return result


from ..web_personal_cabinet.service import distribute_percents as dp
from ..web_personal_cabinet.service import buy_good_take_place as bg


@app.route('/distribute_test', methods=['GET', 'POST'])
def distribute_test():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        reg_user_number = UserRegister.objects(positional_id__gt=0).count()
        core: Core = Core.objects.first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/distribute_test')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':

            good = request.form.get('good')
            if good != '0':
                good = Product.objects(id=good).first()
            else:
                good = None

            positional_id = request.form.get('positional_id')
            if positional_id:
                try:
                    positional_id = int(positional_id)
                    reg_user: UserRegister = UserRegister.objects(positional_id=positional_id).first()

                    if not reg_user:
                        return make_response(render_template(template_name_or_list='distribute_test.html', user=user,
                                                             reg_user_number=reg_user_number,
                                                             error='Пользователь не найден'))

                    try:

                        if not good:
                            num = request.form.get('sum')
                            if num:
                                num = int(num)
                                reg_user.number_to_distribute = num
                                reg_user.save()
                                text = 'Распределение по главной сетке\n\n\n'
                                text += distribute_percents(reg_user)

                                log = DistributeLogs()
                                log.date = datetime.datetime.now() + datetime.timedelta(hours=3)
                                log.result = text
                                # log.structure = good
                                log.save()

                                return make_response(render_template(template_name_or_list='result.html',
                                                                     user=user,
                                                                     result=text))
                        else:
                            text = locale_text('rus', 'destribute_msg')

                            creator = good.creator

                            creator.balance += (float(good.fields.get('price')) - float(
                                good.fields.get('reward')))
                            creator.earned_sum += (float(good.fields.get('price')) - float(
                                good.fields.get('reward')))
                            if creator.my_goods_earned_sum.get(str(good.id)):
                                creator.my_goods_earned_sum[str(good.id)] += (float(good.fields.get('price')) - float(
                                    good.fields.get('reward')))
                            else:
                                creator.my_goods_earned_sum[str(good.id)] = (float(good.fields.get('price')) - float(
                                    good.fields.get('reward')))
                            creator.save()

                            reg_user.number_to_distribute = float(good.fields.get('reward'))
                            reg_user.save()
                            text_2 = 'Распределение по сетке товара "{0}"\n\n\n'.format(good.fields.get('name'))

                            if reg_user.is_main_structure:
                                structure_user = bg(good, reg_user)
                                text_2 += 'Пользователь: {0}, Встал на место: {1}, В линию: {2}, Процент: {3}\n\n'.format(
                                    structure_user.user.login, structure_user.positional_id, structure_user.level,
                                    "%.2f" % structure_user.percent
                                )
                                text_2 += dp(reg_user, bot, structure_user, text=text)
                            else:
                                text_2 += dp(reg_user, bot, text=text, structure=good)

                            log = DistributeLogs()
                            log.date = datetime.datetime.now() + datetime.timedelta(hours=3)
                            log.result = text_2
                            # log.structure = good
                            log.save()
                            return make_response(render_template(template_name_or_list='result.html',
                                                                 user=user,
                                                                 result=text_2))

                    except ValueError:
                        return make_response(render_template(template_name_or_list='distribute_test.html', user=user,
                                                             reg_user_number=reg_user_number,
                                                             error='Введите число'))

                except ValueError:
                    return make_response(render_template(template_name_or_list='distribute_test.html', user=user,
                                                         reg_user_number=reg_user_number,
                                                         error='Введите число'))
        else:
            goods = Product.objects
            result = make_response(render_template(template_name_or_list='distribute_test.html', user=user,
                                                   reg_user_number=reg_user_number, goods=goods))

    return result


@app.route('/delete_distribute_logs', methods=['GET', 'POST'])
def delete_distribute_logs():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/delete_distribute_logs')
            if result:
                return make_response(redirect(result))

        DistributeLogs.drop_collection()

        result = make_response(redirect('/distribute_test'))

    return result


@app.route('/distribute_logs', methods=['GET', 'POST'])
def distribute_logs():
    result = make_response(redirect('/login'))

    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/distribute_logs')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            texts = DistributeLogs.objects.order_by('-date')
            result = render_template(template_name_or_list='distributed_logs.html', logs=texts, user=user)

    return result

def generate_reg_users_poolling(r):
    core: Core = Core.objects.first()
    for i in range(r):
        core.bot_counter_2 += 1
        core.save()
        reg_user = UserRegister()
        reg_user.login = 'bot_{0}@gmail.com'.format(core.bot_counter_2)
        reg_user.password = 'qwer1234'
        reg_user.is_main_structure = True
        reg_user.save()
        referrals_indent(None, reg_user)


def distribute_percents(reg_user: UserRegister):
    core = Core.objects.first()
    distribute_user_percents = 0

    text: str = str()

    core.bot_balance += reg_user.number_to_distribute * core.bot_comission
    core.save()

    text += 'Комиссия бота: {0}\n\n\n'.format(reg_user.number_to_distribute * core.bot_comission)

    # if reg_user.parent:
    #     parent: UserRegister = reg_user.parent
    #     parent.balance += reg_user.number_to_distribute * core.parent_comission
    #     parent.save()
    # else:
    #     core.bot_balance += reg_user.number_to_distribute * core.parent_comission
    #     core.save()

    reg_user.number_to_distribute = reg_user.number_to_distribute - \
                                    reg_user.number_to_distribute*core.bot_comission
    reg_user.save()
    # parent_user = user
    if len(find_parents_ids(reg_user)) != 0:
        text += 'Вознаграждения по структуре\n\n'
        date_1 = datetime.datetime.now()
        for parent_id in find_parents_ids(reg_user):
            parent_user: UserRegister = UserRegister.objects(id=parent_id).first()
            distribute_user_percents += parent_user.percent

        date_2 = datetime.datetime.now()

        print('timedelta_1: {0}'.format((date_2-date_1).microseconds))

        x = float(reg_user.number_to_distribute / distribute_user_percents)
        date_3 = datetime.datetime.now()

        for parent_id in find_parents_ids(reg_user):
            parent_user: UserRegister = UserRegister.objects(id=parent_id).first()
            # if parent_user.parent_referrals_user_id:
            # parent_user = User.objects(user_id=parent_user.parent_referrals_user_id).first()
            parent_user.balance += x * parent_user.percent
            parent_user.earned_sum += x * parent_user.percent
            parent_user.structure_earned_sum += x * parent_user.percent
            parent_user.save()

            text += 'Пользователь: {0}\n' \
                    'Номер в структуре: {1}\n' \
                    'Вознаграждение {2}\n\n'.format(parent_user.login, parent_user.positional_id,
                                                    x * parent_user.percent)

        date_4 = datetime.datetime.now()
        print('timedelta_2: {0}'.format((date_4-date_3).microseconds))

    else:

        reg_user.balance += reg_user.number_to_distribute
        reg_user.earned_sum += reg_user.number_to_distribute
        reg_user.structure_earned_sum += reg_user.number_to_distribute
        reg_user.save()

        text += 'Пользователей для распределения не найдено сумма {0} зачислена пользователю {1} Номер в структуре{2}'.\
            format(reg_user.number_to_distribute, reg_user.login, reg_user.positional_id)

    reg_user.number_to_distribute = 0
    reg_user.save()

    return text


@app.route('/sub_categories/category/edit/<string:category_id>', methods=['GET', 'POST'])
def edit_subcategory(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        result = make_response(redirect('/categories'))

        if not category_id or not user:
            return result

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        target_category = Category.objects(id=category_id).first()
        categories = Category.objects().order_by('-priority')
        # categories.remove(target_category)

        if not target_category:
            return None

        if request.method == 'POST':

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    target_category.values[language.tag] = name
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template(template_name_or_list='category.html',
                                                           languages=languages,
                                                           error=error, user=user, categories=categories,
                                                           target_category=target_category))
                    return result

            parent = request.form.get('parent')
            if parent == '0':
                pass
            elif parent == '1':
                if target_category.parent_category:
                    target_category.parent_category = None
                    target_category.save()
            elif parent:
                parent: Category = Category.objects(id=parent).first()
                if parent:
                    if all_parent_categories(parent).count(target_category) == 0:
                        target_category.parent_category = parent
                        target_category.save()

                    else:
                        error = 'Ошибка! Невозможно назначить родительскую категорию'
                        result = make_response(
                            render_template(user=user, template_name_or_list='category.html', error=error,
                                            languages=languages, categories=categories,
                                            target_category=target_category))
                        return result
                else:
                    error = 'Такой категории не сущестувет'
                    result = make_response(
                        render_template(user=user, template_name_or_list='category.html', error=error,
                                        languages=languages, categories=categories,
                                        target_category=target_category))
                    return result

            target_category.save()
            if target_category.parent_category:
                result = make_response(redirect('/sub_categories/{0}'.format(target_category.parent_category.id)))
            else:
                result = make_response(redirect('/categories'))
        else:
            result = render_template(template_name_or_list='category.html',
                                     target_category=target_category, user=user, languages=languages,
                                     categories=categories,
                                     )

    return result


@app.route('/sub_categories/<string:category_id>', methods=['GET', 'POST'])
def subcategories_method(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        category = Category.objects(id=category_id).first()
        if not category:
            return None

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        if request.method == 'POST':
            pass
        else:
            categories = Category.objects(parent_category=category).order_by('-priority')
            result = render_template(user=user, template_name_or_list='categories.html', p=page, rows=categories, parent_category=category)

    return result


@app.route('/sub_category/<string:category_id>', methods=['GET', 'POST'])
def subcategory_method(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        category = Category.objects(id=category_id).first()

        if request.method == 'POST':
            new_category = Category()

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    new_category.values[language.tag] = name
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template(template_name_or_list='category.html',
                                                           languages=languages,
                                                           error=error, user=user))
                    return result

            new_category.is_moderated = True
            new_category.parent_category = category
            new_category.save()
            result = make_response(redirect('/sub_categories/{0}'.format(category.id)))
        else:
            result = render_template(template_name_or_list='category.html', user=user, languages=languages)

    return result


@app.route('/sub_categories/sub_category/<string:category_id>', methods=['GET', 'POST'])
def subcategory_method_2(category_id):
    result = make_response(redirect('/login'))
    languages = Language.objects
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        category = Category.objects(id=category_id).first()

        if request.method == 'POST':
            new_category = Category()

            for language in languages:
                name = request.form.get(language.tag + '_name')
                if name:
                    new_category.values[language.tag] = name
                else:
                    error = 'Вы не ввели значение  для языка: ' + language.name + '!'
                    result = make_response(render_template(template_name_or_list='category.html',
                                                           languages=languages,
                                                           error=error, user=user))
                    return result

            new_category.parent_category = category
            new_category.is_moderated = True
            new_category.save()
            result = make_response(redirect('/sub_categories/{0}'.format(category.id)))


        else:
            result = render_template(template_name_or_list='category.html',
                                     user=user, languages=languages)

    return result


@app.route('/sub_categories/category/del/<string:category_id>', methods=['GET', 'POST'])
def del_category_2(category_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/'))

        if not category_id:
            return result

        target_category: Category = Category.objects(id=category_id).first()

        for category in Category.objects(parent_category=target_category):
            category.parent_category = target_category.parent_category if target_category.parent_category else None
            category.save()

        target_category.delete()

        result = make_response(redirect('/categories'))

    return result


@app.route('/sub_categories/del/<string:category_id>', methods=['GET', 'POST'])
def del_subcategory(category_id):
    result = make_response(redirect('/login'))
    if auth_check():

        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if not user:
            return None

        if user.rank != 0:
            result = user.get_access('/categories')
            if result:
                return make_response(redirect(result))

        result = make_response(redirect('/'))

        if not category_id:
            return result

        target_category: Category = Category.objects(id=category_id).first()

        for category in Category.objects(parent_category=target_category):
            category.parent_category = target_category.parent_category if target_category.parent_category else None
            category.save()

        target_category.delete()

        result = make_response(redirect('/categories'))


    return result


def all_parent_categories(category):
    result: list = list()

    while category.parent_category:
        result.append(category)
        category = category.parent_category

    return result


@app.route('/presentation/tg_documents/<string:path>', methods=['GET', 'POST'])
def presentation_dawnload(path):
    print(path)

    path = 'tg_documents/' + path
    print(path)
    file_path = path.split('/')
    print(file_path)
    root_dir = os.path.join(app.root_path)
    print(root_dir)
    print(os.path.join(root_dir, 'static', file_path[0]), file_path[1])
    return send_from_directory(os.path.join(root_dir, 'static', file_path[0]), file_path[1])


@app.route('/reversation', methods=['GET', 'POST'])
def reversation_method():
    result = make_response(redirect('/login'))
    if auth_check():
        core: Core = Core.objects.first()
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()
        if not user:
            return None

        if user.rank != 0:
            result = make_response(redirect('/'))

        else:
            if request.method == 'POST':
                num = request.form.get('num')
                if num:
                    try:
                        num = int(num)
                        generating = threading.Thread(target=reversation_users_function, args=(num, core))
                        generating.daemon = True
                        generating.start()

                        return redirect('/reversations')

                    except ValueError:
                        error = 'Вы ввели неверное значение!'
                        result = make_response(render_template('reversation.html', user=user, error=error))
            else:
                result = make_response(render_template('reversation.html', user=user))
            # result = make_response(redirect('/reversations'))

    return result


@app.route('/reversations', methods=['GET', 'POST'])
def reversations_method():
    result = make_response(redirect('/login'))
    if auth_check():
        page = int(request.args.get('p', None)) if request.args.get('p', None) else 1
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        if not user:
            return None

        if user.rank != 0:
            return make_response(redirect('/'))

        if request.method == 'POST':
            pass
        else:
            end = page * 20
            start = end - 20
            users_len = UserRegister.objects(is_reserved=True).count()

            p_all = ceil(users_len / 20) if ceil(users_len / 20) != 0 else 1

            if start > users_len:
                start = users_len

            if end > users_len:
                end = users_len

            users = UserRegister.objects(is_reserved=True).order_by('positional_id')[start:end]
            result = render_template(template_name_or_list='reversations.html', p=page, rows=users, p_all=p_all,
                                     u_all=users_len, user=user)
    return result


@app.route('/give_out_reversation/<string:reversation_id>', methods=['GET', 'POST'])
def give_out_method(reversation_id):
    result = make_response(redirect('/login'))
    if auth_check():
        session_id = request.cookies.get('session_id', None)
        user = User.objects(session_id=session_id).first()

        reg_user = UserRegister.objects(id=reversation_id).first()

        if not user:
            return None

        if user.rank != 0:
            return make_response(redirect('/'))

        if request.method == 'POST':
            email = request.form.get('email')
            if re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
                current_users = UserRegister.objects(login=email)
                if not current_users:
                    reg_user.login = email
                    reg_user.password = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                    reg_user.is_reserved = False
                    reg_user.save()

                    smtp = smtplib.SMTP('smtp.gmail.com', 587)
                    smtp.starttls()
                    smtp.login(config.EMAIL_LOGIN, config.EMAIL_PASSWORD)
                    text1 = 'Поздравляю с успешным приобритением места в основном пакете платформы ShopSystem!\n' \
                            'Войти в кабинет вы можете через бот {0} или через сайт {1}!\n\n' \
                            'Ваш логин: {2}\n' \
                            'Ваш пароль: {3}\n' \
                            'Congratulations on the successful purchase of a place in the main package of the ShopSystem platform!\n' \
                            'You can enter the office through the bot {0} or through the site {1}!\n\n' \
                            'Your login: {2}\n' \
                            'Your password: {3}\n'.format('https://t.me/shop_system_bot',
                                                          config.CABINET_LINK,
                                                          reg_user.login,
                                                          reg_user.password)

                    msg = MIMEText(text1)
                    msg['Subject'] = 'Auth message'
                    msg['From'] = config.EMAIL_LOGIN

                    msg['To'] = email
                    smtp.send_message(from_addr=config.EMAIL_PASSWORD, to_addrs=email, msg=msg)
                    smtp.quit()

                    return make_response(redirect('/reversations'))
                else:
                    error = 'Пользователь с таким email уже существует!'
                    result = make_response(render_template('give_out_reversation.html', user=user, error=error))
            else:
                error = 'Вы ввели неверное значение!'
                result = make_response(render_template('give_out_reversation.html', user=user, error=error))
        else:
            return make_response(render_template('give_out_reversation.html', user=user))

    return result