import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'mysql://localhost/autobench'

SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

WTF_CSRF_ENABLED = False
SECRET_KEY = 'youwillneverguess'

PERMANENET_SESSION_LIFETIME = timedelta(minutes=1)
