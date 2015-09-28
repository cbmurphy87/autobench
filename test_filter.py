#!flask/bin/python
import os
import fnmatch
import datetime

matches = []
for root, dirnames, filenames in os.walk(os.getcwd()):
  for filename in fnmatch.filter(filenames, '*.html'):
    print filename
    matches.append(os.path.join(root, filename))
print datetime.datetime.fromtimestamp(os.path.getctime(max(matches, key=os.path.getctime))).strftime('%b %d %Y')

