import sys
import os

from werkzeug.contrib.fixers import ProxyFix

from src.web_admin_panel.service import app

sys.path.append(os.getcwd())


# run web admin panel
def run():
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run(host='0.0.0.0', port=11000, debug=True)


if __name__ == '__main__':
    run()
