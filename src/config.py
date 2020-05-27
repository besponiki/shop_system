PROJECT_NAME = 'shop_system'
BOT_TOKEN = '651489467:AAGR03FuQYSYRQhM0vN1YSVwXWuDkFlbl3Y'
BOT_URL = PROJECT_NAME
#
WEBHOOK_HOST = 'telegram-bot.botup.pp.ua' # server ip address
WEBHOOK_PORT = 443
WEBHOOK_LISTEN_HOST = '127.0.0.1'  # In some VPS you may need to put here the IP addr
WEBHOOK_LISTEN_PORT = 10102

WEBHOOK_SSL_CERT = '/etc/letsencrypt/live/telegram-bot.mavas.pp.ua/fullchain.pem'  # Path to the ssl certificate

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s" % BOT_URL
EMAIL_LOGIN = 'freebie2kpy@gmail.com'
EMAIL_PASSWORD = 'podrybal1t1'
APPLYING_WAYS = ('bot', 'personal_panel')

CABINET_LINK = 'https://cabinet-shop-system.botup.pp.ua/'
CABINET_LINK_ADD_GGOD = 'https://cabinet-shop-system.botup.pp.ua/new_product'

DEFAULT_FIELDS_TAG = ['name', 'description', 'reward', 'price']