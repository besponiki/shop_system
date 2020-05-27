import sys
import os
import time

from werkzeug.contrib.fixers import ProxyFix

from src.tg_bot.channel_server import *

sys.path.append(os.getcwd())


# run tg bot service
def run():
    bot_handler.bot.remove_webhook()
    time.sleep(1)
    bot_handler.bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH)

    app.wsgi_app = ProxyFix(app.wsgi_app)

    app.run(host=config.WEBHOOK_LISTEN_HOST,
            port=config.WEBHOOK_LISTEN_PORT,
            threaded=True,
            debug=True
            )


if __name__ == '__main__':
    run()
