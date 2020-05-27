from telebot import types
from ..core.db_model.structure import Product
from ..core.db_model.text.text import Text
from ..core.db_model.text.language import Language
from ..core.db_model.currency import Currency
from ..tg_bot.db_model.user_register import UserRegister
from ..config import *
from itertools import chain


def get_lang_keyboard(buttons_text):
    lang_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    for text in buttons_text:
        lang_kb.add(text)

    return lang_kb


def referrals_menu(user):
    lang = user.user_lang
    keyboard = types.InlineKeyboardMarkup()

    btn1 = types.InlineKeyboardButton(locale_text(lang, 'left_referrals_link'),
                                      callback_data='cabinet_state_inline_button_1_option')
    keyboard.row(btn1)

    return keyboard


def wallets_keyboard(user):
    reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
    lang = user.user_lang
    currencies: Currency = Currency.objects

    keyboard = types.InlineKeyboardMarkup()

    for currency in currencies:
        try:
            wallet = reg_user.wallets.get(currency.tag)
        except Exception as e:
            wallet = None
            print(e)

        text = currency.values.get(lang)
        if wallet:
            text += '-'
            callback_data = 'choose_wallets_state_inline_button_{0}_del'.format(currency.tag)

        else:
            text += '+'
            callback_data = 'choose_wallets_state_inline_button_{0}_add'.format(currency.tag)

        btn = types.InlineKeyboardButton(text=text, callback_data=callback_data)
        keyboard.add(btn)

    return keyboard


def apply_to_del_keyboard(lang):
    keyboards = types.InlineKeyboardMarkup()

    btn1 = types.InlineKeyboardButton(locale_text(lang, 'delete'), callback_data='apply_to_del_state_inline_button_apply')
    btn2 = types.InlineKeyboardButton(locale_text(lang, 'cancel_msg'), callback_data='apply_to_del_state_inline_button_cancel')

    keyboards.row(btn1, btn2)

    return keyboards


def back_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = locale_text(lang, 'back_btn')

    keyboard.row(btn1)

    return keyboard


def apply_rewrite_keyboard(lang):
    keyboards = types.InlineKeyboardMarkup()

    btn1 = types.InlineKeyboardButton('Переписать', callback_data='enter_wallet_state_inline_button_apply')
    btn2 = types.InlineKeyboardButton('Отмена', callback_data='enter_wallet_state_inline_button_cancel')

    keyboards.row(btn1, btn2)

    return keyboards


def main_menu_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    btn1 = locale_text(lang, 'user_cabinet')
    btn2 = locale_text(lang, 'company')
    btn3 = locale_text(lang, 'contacts')
    btn4 = locale_text(lang, 'market')

    keyboard.row(btn4)
    keyboard.row(btn2, btn3)
    keyboard.row(btn1)

    return keyboard


def choose_goods_keyboard(goods, lang):
    keyboard = types.InlineKeyboardMarkup()

    for good in goods:
        text = locale_text(lang, 'keyboard_price_text').format(good.name, good.price+good.destributed_price)
        btn = types.InlineKeyboardButton(text=text, callback_data='shop_state_inline_button_{0}'.format(good.id))
        keyboard.add(btn)

    keyboard.add(types.InlineKeyboardButton(text=locale_text(lang, 'back_btn'),
                                            callback_data='shop_state_inline_button_back_to_choose'))

    return keyboard


def choose_structure_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup()
    text = locale_text(lang, 'prise_msg')

    for i in Product.objects:
        btn = types.InlineKeyboardButton(text=text.format(i.name, i.price),
                                         callback_data='choose_structure_inline_button_{0}'.format(i.id))
        keyboard.add(btn)
    return keyboard


def good_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup()

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'buy'),
                                      callback_data='shop_state_inline_button_1_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'back_btn'),
                                      callback_data='shop_state_inline_button_2_option')

    keyboard.row(btn2, btn1)

    return keyboard


