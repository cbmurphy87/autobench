#!/usr/bin/python
from app import myapp, context

myapp.run(host='0.0.0.0', port=500, threaded=True, ssl_context='adhoc',
          debug=True)
