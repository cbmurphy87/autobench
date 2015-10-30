#!/usr/bin/python
from app import myapp, context

from flask_sslify import SSLify

SSLify(myapp)

myapp.run(host='0.0.0.0', port=443, threaded=True, ssl_context='adhoc')