def enter_advert_name_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn1 = locale_text(lang, 'back_btn')
    btn2 = locale_text(lang, 'cancel_msg')

    keyboard.add(btn1, btn2)
    return keyboard


def company_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'history'),
                                      callback_data='company_state_inline_button_1_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'mission'),
                                      callback_data='company_state_inline_button_2_option')
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'whitepaper'),
                                      callback_data='company_state_inline_button_3_option')
    btn4 = types.InlineKeyboardButton(text=locale_text(lang, 'presentation'),
                                      callback_data='company_state_inline_button_6_option')
    btn5 = types.InlineKeyboardButton(text=locale_text(lang, 'help_the_project'),
                                      callback_data='company_state_inline_button_7_option')

    keyboard.row(btn1)
    keyboard.row(btn2, btn3)
    keyboard.row(btn4, btn5)

    return keyboard


def structure_keyboard(max_deep, lang, page: int = 1, current_page: int = 1, pages_count: int = 1):
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    low_ragne = (current_page - 1) * 5
    up_range = current_page * 5 if current_page * 5 < max_deep else max_deep

    for i in range(low_ragne, up_range):
        text = locale_text(lang, 'my_line').format(i+1)
        btn = types.InlineKeyboardButton(text=text, callback_data='cabinet_state_inline_button_my_line_{0}_{1}'.\
                                         format(i+1, page))
        keyboard.add(btn)

    if pages_count > 1:
        next_num = current_page+1 if current_page+1 <= pages_count else 1
        back_num = current_page-1 if current_page-1 >= 1 else pages_count
        forward = types.InlineKeyboardButton(text=locale_text(lang, 'type_1_next_button_msg').format(next_num, pages_count),
                                             callback_data='cabinet_state_inline_button_goto_{0}'.format(next_num))
        back = types.InlineKeyboardButton(text=locale_text(lang, 'type_1_back_button_msg').format(back_num, pages_count),
                                          callback_data='cabinet_state_inline_button_goto_{0}'.format(back_num))
        keyboard.row(back, forward)

    return keyboard


def new_shop_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'new_goods'),
                                      callback_data='new_shop_state_inline_button_1_option')
    btn_day_product = types.InlineKeyboardButton(text=locale_text(lang, 'product_of_the_day_btn'),
                                                 callback_data='new_shop_state_inline_button_day_product')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'basket'),
                                      callback_data='new_shop_state_inline_button_2_option')
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'search_btn'),
                                      callback_data='new_shop_state_inline_button_3_option')
    btn4 = types.InlineKeyboardButton(text=locale_text(lang, 'back_btn'),
                                      callback_data='new_shop_state_inline_button_4_option')
    keyboard.row(btn1)
    keyboard.add(btn_day_product, btn2, btn3, btn4)

    return keyboard


def single_back_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn = locale_text(lang, 'back_btn')
    keyboard.add(btn)

    return keyboard


def feedback_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.row(locale_text(lang, 'back_btn'))

    return keyboard


def contacts_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'enter_quest_button_msg'),
                                      callback_data='contacts_state_inline_button_1_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'usually_quest_button_msg'),
                                      callback_data='contacts_state_inline_button_2_option')
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'feedback_button_msg'),
                                      callback_data='contacts_state_inline_button_3_option')

    keyboard.row(btn1)
    keyboard.row(btn3)
    keyboard.row(btn2)

    return keyboard


def comments_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'enter_comment_btn_msg'),
                                      callback_data='contacts_state_inline_button_1_option_comment')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'watch_comments_msg'),
                                      callback_data='contacts_state_inline_button_2_option_comment')
    keyboard.add(btn1, btn2)

    return keyboard


