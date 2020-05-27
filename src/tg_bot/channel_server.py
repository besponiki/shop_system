import flask
from telebot import types
from mongoengine import connect

from src import config
from .bot_handlers import BotHandlers

connect(config.PROJECT_NAME, alias='default')

app = flask.Flask(__name__)
bot_handler = BotHandlers(config.BOT_TOKEN)


@app.route(config.WEBHOOK_URL_PATH, methods=['POST', 'GET'])
def web_hook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot_handler.bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)
