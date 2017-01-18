import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'mysql://localhost/autobench'
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_TRACK_MODIFICATIONS = False

MONGOALCHEMY_DATABASE = 'autobench'
MONGOALCHEMY_TIMEZONE = 'US/Central'

WTF_CSRF_ENABLED = False
SECRET_KEY = 'youwillneverguess'
TIMEZONE = 'US/Central'

PERMANENET_SESSION_LIFETIME = timedelta(minutes=1)