def category_keyboard(lang, categories,
                      col_num: int = 2, row_num: int = 5,
                      current_page: int = 1, max_pages_count: int = 0,
                      user=None, goods=None):
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    category_container: list = list()
    index = 0

    current_index = (current_page - 1) * row_num * col_num
    counter = current_index
    if goods:
        categories_s_goods = list(chain(categories, goods))
    else:
        categories_s_goods = categories

    for category in categories_s_goods[current_index:current_index+row_num*col_num]:
        if type(category) == Product:
            btn = types.InlineKeyboardButton(text=category.fields.get('name'),
                                             callback_data='_category_state_inline_button_good_' + str(category.id))
        else:
            btn = types.InlineKeyboardButton(text=category.values.get(lang),
                                             callback_data='_category_state_inline_button_' + str(category.id))

        category_container.append(btn)
        index += 1
        counter += 1

        if index == col_num:
            keyboard.row(*category_container)
            index = 0
            category_container.clear()

    if len(category_container) > 0:
        keyboard.row(*category_container)

    text_1: str = locale_text(lang, 'type_1_back_button_msg')
    text_1 = text_1.format(
        str(current_page - 1) if current_page != 1 else str(max_pages_count),
        str(max_pages_count)
    )
    prev_btn = types.InlineKeyboardButton(
        text=text_1,
        callback_data='_category_state_inline_button_1_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    text_2: str = locale_text(lang, 'back_2_button_msg')
    text_2 = text_2.format(
        str(current_page)
    )
    text_back = locale_text(lang, 'back_btn')
    if len(categories) > row_num * col_num:
        back_btn = types.InlineKeyboardButton(
            text=text_2,
            callback_data='_category_state_inline_button_2'
        )
    else:
        back_btn = types.InlineKeyboardButton(
            text=text_back,
            callback_data='_category_state_inline_button_2'
        )

    text_3: str = locale_text(lang, 'type_1_next_button_msg')
    text_3 = text_3.format(
        str(current_page + 1) if current_page != max_pages_count else str(1),
        str(max_pages_count)
    )
    next_btn = types.InlineKeyboardButton(
        text=text_3,
        callback_data='_category_state_inline_button_3_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    if len(categories) > row_num * col_num:
        keyboard.row(prev_btn, back_btn, next_btn)
    else:
        keyboard.row(back_btn)

    if not user.is_in_shop and user.category:
        apply_btn = types.InlineKeyboardButton(text=locale_text(lang, 'aplly_current_category'),
                                               callback_data='_category_state_inline_button_apply')

        keyboard.row(apply_btn)

    return keyboard

    # button_1 = types.InlineKeyboardButton(text=locale_text(lang, 'next_btn'),
    #                                       callback_data='_category_state_inline_button_2_option')
    # button_2 = types.InlineKeyboardButton(text=locale_text(lang, 'back_btn'),
    #                                       callback_data='_category_state_inline_button_1_option')
    #
    # keyboard.add(button_2)
    #
    # return keyboard


def back_pass_keyboard(lang):
    """ use in enter_field_state """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn1 = locale_text(lang, 'back_btn')
    btn2 = locale_text(lang, 'pass_btn_2')
    btn3 = locale_text(lang, 'cancel_msg')

    keyboard.row(btn1, btn2)
    keyboard.row(btn3)

    return keyboard


def send_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn1 = locale_text(lang, 'send_btn')
    btn2 = locale_text(lang, 'cancel_msg')

    keyboard.add(btn1)
    keyboard.add(btn2)

    return keyboard


def shop_state_keyboard(lang, goods, col_num: int = 2, row_num: int = 5,
                        current_page: int = 1, max_pages_count: int = 0
                        ):

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    goods_container: list = list()
    index = 0

    current_index = (current_page - 1) * row_num * col_num
    counter = current_index

    for good in goods[current_index:current_index+row_num*col_num]:
        btn = types.InlineKeyboardButton(text=good.fields.get('name'),
                                         callback_data='shop_state_inline_button_{0}'.format(good.id))
        goods_container.append(btn)
        index += 1
        counter += 1

        if index == col_num:
            keyboard.row(*goods_container)
            index = 0
            goods_container.clear()

    if len(goods_container) > 0:
        keyboard.row(*goods_container)

    text_1: str = locale_text(lang, 'type_1_back_button_msg')
    text_1 = text_1.format(
        str(current_page - 1) if current_page != 1 else str(max_pages_count),
        str(max_pages_count)
    )

    prev_btn = types.InlineKeyboardButton(
        text=text_1,
        callback_data='shop_state_inline_button_1_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    text_2: str = locale_text(lang, 'back_2_button_msg')
    text_2 = text_2.format(
        str(current_page)
    )
    text_back = locale_text(lang, 'back_btn')
    if len(goods) > row_num * col_num:
        back_btn = types.InlineKeyboardButton(
            text=text_2,
            callback_data='shop_state_inline_button_2'
        )
    else:
        back_btn = types.InlineKeyboardButton(
            text=text_back,
            callback_data='shop_state_inline_button_2'
        )

    text_3: str = locale_text(lang, 'type_1_next_button_msg')
    text_3 = text_3.format(
        str(current_page + 1) if current_page != max_pages_count else str(1),
        str(max_pages_count)
    )
    next_btn = types.InlineKeyboardButton(
        text=text_3,
        callback_data='shop_state_inline_button_3_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    if len(goods) > row_num * col_num:
        keyboard.row(prev_btn, back_btn, next_btn)
    else:
        keyboard.row(back_btn)

    return keyboard


def comments_control_keyboard(lang, current_page: int = 1, max_pages_count: int = 0):

    keyboard = types.InlineKeyboardMarkup(row_width=3)

    text_1: str = locale_text(lang, 'type_1_back_button_msg')
    text_1 = text_1.format(
        str(current_page - 1) if current_page != 1 else str(max_pages_count),
        str(max_pages_count)
    )
    prev_btn = types.InlineKeyboardButton(
        text=text_1,
        callback_data='comments_state_$$_1_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    text_2: str = locale_text(lang, 'back_2_button_msg')
    text_2 = text_2.format(
        str(current_page)
    )
    back_btn = types.InlineKeyboardButton(
        text=text_2,
        callback_data='comments_state_$$_2'
    )

    text_3: str = locale_text(lang, 'type_1_next_button_msg')
    text_3 = text_3.format(
        str(current_page + 1) if current_page != max_pages_count else str(1),
        str(max_pages_count)
    )
    next_btn = types.InlineKeyboardButton(
        text=text_3,
        callback_data='comments_state_$$_3_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    keyboard.row(prev_btn, back_btn, next_btn)

    return keyboard


def _buy_history_keyboard(lang, good, current_page: int = 1, max_pages_count: int = 0):

    keyboard = types.InlineKeyboardMarkup(row_width=3)

    text_1: str = locale_text(lang, 'type_1_back_button_msg')
    text_1 = text_1.format(
        str(current_page - 1) if current_page != 1 else str(max_pages_count),
        str(max_pages_count)
    )
    prev_btn = types.InlineKeyboardButton(
        text=text_1,
        callback_data='_buy_history_state_inline_button_1_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    text_2: str = locale_text(lang, 'back_2_button_msg')
    text_2 = text_2.format(
        str(current_page)
    )
    back_btn = types.InlineKeyboardButton(
        text=text_2,
        callback_data='_buy_history_state_inline_button_2'
    )

    text_3: str = locale_text(lang, 'type_1_next_button_msg')
    text_3 = text_3.format(
        str(current_page + 1) if current_page != max_pages_count else str(1),
        str(max_pages_count)
    )
    next_btn = types.InlineKeyboardButton(
        text=text_3,
        callback_data='_buy_history_state_inline_button_3_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    btn_repeat = types.InlineKeyboardButton(text=locale_text(lang, 'repeat_purchase_btn'),
                                            callback_data='_buy_history_state_inline_button_repeat_{0}'.format(good.id))
    btn_share = types.InlineKeyboardButton(text=locale_text(lang, 'share_btn'),
                                           callback_data='_buy_history_state_inline_button_share_{0}'.format(good.id))

    keyboard.row(prev_btn, back_btn, next_btn)
    keyboard.row(btn_repeat)
    keyboard.row(btn_share)

    return keyboard


def my_goods_keyboard(lang, goods, col_num: int = 1, row_num: int = 5,
                      current_page: int = 1, max_pages_count: int = 0
                      ):

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    goods_container: list = list()
    index = 0

    current_index = (current_page - 1) * row_num * col_num
    counter = current_index

    for good in goods[current_index:current_index+row_num*col_num]:
        btn = types.InlineKeyboardButton(text=good.fields.get('name'),
                                         callback_data='my_goods_state_inline_button_{0}'.format(good.id))
        goods_container.append(btn)
        index += 1
        counter += 1

        if index == col_num:
            keyboard.row(*goods_container)
            index = 0
            goods_container.clear()

    if len(goods_container) > 0:
        keyboard.row(*goods_container)

    text_1: str = locale_text(lang, 'type_1_back_button_msg')
    text_1 = text_1.format(
        str(current_page - 1) if current_page != 1 else str(max_pages_count),
        str(max_pages_count)
    )
    prev_btn = types.InlineKeyboardButton(
        text=text_1,
        callback_data='my_goods_state_inline_button_1_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    text_2: str = locale_text(lang, 'back_2_button_msg')
    text_2 = text_2.format(
        str(current_page)
    )
    text_back = locale_text(lang, 'back_btn')
    if len(goods) > row_num * col_num:
        back_btn = types.InlineKeyboardButton(
            text=text_2,
            callback_data='my_goods_state_inline_button_2'
        )
    else:
        back_btn = types.InlineKeyboardButton(
            text=text_back,
            callback_data='my_goods_state_inline_button_2'
        )

    text_3: str = locale_text(lang, 'type_1_next_button_msg')
    text_3 = text_3.format(
        str(current_page + 1) if current_page != max_pages_count else str(1),
        str(max_pages_count)
    )
    next_btn = types.InlineKeyboardButton(
        text=text_3,
        callback_data='my_goods_state_inline_button_3_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )
    if len(goods) > row_num * col_num:
        keyboard.row(prev_btn, back_btn, next_btn)
    else:
        keyboard.row(back_btn)

    return keyboard


def share_keyboard(lang, good):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn = types.InlineKeyboardButton(text=locale_text(lang, 'share_btn'),
                                     callback_data='my_goods_state_inline_button_share_{0}'.format(good.id))
    keyboard.add(btn)
    return keyboard


def reply_back_keyboard(lang):
    # back_btn
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    keyboard.row(locale_text(lang, 'back_btn'))

    return keyboard


def view_basket_keyboard(user, good, full_price, current_page: int = 1, max_pages_count: int = 0):
    lang = user.user_lang
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    print(good.fields)
    sum_btn = types.InlineKeyboardButton(text=locale_text(lang, 'sum').format(
        user.cart.count(good), good.fields.get('price'),
        round(user.cart.count(good) * float(good.fields.get('price')), 2)
    ), callback_data='v_a_c_s_inline_button_count')

    btn_address = types.InlineKeyboardButton(text=locale_text(lang, 'change_adres_btn'),
                                             callback_data='v_a_c_s_inline_button_change_address')
    btn_phone = types.InlineKeyboardButton(text=locale_text(lang, 'change_phone_btn'),
                                           callback_data='v_a_c_s_inline_button_change_phone')
    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'confirm_purchase_btn').
                                      format(round(full_price, 2)),
                                      callback_data='v_a_c_s_inline_button_accept')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'remove_item_btn'),
                                      callback_data='v_a_c_s_inline_button_del_good_{0}'.format(good.id))
    btn_share = types.InlineKeyboardButton(text=locale_text(lang, 'share_btn'),
                                           callback_data='v_a_c_s_inline_button_share_{0}'.format(good.id))

    text_1: str = locale_text(lang, 'type_1_back_button_msg')
    text_1 = text_1.format(
        str(current_page - 1) if current_page != 1 else str(max_pages_count),
        str(max_pages_count)
    )
    prev_btn = types.InlineKeyboardButton(
        text=text_1,
        callback_data='v_a_c_s_inline_button_1_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    text_2: str = locale_text(lang, 'back_btn')
    back_btn = types.InlineKeyboardButton(
        text=text_2,
        callback_data='v_a_c_s_inline_button_2'
    )

    text_3: str = locale_text(lang, 'type_1_next_button_msg')
    text_3 = text_3.format(
        str(current_page + 1) if current_page != max_pages_count else str(1),
        str(max_pages_count)
    )
    next_btn = types.InlineKeyboardButton(
        text=text_3,
        callback_data='v_a_c_s_inline_button_3_{0}_{1}'.format(
            str(current_page),
            str(max_pages_count)
        )
    )

    up_btn = types.InlineKeyboardButton(
        text=locale_text(lang, 'up'),
        callback_data='v_a_c_s_inline_button_up_{0}_{1}'.format(good.id, current_page)
    )

    coun_btn = types.InlineKeyboardButton(
        text='{0}'.format(user.cart.count(good)),
        callback_data='v_a_c_s_inline_button_number'
    )

    down_btn = types.InlineKeyboardButton(
        text=locale_text(lang, 'down'),
        callback_data='v_a_c_s_inline_button_down_{0}_{1}'.format(good.id, current_page)
    )

    keyboard.row(sum_btn)

    keyboard.row(btn2, down_btn,  coun_btn, up_btn)

    keyboard.row(btn_address, btn_phone)

    keyboard.row(btn1)

    if max_pages_count == 1:
        keyboard.row(back_btn)
    else:
        keyboard.row(prev_btn, back_btn, next_btn)

    keyboard.row(btn_share)

    return keyboard


def buy_keyboard(lang, good, user):
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    # btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'buy_btn'),
    #                                   callback_data='shop_state_inline_button_buy_{0}'.format(good.id))
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'add_to_cart'),
                                      callback_data='shop_state_inline_button_add_to_cart_{0}'.format(good.id))
    btn4 = types.InlineKeyboardButton(text=locale_text(lang, 'to_cart'),
                                      callback_data='shop_state_inline_button_to_cart_{0}'.format(good.id))
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'back_btn'),
                                      callback_data='shop_state_inline_button_back')
    if len(user.cart) != 0:
        keyboard.add(btn3, btn4,  btn2)
    else:
        keyboard.add(btn3, btn2)

    return keyboard


def cabinet_keyboard_2(user, user_lang):

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    if not user.is_main_structure:
        keyboard.add(types.InlineKeyboardButton(text=locale_text(user_lang, 'activate_btn'),
                                                callback_data='cabinet_state_inline_button_1_option'))
    else:
        keyboard.add(types.InlineKeyboardButton(text=locale_text(user_lang, 'user_cabinet'), url=CABINET_LINK))

    return keyboard


def line_pages_keyboard(lang, page, line, max_page):
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    forward_page = page + 1 if page != max_page else 1

    back_page = page - 1 if page != 1 else max_page

    btn_forward = types.InlineKeyboardButton(locale_text(lang, 'forward_btn_2').format(forward_page, max_page),
                                             callback_data='cabinet_state_inline_button_my_line_{0}_{1}'.
                                             format(line, forward_page))
    btn_back = types.InlineKeyboardButton(locale_text(lang, 'back_btn_2').format(back_page, max_page),
                                          callback_data='cabinet_state_inline_button_my_line_{0}_{1}'.
                                          format(line, back_page))

    btn_del_msg = types.InlineKeyboardButton(locale_text(lang, 'back_btn'),
                                             callback_data='cabinet_state_inline_button_6_option')
    if max_page > 1:
        keyboard.add(btn_back, btn_del_msg, btn_forward)
    else:
        keyboard.add(btn_del_msg)

    return keyboard


def cabinet_keyboard(lang, user):
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    reg_user: UserRegister = UserRegister.objects(login=user.auth_login).first()
    if not reg_user:
        reg_user = user.defaul_unregister_user

    if not reg_user.is_main_structure:
        keyboard.row(locale_text(lang, 'activate_btn'), locale_text(lang, 'web_cabinet_btn'))
    else:
        keyboard.row(locale_text(lang, 'web_cabinet_btn'), locale_text(lang, 'invite_friend_btn'))

    btn1 = locale_text(lang, 'info_btn')
    # btn2 = locale_text(lang, 'invite_friend_btn')
    btn3 = locale_text(lang, 'add_good')
    btn4 = locale_text(lang, 'basket_btn')
    btn5 = locale_text(lang, 'settings')
    btn6 = locale_text(lang, 'back_btn')
    btn7 = locale_text(lang, 'log_out_btn')

    keyboard.add(btn1, btn3, btn4, btn5, btn6, btn7) if reg_user.is_registered else keyboard.add(btn1, btn3, btn4, btn5, btn6)

    return keyboard


def cabinet_info_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'structures_data'),
                                      callback_data='cabinet_state_inline_button_6_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'balance'),
                                      callback_data='cabinet_state_inline_button_7_option')
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'my_wallets'),
                                      callback_data='cabinet_state_inline_button_8_option')
    btn4 = types.InlineKeyboardButton(text=locale_text(lang, 'purches_history'),
                                      callback_data='cabinet_state_inline_button_9_option')
    btn5 = types.InlineKeyboardButton(text=locale_text(lang, 'my_goods'),
                                      callback_data='cabinet_state_inline_button_10_option')

    keyboard.row(btn1)
    keyboard.add(btn2, btn3, btn4, btn5)

    return keyboard


