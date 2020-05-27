import logging
from telebot import TeleBot, types
from types import FunctionType
from .db_model.user import User


class StateHandler(object):
    def __init__(self, bot: TeleBot):

        self._bot = bot
        self.__state_functions = {'start': self._start_state}

    def _start_state(self, message):
        try:
            self._bot.send_message(message.chat.id, 'Welcome message')
        except Exception as e:
            logging.exception(e)

    def handle_state_with_message(self, message: types.Message):
        user = User.objects(user_id=message.chat.id).first()

        if not user:
            user = User()
            user.user_id = message.chat.id
            user.username = str(message.from_user.username)
            user.state = 'start'
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name
            user.save()

        self.__state_functions[user['state']](message=message)

    def handle_state_with_call(self, call: types.CallbackQuery):
        user = User.objects(user_id=call.message.chat.id).first()

        if not user:
            user = User()
            user.user_id = call.message.chat.id
            user.username = str(call.message.from_user.username)
            user.state = 'start'
            user.first_name = call.message.from_user.first_name
            user.last_name = call.message.from_user.last_name
            user.save()

        state = user['state']
        if call.data:
            state_position_index = call.data.find('_inline_button')

            if state_position_index != -1:
                state = call.data[0:state_position_index]
                user.state = state
                user.save()
        self.__state_functions[state](message=call.message, call=call)

    def handle_state_with_query(self, query: types.InlineQuery):
        user = User.objects(user_id=query.from_user.id).first()

        if not user:
            user = User()
            user.user_id = query.from_user.id
            user.username = str(query.from_user.username)
            user.state = 'start'
            user.first_name = query.from_user.first_name
            user.last_name = query.from_user.last_name
            user.save()

        state = user['state']
        self.__state_functions[state](message=None, query=query)

    def handle_state_with_empty_query(self, empty_query: types.InlineQuery):
        user = User.objects(user_id=empty_query.from_user.id).first()

        if not user:
            user = User()
            user.user_id = empty_query.from_user.id
            user.username = str(empty_query.from_user.username)
            user.state = 'start'
            user.first_name = empty_query.from_user.first_name
            user.last_name = empty_query.from_user.last_name
            user.save()

        state = user['state']
        self.__state_functions[state](message=None, empty_query=empty_query)

    def __register_state(self, name, function_pointer: FunctionType):
        if name != '' and function_pointer is not None:
            self.__state_functions[name] = function_pointer

    def _register_states(self, states_list):
        for state_func in states_list:
            self.__register_state(state_func.__name__, state_func)

    def _go_to_state(self, message, state_name, *args, **kwargs):
        print('_go_to_state: {0}'.format(state_name))
        if str(type(state_name)) == "<class 'method'>":
            state_name = state_name.__name__
        if state_name in self.__state_functions:
            User.objects(user_id=message.chat.id).update_one(state=state_name)
        else:
            state_name = 'start'
            User.objects(user_id=message.chat.id).update_one(state=state_name)

        self.__state_functions[state_name](message, entry=True, *args, **kwargs)
