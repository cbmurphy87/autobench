#!/usr/bin/python

import os

paths = [r'/opt/MicronTechnology/',
         r'/root/autobench/',
         r'c:\Program Files\MicronTechnology']

pthlocation = '/usr/lib/python2.7/site-packages'
pthfile = 'aaepaths.pth'

with open(os.path.join(pthlocation, pthfile), 'w') as pth:
    pth.write('\n'.join(paths))
