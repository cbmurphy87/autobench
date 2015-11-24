#!/usr/bin/python
from autobench import myapp

from aaebench import customlogger


def main():
    myapp.run(host='0.0.0.0', port=8080, threaded=True, debug=False)

if __name__ == '__main__':
    print 'creating logger with name: {}'.format(__name__)
    logger = customlogger.create_logger('autobench')
    main()
else:
    print 'getting logger with name: {}'.format(__name__)
    logger = customlogger.get_logger(__name__)
