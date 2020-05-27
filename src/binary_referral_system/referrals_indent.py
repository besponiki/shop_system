import math
from operator import itemgetter
from ..tg_bot.db_model.user_register import UserRegister
from ..tg_bot.db_model.user import User
from ..core.db_model.structure import ProductStructureUser
from ..core.db_model.text.text import Text
from ..core.db_model.core import Core
from ..core.db_model.field import Field

import logging


def referrals_indent(user, reg_user: UserRegister):
    ident = None
    if user:
        ident = user.referral_link[7:]
        if ident:
            if len(ident) != 24:
                ident = None
                user.referral_link = None
                user.save()
                reg_user.referral_link = None
                reg_user.save()
                for field in Field.objects(user=reg_user):
                    field.delete()
        if ident:
            parent: UserRegister = UserRegister.objects(id=ident).first()
            if not parent:
                ident = None
                user.referral_link = None
                user.save()
                reg_user.referral_link = None
                reg_user.save()
                for field in Field.objects(user=reg_user):
                    field.delete()

            if ident and ident != reg_user.id and parent:
                reg_user.referral_link = user.referral_link
                reg_user.referral_parent = parent
                reg_user.save()

    if ident and ident != reg_user.id:
        try:
            parent_l: UserRegister = UserRegister.objects(id=ident).first()
            parent_r: UserRegister = UserRegister.objects(id=ident).first()
            i = 0
            while True:
                if i % 2 == 0:
                    if parent_l.left_referrals_branch:
                        parent_l: UserRegister = parent_l.left_referrals_branch
                    else:
                        parent_l.left_referrals_branch = reg_user
                        parent_l.save()
                        reg_user.parent = parent_l
                        reg_user.positional_id = parent_l.positional_id * 2
                        reg_user.percent = (1 / parent_l.level) * 2 - 0.01
                        reg_user.level = parent_l.level + 1
                        reg_user.save()
                        break
                elif i % 2 == 1:
                    if parent_r.right_referrals_branch:
                        parent_r: UserRegister = parent_r.right_referrals_branch
                    else:
                        parent_r.right_referrals_branch = reg_user
                        parent_r.save()
                        reg_user.parent = parent_r
                        reg_user.positional_id = parent_r.positional_id * 2 + 1
                        reg_user.percent = 2 / parent_r.level - 0.01
                        reg_user.level = parent_r.level + 1
                        reg_user.save()
                        break
                i += 1

        except Exception as e:
            logging.exception(e)
    else:
        core: Core = Core.objects.first()
        while True:
            us: UserRegister = UserRegister.objects(positional_id=core.positional_id).first()
            if us:
                core.positional_id += 1
                core.save()
            else:
                reg_user.positional_id = core.positional_id
                reg_user.save()
                parent_positional_id = reg_user.positional_id // 2
                parent: UserRegister = UserRegister.objects(positional_id=parent_positional_id).first()
                if parent:
                    if reg_user.id != parent.id:
                        reg_user.parent = parent
                        reg_user.percent = 2 / parent.level - 0.01
                        reg_user.level = parent.level + 1
                        reg_user.save()
                        reg_user.save()
                        if reg_user.positional_id % 2 == 0:
                            parent.left_referrals_branch = reg_user
                            parent.save()
                        else:
                            parent.right_referrals_branch = reg_user
                            parent.save()
                else:
                    reg_user.percent = 1.99
                    reg_user.level = 1
                    reg_user.save()

                break


def find_parents_ids(reg_user: UserRegister):
    user_ids = []
    while True:
        if reg_user.parent:
            user_ids.append(reg_user.id)
            reg_user: UserRegister = reg_user.parent
        else:
            user_ids.append(reg_user.id)
            break
    return user_ids


def find_structure_parents_ids(structure_user):
    structure_user_ids: list = list()
    while True:
        if structure_user.parent:
            structure_user_ids.append(structure_user.parent)
            structure_user: ProductStructureUser = structure_user.parent
        else:
            break
    return structure_user_ids


