from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import timedelta
from flask.ext.login import LoginManager
from aaebench import customlogger

app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.jinja_env.keep_trailing_newline = False
app.config.from_object('config')
app.permanent_session_lifetime = timedelta(seconds=10)


lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'

db = SQLAlchemy(app)

app.jinja_env.trim_blocks = True

from app import views, models


ADMINS = ['aae@micron.com', 'cmurphy@micron.com']
if not app.debug:
    logger = customlogger.create_logger('aaebench')
