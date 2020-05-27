import telebot

from src import config

from .logger_settings import logger
from .bot_states import BotStates
from .db_model.user import User


class BotHandlers(object):
    def __init__(self, token):
        self._bot = telebot.TeleBot(token)
        print(self.bot.get_me())
        self.__bot_state_handler = BotStates(self._bot)
        self.__start_handling()

    def __start_handling(self):
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            try:
                user = User.objects(user_id=message.chat.id).first()
                if user is None:
                    user = User()
                    user.user_id = message.chat.id
                    user.username = str(message.from_user.username)
                    user.state = 'start'
                    user.first_name = message.from_user.first_name
                    user.last_name = message.from_user.last_name
                    user.save()
                else:
                    User.objects(user_id=message.chat.id).update_one(state='start')
                self.__bot_state_handler.handle_state_with_message(message)
            except Exception as e:
                logger.exception(e)

        @self.bot.message_handler(content_types=['text'])
        def text_handler(message):
            try:
                self.__bot_state_handler.handle_state_with_message(message)
            except Exception as e:
                logger.exception(e)

        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_query_handler(call: telebot.types.CallbackQuery):
            try:
                self.__bot_state_handler.handle_state_with_call(call)
            except Exception as e:
                logger.exception(e)

        @self.bot.inline_handler(func=lambda query: len(query.query) > 0)
        def inline_handler(query: telebot.types.InlineQuery):
            try:
                self.__bot_state_handler.handle_state_with_query(query)
            except Exception as e:
                logger.exception(e)

        @self.bot.inline_handler(func=lambda query: len(query.query) is 0)
        def inline_empty_handler(query: telebot.types.InlineQuery):
            try:
                self.__bot_state_handler.handle_state_with_empty_query(query)
            except Exception as e:
                logger.exception(e)

        @self.bot.message_handler(content_types=['photo'])
        def handle_docs_photo(message):
            try:
                self.__bot_state_handler.handle_state_with_message(message)
            except Exception as e:
                logger.exception(e)

        @self.bot.message_handler(content_types=['contact'])
        def handle_contacts(message):
            try:
                self.__bot_state_handler.handle_state_with_message(message)
            except Exception as e:
                logger.exception(e)

        @self.bot.message_handler(content_types=['document'])
        def handle_contacts(message):
            try:
                self.__bot_state_handler.handle_state_with_message(message)
            except Exception as e:
                logger.exception(e)

    @property
    def bot(self) -> telebot.TeleBot:
        return self._bot


if __name__ == '__main__':
    bot_handler = BotHandlers(config.BOT_TOKEN)
    bot_handler.bot.remove_webhook()
    bot_handler.bot.polling(none_stop=True)