def graph_data(reg_user: UserRegister, admin_panel: bool = True, index: int = 0, max_line: int = 3, is_started: bool = True):
    if index == max_line + 1:
        return None

    result = None
    if reg_user:
        tg_user = User.objects(auth_login=reg_user.login).first()

        # if tg_user:
        txt = ''
        if tg_user:

            if tg_user.username and not tg_user.username == 'None':
                    link = 'https://t.me/{0}'.format(str(tg_user.username)) + '\n'
                    txt += link
            else:
                    link = Text.objects(tag='link_msg').first().values.get('rus').format(tg_user.user_id) + '\n'
                    txt += link
        if admin_panel:
            contents = "level: {0} <br> percent: {1} <br> <a href = '{2}'> View:</a><br><a href= {3}>{3}</a> " \
                       "<br> <a href= '{4}'> Up</a><br> <a href= '{5}'> Down</a>".format(
                reg_user.level, '%.3f' % reg_user.percent if reg_user.percent else 0.0,
                'https://admin-setevik.botup.pp.ua/shops/viev/{0}'.format(reg_user.id), txt,
                'https://admin-setevik.botup.pp.ua/graph',
                'https://admin-setevik.botup.pp.ua/graph?id={0}'.format(reg_user.id),
            )
            result = {
                "head": "{0}".format(reg_user.login),
                "id": "{0}".format(reg_user.id),
                "contents": contents,
                "children": [],
                'level': reg_user.level,
                'parent_id': str(reg_user.parent.id) if reg_user.parent else None
            }
        else:
            contents = "level: {0} <br> percent: {1} <br><a href= {2}>{2}</a> " \
                       "<br> <a href= '{3}'> Up</a><br> <a href= '{4}'> Down</a>".format(
                reg_user.level, '%.3f' % reg_user.percent, txt,
                'https://cabinet-shop-system.botup.pp.ua/graph',
                'https://cabinet-shop-system.botup.pp.ua/graph?id={0}'.format(reg_user.id),
                                )
            result = {
                "head": "Positional id: {0}".format(reg_user.positional_id),
                "id": "{0}".format(reg_user.id),
                "contents": contents,
                "children": [],
                'level': reg_user.level,
                'parent_id': str(reg_user.parent.id) if reg_user.parent else None
            }

        children = list()

        if reg_user.left_referrals_branch:
            child_data = graph_data(reg_user.left_referrals_branch, admin_panel, index + 1, max_line, False)

            if child_data:
                children.append(child_data)

        if reg_user.right_referrals_branch:
            child_data = graph_data(reg_user.right_referrals_branch, admin_panel,  index + 1, max_line, False)

            if child_data:
                children.append(child_data)

        result['children'] = children

        if is_started:
            result = [result]

            import pprint
            pprint.pprint(result)
    return result


def get_dicts_from_list(key, param, lst):
    result: list = list()
    for i in lst:
        if i[key] == param:
            result.append(i)
    return result


def get_verge_index(line_users, positional_id, len_line_users, interim_list: list = None, curent_index: int = None):
    res = None
    if interim_list:
        if interim_list[0].positional_id == positional_id:
            res = curent_index

        elif interim_list[len_line_users-1].positional_id == positional_id:
            res = curent_index + len_line_users-1

        else:
            midl_index = math.ceil(len_line_users / 2)

            if interim_list[midl_index].positional_id > positional_id:
                res = get_verge_index(line_users, positional_id, midl_index, interim_list[:midl_index],
                                      curent_index+midl_index)

            elif interim_list[midl_index].positional_id == positional_id:
                res = curent_index+midl_index

            elif interim_list[midl_index].positional_id < positional_id:
                res = get_verge_index(line_users, positional_id, midl_index, interim_list[midl_index:],
                                      curent_index-(curent_index-midl_index))
    else:
        if line_users[0].positional_id == positional_id:
            res = 0

        elif line_users[len_line_users-1].positional_id == positional_id:
            res = len_line_users-1

        else:
            midl_index = math.ceil(len_line_users / 2)

            if line_users[midl_index].positional_id > positional_id:
                res = get_verge_index(line_users, positional_id, midl_index, line_users[:midl_index], midl_index)

            elif line_users[midl_index].positional_id == positional_id:
                res = midl_index

            elif line_users[midl_index].positional_id < positional_id:
                res = get_verge_index(line_users, positional_id, midl_index, line_users[midl_index:],
                                      midl_index)

    if res:
        return res