def add_good_choose_way_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'read_the_terms_btn'),
                                      callback_data='cabinet_state_inline_button_11_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'add_from_telegram_btn'),
                                      callback_data='cabinet_state_inline_button_12_option')
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'web_cabinet_btn'),
                                      callback_data='cabinet_state_inline_button_13_option')

    keyboard.row(btn1)
    keyboard.add(btn2, btn3)

    return keyboard


def buy_place_in_structure_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    keyboard.add(types.InlineKeyboardButton(text=locale_text(lang, 'activate_btn'),
                                            callback_data='cabinet_state_inline_button_2_option'))
    keyboard.add(types.InlineKeyboardButton(text=locale_text(lang, 'back_btn'),
                                            callback_data='cabinet_state_inline_button_3_option'))
    #
    # btn1 = locale_text(lang, 'activate_btn')
    # btn2 = locale_text(lang, 'back_btn')
    #
    # keyboard.add(btn1, btn2)
    # keyboard.row(btn2)

    return keyboard


def no_buy_history_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    keyboard.add(types.InlineKeyboardButton(text=locale_text(lang, 'market'),
                                            callback_data='cabinet_state_inline_button_4_option'))
    keyboard.add(types.InlineKeyboardButton(text=locale_text(lang, 'product_of_the_day_btn'),
                                            callback_data='cabinet_state_inline_button_5_option'))
    return keyboard


