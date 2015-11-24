#!/usr/bin/python
from autobench import db, models
from werkzeug.security import generate_password_hash


def load_users():
    users = [
        {'first_name': 'Collin',
         'last_name': 'Murphy',
         'email': 'cmurphy@micron.com',
         'admin': True},
        {'first_name': 'Wes',
         'last_name': 'Vaske',
         'email': 'wvaske@micron.com',
         'admin': True},
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
         'email': 'dlattka@micron.com'},
        {'first_name': 'LOCKED',
         'last_name': 'USER',
         'email': 'lock',
         'password': 'CrAzYlOnGpAsSwOrDfOrLoCkAcCoUnT'}
    ]

    existing_users = models.Users.query

    for user in users:
        existing_user = existing_users.filter_by(email=user['email']).first()
        if existing_user:
            print 'User {} already exists. Updating.'.format(str(existing_user))
            for k, v in user.items():
                setattr(existing_user, k, v)
        else:
            password = generate_password_hash(user.get('password', 'Not24Get'))
            new_user = models.Users(first_name=user['first_name'],
                                    last_name=user['last_name'],
                                    user_name=user['email'].split('@')[0],
                                    email=user['email'], password=password)
            db.session.add(new_user)

    db.session.commit()

if __name__ == '__main__':
    load_users()
