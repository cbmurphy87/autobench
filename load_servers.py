#!/usr/bin/python
from app import db, models

servers = [
    {'id': 'HZKDR22',
     'oob_mac': 'b0:83:fe:e1:28:08',
     'ib_mac': 'b0:83:fe:e1:84:44'}
]

for server in servers:
    s = models.Servers(**server)
    db.session.add(s)

db.session.commit()