def settings_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = locale_text(lang, 'change_adres_btn')
    btn2 = locale_text(lang, 'change_phone_btn')
    btn3 = locale_text(lang, 'save_btn')
    btn4 = locale_text(lang, 'back_btn')

    keyboard.row(btn1, btn2)
    keyboard.row(btn3)
    keyboard.row(btn4)

    return keyboard


def history_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'enter_message_button_msg'),
                                      callback_data='company_state_inline_button_5_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'back_button_msg'),
                                      callback_data='company_state_inline_button_4_option')

    keyboard.row(btn1, btn2)

    return keyboard


def auth_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'login_btn_msg'),
                                      callback_data='auth_state_$$_1_option')
    btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'register_btn_msg'),
                                      callback_data='auth_state_$$_2_option')
    # btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'statistics_btn'),
    #                                   callback_data='auth_state_$$_3_option')
    btn4 = types.InlineKeyboardButton(text=locale_text(lang, 'recover_password_btn'),
                                      callback_data='auth_state_$$_4_option')

    keyboard.add(btn1, btn2,  btn4)
    return keyboard


# def login_register(lang):
#     keyboard = types.InlineKeyboardMarkup(row_width=2)
#
#     btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'login_button_msg'),
#                                       callback_data='cabinet_auth_state_inline_button_1_option')
#     btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'register_button_msg'),
#                                       callback_data='cabinet_auth_state_inline_button_2_option')
#     btn3 = types.InlineKeyboardButton(text='Статистика',
#                                       callback_data='cabinet_auth_state_inline_button_3_option')
#     keyboard.row(btn1, btn2)
#     keyboard.row(btn3)
#
#     return keyboard


