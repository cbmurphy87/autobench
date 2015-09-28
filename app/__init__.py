from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import timedelta
from flask.ext.login import LoginManager

app = Flask(__name__)
app.config.from_object('config')
app.permanent_session_lifetime = timedelta(seconds=10)
app.jinja_env.trim_blocks = True

lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'

db = SQLAlchemy(app)

app.jinja_env.trim_blocks = True

from app import views, models


ADMINS = ['aae@micron.com', 'cmurphy@micron.com']
if not app.debug:
    import logging
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler('127.0.0.1',
                               'server-error@aae.micron.com',
                               ADMINS, 'YourApplication Failed')
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)
