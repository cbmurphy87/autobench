#!/usr/bin/python

from app import db, models
from flask import flash
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from aaebench.testautomation.syscontrol.racadm import RacadmManager


def get_inventory():

    servers = models.Servers.query.all()

    for server in servers:
        drive_count = db.engine.execute("select server_id, count(model), "
                                        "model, capacity "
                                        "from server_storage as S "
                                        "join storage_devices as D "
                                        "where S.device_id=D.id "
                                        "and S.server_id='{}' "
                                        "group by D.model, D.capacity "
                                        "order by count(model) desc;"
                                        .format(server.id))

        setattr(server, 'drive_counts', [])
        for row in drive_count:
            server.drive_counts.append({'count': row['count(model)'],
                                        'model': row.model,
                                        'capacity': row.capacity})

    return servers


def add_inventory(form):

    """
    Add hardware to inventory
    :param entry: dictionary of entry values
    :type entry: dict
    :return: success of adding entry
    :rtype: bool
    """

    s = {
            'hostname': form.drac_ip.data,
            'username': 'root',
            'password': 'Not24Get',
            'verbose': True,
        }

    # get server info
    racadm = RacadmManager(**s)
    server_info = racadm.get_server_info()
    if not server_info:
        print 'Error fetching data. Make sure server is connected.'
    else:
        print server_info

    if 'drac' not in [x['name'].lower() for x in server_info.get('interfaces')]:
        print 'Error getting server drac info.'
        return

    # add server and its interfaces to database
    server = models.Servers(rack=form.rack.data, u=form.u.data)
    for interface in server_info['interfaces']:
        _i = models.NetworkDevices()
        for _k, _v in interface.items():
            if hasattr(_i, _k):
                setattr(_i, _k, _v)
        server.interfaces.append(_i)

    for _k, _v in server_info.items():
        if _k != 'interfaces':
            if hasattr(server, _k):
                setattr(server, _k, _v)
            else:
                print 'key "{}" not in server:'.format(_k)
                print '-> {}: {}'.format(_k, _v)

    try:
        db.session.add(server)
        for interface in server.interfaces:
            db.session.add(interface)
        db.session.commit()
    except InvalidRequestError:
        db.session.rollback()
        print "Non-unique server entry. Rolling back."
    except IntegrityError as e:
        print 'Server {} already there: {}'.format(server, e)
        return

    # get server drive info
    powered_on = racadm.get_power_status()

    if powered_on:
        drives = racadm.get_drive_info()
        check_or_add_drives(server, drives)
    else:
        print 'Server is not powered on. Cannot get drive info.'


def get_power_status(mac):

    # check that a server in inventory has that mac address and ip
    interface = models.NetworkDevices.query.filter_by(mac=mac).first()
    if not interface:
        print 'No server found with that mac address.'
        return

    # check that the mac address is associated with an ip address
    ip = interface.ip
    server = models.Servers.query.filter_by(id=interface.server_id).first()
    if not ip:
        print 'No ip address found for server {}.'\
            .format()
        return
    print 'Getting power status for server at {}'.format(ip)

    s = {
            'hostname': ip,
            'username': 'root',
            'password': 'Not24Get',
            'verbose': True,
        }

    racadm = RacadmManager(**s)
    return racadm.get_power_status()


def remove_inventory(_id):

    try:
        s = models.Servers.query.get(_id)
        print s
    except IntegrityError as e:
        print 'Could not remove hardware: {}'.format(e)
        return e