def phone_request_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'request_phone_btn'), request_contact=True)
    btn2 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))

    keyboard.add(btn1)
    keyboard.add(btn2)

    return keyboard


def email_request_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))
    keyboard.row(btn1)

    return keyboard


def email_code_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup()

    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'get_code_msg'),
                                      callback_data='email_validation_state_$$_1_option')
    keyboard.add(btn1)

    return keyboard


def password_request_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))
    keyboard.add(btn1)

    return keyboard


def login_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))
    keyboard.add(btn1)

    return keyboard


def cancel_back(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = locale_text(lang, 'back_button_msg')
    btn2 = locale_text(lang, 'cancel_msg')

    keyboard.row(btn1, btn2)

    return keyboard


def log_pass_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))
    # btn2 = types.KeyboardButton(text=locale_text(lang, 'recover_password_btn'))

    keyboard.add(btn1)

    return keyboard


def remove_reply_keyboard():
    keyboard = types.ReplyKeyboardRemove()

    return keyboard


def confirm_change_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(locale_text(lang, 'confirm_btn'),
                                      callback_data='shop_state_inline_button_confirm')
    btn2 = types.InlineKeyboardButton(locale_text(lang, 'change_btn'),
                                      callback_data='shop_state_inline_button_change')
    keyboard.add(btn1, btn2)

    return keyboard


