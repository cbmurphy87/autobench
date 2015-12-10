#!/usr/bin/python
from autobench import myapp

from aaebench import customlogger


def main():
    myapp.run(host='0.0.0.0', port=80, threaded=True, debug=True)

if __name__ == '__main__':
    logger = customlogger.create_logger('autobench')
    main()
else:
    logger = customlogger.get_logger(__name__)
