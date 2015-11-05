#!/usr/bin/python
from app import myapp

myapp.debug = True

myapp.run(host='0.0.0.0', port=80, threaded=True, debug=True)