from mongoengine.queryset.visitor import Q


def get_max_deep(users_positional_id, users_level,  current_deep: int = 0):
    res = current_deep
    current_line = users_level + current_deep + 1
    print(current_line)
    left = users_positional_id * 2 ** (current_deep + 1)
    print(left)

    right = users_positional_id * 2 ** (current_deep + 1) + 2 ** (current_deep + 1) - 1
    print(right)

    line_users: UserRegister = UserRegister.objects(Q(level=current_line) &
                                                    Q(positional_id__gte=left) &
                                                    Q(positional_id__lte=right))
    if line_users:
        res = get_max_deep(users_positional_id, users_level, current_deep+1)

    return res


from ..core.db_model.structure import ProductStructureUser


def graph_product_data(reg_user: ProductStructureUser, admin_panel: bool = True, index: int = 0, max_line: int = 3, is_started: bool = True):
    if index == max_line + 1:
        return None

    result = None
    if reg_user:
        tg_user = User.objects(auth_login=reg_user.user.login).first()

        # if tg_user:
        txt = ''
        if tg_user:

            if tg_user.username and not tg_user.username == 'None':
                    link = 'https://t.me/{0}'.format(str(tg_user.username)) + '\n'
                    txt += link
            else:
                    link = Text.objects(tag='link_msg').first().values.get('rus').format(tg_user.user_id) + '\n'
                    txt += link

        if admin_panel:
            contents = "level: {0} <br> percent: {1} <br> <a href = '{2}'> View:</a><br><a href= {3}>{3}</a> " \
                       "<br> <a href= '{4}'> Up</a><br> <a href= '{5}'> Down</a>".format(
                reg_user.level, '%.3f' % reg_user.percent,
                'https://admin-setevik.botup.pp.ua/shops/viev/{0}'.format(reg_user.user.id), txt,
                'https://admin-setevik.botup.pp.ua/advert/edit/{0}'.format(reg_user.structure.id),
                'https://admin-setevik.botup.pp.ua/advert/edit/{0}?id={1}'.format(reg_user.structure.id, reg_user.id),
                # 'https://admin-setevik.botup.pp.ua/graph?id={0}'.format(reg_user.user.id),
            )
            result = {
                "head": "{0}".format(reg_user.user.login),
                "id": "{0}".format(reg_user.id),
                "contents": contents,
                "children": [],
                'level': reg_user.level,
                'parent_id': str(reg_user.parent.id) if reg_user.parent else None
            }
        # else:
        #     contents = "level: {0} <br> percent: {1} <br><a href= {2}>{2}</a> " \
        #                "<br> <a href= '{3}'> Up</a><br> <a href= '{4}'> Down</a>".format(
        #         reg_user.level, '%.3f' % reg_user.percent, txt,
        #         'https://cabinet-shop-system.botup.pp.ua/graph',
        #         'https://cabinet-shop-system.botup.pp.ua/graph?id={0}'.format(reg_user.id),
        #                         )
        #     result = {
        #         "head": "Positional id: {0}".format(reg_user.positional_id),
        #         "id": "{0}".format(reg_user.id),
        #         "contents": contents,
        #         "children": [],
        #         'level': reg_user.level,
        #         'parent_id': str(reg_user.parent.id) if reg_user.parent else None
        #     }

        children = list()

        if reg_user.left_referrals_branch:
            child_data = graph_product_data(reg_user.left_referrals_branch, admin_panel, index + 1, max_line, False)

            if child_data:
                children.append(child_data)

        if reg_user.right_referrals_branch:
            child_data = graph_product_data(reg_user.right_referrals_branch, admin_panel,  index + 1, max_line, False)

            if child_data:
                children.append(child_data)

        result['children'] = children

        if is_started:
            result = [result]

            import pprint
            pprint.pprint(result)
    return result