def choose_recovery_type_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'recover_by_email_btn'))
    # btn2 = types.KeyboardButton(text=locale_text(lang, 'recover_by_phone_btn'))
    btn3 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))

    keyboard.add(btn1, btn3)

    return keyboard


def recover_password_keyboard(lang):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    btn1 = types.KeyboardButton(text=locale_text(lang, 'cancel_msg'))
    btn2 = types.KeyboardButton(text=locale_text(lang, 'recover_password_btn'))

    keyboard.add(btn1, btn2)

    return keyboard


def registration_keyboard(lang):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton(text=locale_text(lang, 'reg_from_email_btn_msg'),
                                      callback_data='register_state_$$_1_option')
    # btn2 = types.InlineKeyboardButton(text=locale_text(lang, 'reg_from_phone_btn_msg'),
    #                                   callback_data='register_state_$$_2_option')
    btn3 = types.InlineKeyboardButton(text=locale_text(lang, 'back_button_msg'),
                                      callback_data='register_state_$$_3_option')
    # keyboard.add(btn1, btn2, btn3)
    keyboard.add(btn1, btn3)
    return keyboard


def language_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    for lang in Language.objects:
        btn = types.InlineKeyboardButton(text=lang.button_text,
                                         callback_data='language_state_inline_button_{0}'.format(lang.id))
        keyboard.row(btn)

    return keyboard


def locale_text(lang, tag):
    if not lang or not tag:
        return None

    text = Text.objects(tag=tag).first()

    if not text:
        return None

    return text.values.get(lang)
