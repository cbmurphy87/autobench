#!/usr/bin/python
from app import db, models


def load_users():
    users = [
        {'first_name': 'Collin',
         'last_name': 'Murphy',
         'email': 'cmurphy@micron.com'},
        {'first_name': 'Wes',
         'last_name': 'Vaske',
         'email': 'wvaske@micron.com'},
        {'first_name': 'Ryan',
         'last_name': 'Meredith',
         'email': 'rmeredith@micron.com'},
        {'first_name': 'Sujit',
         'last_name': 'Somandepalli',
         'email': 'sujit@micron.com'},
        {'first_name': 'Jason',
         'last_name': 'Burroughs',
         'email': 'jburroughs@micron.com'},
        {'first_name': 'John',
         'last_name': 'Terpstra',
         'email': 'jterpstra@micron.com'},
        {'first_name': 'Ananda',
         'last_name': 'Sankaran',
         'email': 'asankaran@micron.com'},
        {'first_name': 'Dennis',
         'last_name': 'Lattka',
         'email': 'dlattka@micron.com'}
    ]

    all_users = models.Users.query.all()

    for user in all_users:
        db.session.delete(user)

    db.session.commit()

    for user in users:
        u = models.Users(first_name=user['first_name'], last_name=user['last_name'],
                         email=user['email'])
        db.session.add(u)

    db.session.commit()

if __name__ == '__main__':
    load_users()
