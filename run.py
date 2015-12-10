#!/usr/bin/python
from autobench import myapp

from aaebench import customlogger


def main():
    myapp.run(host='0.0.0.0', port=80, threaded=True)

if __name__ == '__main__':
    logger = customlogger.create_logger(__name__)
    main()
else:
    logger = customlogger.get_logger(__name__)