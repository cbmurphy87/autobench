import logging
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from flask import Flask, session
from flask_login import LoginManager
from flask_mongoalchemy import MongoAlchemy
from flask_pymongo import PyMongo
from flask_sqlalchemy import SQLAlchemy

from autobench.jinja.custom_filters import _split, _datetime_format

# setup autobench
myapp = Flask(__name__)
myapp.config.from_object('config')
# db = SQLAlchemy(myapp)
mongo_alchemy = MongoAlchemy(myapp)
print 'mongo_alchemy timezone:', mongo_alchemy.session.timezone

lm = LoginManager()
lm.init_app(myapp)
lm.login_view = '_login'

# setup logging
file_handler = RotatingFileHandler('autobench.log', 'a',
                                   1 * 1024 * 1024, 10)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: '
                                            '%(message)s [in %(pathname)s:'
                                            '%(lineno)d]'))
myapp.logger.setLevel(logging.INFO)
file_handler.setLevel(logging.INFO)
myapp.logger.addHandler(file_handler)

# configure environment
myapp.jinja_env.trim_blocks = True
myapp.jinja_env.lstrip_blocks = True
myapp.jinja_env.keep_trailing_newline = False
myapp.permanent_session_lifetime = timedelta(seconds=10)
myapp.jinja_env.filters['split'] = _split
myapp.jinja_env.filters['datetime_format'] = _datetime_format

from autobench import mongo_views, mongo_models
