#!/usr/bin/python
from app import db, models

servers = [
    {'id': 'HZKDR22',
     'oob_mac': 'b0:83:fe:e1:28:08',
     'ib_mac': 'b0:83:fe:e1:84:44',
     'model': 'R730xd',
     'cpu_count': 2,
     'cpu_model': 'E5-2690v3',
     'memory_capacity': '128GB',
     'rack': 3,
     'u': 31,
     'available': False}
]

for server in servers:
    s = models.Servers(**server)
    db.session.add(s)

db.session.commit()