def update_inventory(mac):

    # check that a server in inventory has that mac address and ip
    interface = models.NetworkDevices.query.filter_by(mac=mac).first()
    if not interface:
        print 'No server found with that mac address.'
        return

    # check that the mac address is associated with an ip address
    ip = interface.ip
    server = models.Servers.query.filter_by(id=interface.server_id).first()
    if not ip:
        print 'No ip address found for server {}.'\
            .format()
        return
    print 'Updating server at {}'.format(ip)

    s = {
            'hostname': ip,
            'username': 'root',
            'password': 'Not24Get',
            'verbose': True,
        }

    racadm = RacadmManager(**s)
    new_info = racadm.get_server_info()

    # get new info
    if not new_info:
        print 'Could not fetch info for server.'
        return

    # delete all interfaces
    interfaces = models.NetworkDevices.query \
        .filter_by(server_id=server.id).all()
    for interface in interfaces:
        db.session.delete(interface)
    try:
        db.session.commit()
    except IntegrityError as e:
        print 'Error deleting interfaces: {}'.format(e)
        db.session.rollback()

    for interface in new_info['interfaces']:
        _i = models.NetworkDevices()
        for _k, _v in interface.items():
            if hasattr(_i, _k):
                setattr(_i, _k, _v)
        server.interfaces.append(_i)

    for _k, _v in new_info.items():
        if _k != 'interfaces':
            if hasattr(server, _k):
                setattr(server, _k, _v)
            else:
                print 'key "{}" not in server:'.format(_k)
                print '-> {}: {}'.format(_k, _v)

    try:
        db.session.add(server)
        for interface in server.interfaces:
            db.session.add(interface)
        db.session.commit()
    except InvalidRequestError:
        print "Non-unique server entry. Rolling back."
        db.session.rollback()
    except IntegrityError as e:
        print 'Server {} already there: {}'.format(server, e)
        db.session.rollback()
        return

    # get server drive info
    powered_on = racadm.get_power_status()

    if powered_on:
        drives = racadm.get_drive_info()
        check_or_add_drives(server, drives)
    else:
        print 'Server is not powered on. Cannot get drive info.'

    # get server virtual drive info
    try:
        old_drives = models.VirtualStorageDevices.query \
            .filter_by(server_id=server.id).all()
        for _drive in old_drives:
            db.session.delete(_drive)
        db.session.commit()
    except Exception as e:
        print 'Error deleting VDs: {}'.format(e)

    drives = racadm.get_vdisks()
    for _drive in drives:
        new_vd = models.VirtualStorageDevices(server_id=server.id)
        for k, v in _drive.items():
            if hasattr(new_vd, k):
                setattr(new_vd, k, v)
        try:
            db.session.add(new_vd)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print 'Could not add VD {}.'.format(new_vd)
        except InvalidRequestError:
            db.session.rollback()

    print 'Success'


def check_or_add_drives(server, drives):

    """
    Check if drives are in database, else add them, since they are foreign
    keys for the ServerStorage model.

    :param drives: list of dictionaries of discovered drives
    :type drives: list
    """

    # delete old entries to allow for new updated ones
    try:
        print 'Deleting all drives for server {}.'.format(server.id)
        old_entries = models.ServerStorage.query\
            .filter_by(server_id=server.id).all()
        for entry in old_entries:
            db.session.delete(entry)
        db.session.commit()
    except Exception as e:
        print 'Failed to delete drives for server {}: {}.'.format(server.id, e)

    for drive in drives:
        print drive

        # check if drive model is already in database
        drive_model, capacity = drive.get('model'), drive.get('capacity')
        try:
            print 'Checking if {} {} in database already.'\
                .format(capacity, drive_model)
            check = models.StorageDevices.query.filter_by(model=drive_model,
                                                          capacity=capacity) \
                .first()

            if not check:
                print 'Adding new drive {} to database.'.format(drive_model)
                new_drive = models.StorageDevices()
                print drive.items()
                for k, v in drive.items():
                    if hasattr(new_drive, k):
                        setattr(new_drive, k, v)
                try:
                    db.session.add(new_drive)
                    db.session.commit()
                except (IntegrityError, InvalidRequestError):
                    print 'Drive {} already in database.'.format(new_drive)
            else:
                print 'Drive {} already in database.'.format(drive_model)

        except InvalidRequestError:
            print 'Error filtering query. Rolling back.'
            db.session.rollback()

        # add unique devices to server_storage table
        for slot, _id in drive['ids'].items():
            try:
                if not _id:
                    message = 'No serial number found for drive in slot {}. ' \
                              'Check that server is powered on.'.format(slot)
                    print message
                    flash(message)
                    continue
                device_id = models.StorageDevices.query.\
                    filter_by(model=drive['model'],capacity=drive['capacity'])\
                    .first()
                if not device_id:
                    message = 'No info found for drive in slot {}. ' \
                              'Not adding drive to inventory.'\
                        .format(drive.get('slot'))
                    print message
                    flash(message)
                    continue
                if models.ServerStorage.query.filter_by(id=_id).first():
                    print 'Drive {} already in database.'.format(_id)
                    continue
                db.session.add(models.ServerStorage(id=_id,
                                                    device_id=device_id.id,
                                                    server_id=server.id,
                                                    slot=slot))
                db.session.commit()
            except InvalidRequestError as e:
                db.session.rollback()
            except IntegrityError as e:
                print 'Could not add drive {} to server_storage: {}'\
                    .format(_id, e)


def main():
    servers = get_inventory()
    for server in servers:
        print server
        for drive in server.drive_counts:
            print drive['count'], drive['model'], drive['capacity']

if __name__ == '__main__':
    main()
