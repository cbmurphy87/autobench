#!/usr/bin/python

from .. import db, models
from sqlalchemy.exc import IntegrityError


def add_inventory(form):

    """
    Add hardware to inventory
    :param entry: dictionary of entry values
    :type entry: dict
    :return: success of adding entry
    :rtype: bool
    """

    d = {}
    try:
        for key in ('id', 'oob_mac', 'ib_mac', 'model', 'cpu_count',
                    'cpu_model', 'memory_capacity', 'rack', 'u'):
            d[key] = getattr(form, key).data
    except KeyError as e:
        print 'Key Error: {}'.format(e)
        return 'Error'

    try:
        s = models.Servers(**d)
        db.session.add(s)
        db.session.commit()
        print 'Successfully added hardware to database.'
    except IntegrityError as e:
        print 'Error adding hardware to database: {}'.format(e)
        return e


def remove_inventory(id):

    try:
        s = models.Servers.query.get(id)
        print s
    except IntegrityError as e:
        print 'Could not remove hardware: {}'.format(e)
        return e