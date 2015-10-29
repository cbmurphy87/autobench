from datetime import timedelta
from flask import Flask
from flask.ext.login import LoginManager
from flask.ext.sqlalchemy import SQLAlchemy
from OpenSSL import SSL
from flask_sslify import SSLify

context = SSL.Context(SSL.TLSv1_2_METHOD)

myapp = Flask(__name__)
sslify = SSLify(myapp)
myapp.config.from_object('config')
db = SQLAlchemy(myapp)
lm = LoginManager()
lm.init_app(myapp)
lm.login_view = '_login'


if not myapp.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler('tmp/microblog.log', 'a',
                                       1 * 1024 * 1024, 10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: '
                                                '%(message)s [in %(pathname)s:'
                                                '%(lineno)d]'))
    myapp.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    myapp.logger.addHandler(file_handler)
    myapp.logger.info('microblog startup')


myapp.jinja_env.trim_blocks = True
myapp.jinja_env.lstrip_blocks = True
myapp.jinja_env.keep_trailing_newline = False
myapp.permanent_session_lifetime = timedelta(seconds=10)

from app import views, models
