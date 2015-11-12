#!/usr/bin/python

from app import myapp, db, models, forms
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from werkzeug.security import generate_password_hash
from subprocess import Popen, PIPE
import re


def get_ip_from_mac(mac):

    command = 'ssh aaebench@atxlab.aae.lcl ' \
              '"cat /var/lib/dhcp/db/dhcpd.leases"'
    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    leases, errors = p.communicate()

    if errors and not leases:
        print "errors:\n{}".format(errors)
        raise IOError("Could not read dhcpd leases file: {}".format(errors))

    sstring = r'(?is)' \
              r'lease\s+' \
              r'(?P<ip_address>\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}).*?' \
              r'hardware\s+ethernet\s+' \
              r'(?P<mac>\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2})'

    addresses = [m.groupdict() for m in re.finditer(sstring, leases)
                 if m.groupdict().get('mac').lower() == mac.lower()]

    if addresses:
        return addresses.pop().get('ip_address')


def get_mac_from_ip(ip):

    command = 'ssh aaebench@atxlab.aae.lcl ' \
              '"cat /var/lib/dhcp/db/dhcpd.leases"'
    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    leases, errors = p.communicate()

    if errors and not leases:
        print "errors:\n{}".format(errors)
        raise IOError("Could not read dhcpd leases file: {}".format(errors))

    sstring = r'(?is)' \
              r'lease\s+' \
              r'(?P<ip_address>\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}).*?' \
              r'hardware\s+ethernet\s+' \
              r'(?P<mac>\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2})'

    addresses = [m.groupdict() for m in re.finditer(sstring, leases)
                 if m.groupdict().get('ip_address').lower() == ip.lower()]

    if addresses:
        return addresses.pop().get('ip_address')


def update_user_info(form, user):

    user = models.Users.query.filter_by(id=user.id).first()
    if not user:
        return 'Could not update info.'

    for field, data in form.data.items():
        if hasattr(user, field) and field != 'password':
            setattr(user, field, data)
    if form.new_password.data:
        if form.new_password.data == form.verify_new_password.data:
            new_password = generate_password_hash(form.new_password.data)
            if new_password:
                user.password = new_password
        else:
            return 'Passwords did not match.'

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        print 'Error updating user info: {}'.format(e)
        db.session.rollback()
        return 'Could not update info.'

    return 'Successfully updated your info.'


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


def add_inventory(form, user):

    """
    Add hardware to inventory
    :return: success of adding entry
    :rtype: bool
    """

    # get ip address either from field, or translate from mac address
    if len(form.drac_address.data) > 16:
        mac_address = form.drac_address.data
        ip_address = get_ip_from_mac(mac_address)
    else:
        ip_address = form.drac_address
        mac_address = get_mac_from_ip(ip_address)

    nic_info = {'ip_address': ip_address,
                'mac_address': mac_address}

    # if dell, do this
    try:
        return add_dell_info(nic_info=nic_info, form=form, user=user)
    except IOError:
        # else it's supermicro, and do this
        print 'not a dell server. try supermicro.'
        return add_smc_info(nic_info=nic_info, form=form, user=user)


def add_smc_info(nic_info, form, user):

    ip_address = nic_info.get('ip_address')
    mac_address = nic_info.get('mac_address')

    command = ['/root/SMCIPMITool_2.11.0/SMCIPMITool', ip_address, 'ADMIN',
               'ADMIN', 'ipmi', 'fru']
    smcipmi = Popen(command, stdout=PIPE, stderr=PIPE)
    system_info, errors = smcipmi.communicate()

    print 'info:\n{}'.format(system_info)
    if errors:
        print 'Errors:\n{}'.format(errors)

    ss = re.compile(r'(?is)'
                    r'Product\s+PartModel\s+Number\s+\(PPM\)\s+=\s+'
                    r'(?P<model>.*?)\s+'
                    r'Product\s+Version\s+\(PV\).+?'
                    r'Product\s+Serial\s+Number\s+\(PS\)\s+=\s+'
                    r'(?P<id>.+?)\s+')

    info = ss.search(system_info)
    if info:
        server_info = info.groupdict()
    else:
        print 'Could not get server info.'
        return

    server = models.Servers(rack=form.rack.data, u=form.u.data)
    server.held_by = user.id
    server.make = 'Supermicro'

    nic_info = {'name': 'ipmi',
                'ip': ip_address,
                'mac': mac_address,
                'slot': 'Dedicated',
                'type': 'oob',
                'server_id': server_info.get('id')}

    print 'Nic info: {}'.format(nic_info)

    ipmi_interface = models.NetworkDevices(**nic_info)
    server.interfaces.append(ipmi_interface)

    if info:
        print
        for _k, _v in server_info.items():
            if hasattr(server, _k):
                setattr(server, _k, _v)
            else:
                print 'key "{}" not in server:'.format(_k)
                print '-> {}: {}'.format(_k, _v)
    else:
        print 'error getting info'
        return

    try:
        db.session.add(server)
        db.session.add(ipmi_interface)
        db.session.commit()
    except InvalidRequestError:
        db.session.rollback()
        print "Non-unique server entry. Rolling back."
    except IntegrityError as e:
        print 'Server {} already there: {}'.format(server, e)
        return


def add_dell_info(nic_info, form, user):

    ip_address = nic_info.get('ip_address')
    mac_address = nic_info.get('mac_address')

    s = {
            'hostname': ip_address,
            'username': 'root',
            'password': 'Not24Get',
            'verbose': True,
        }

    # get server info
    racadm = RacadmManager(**s)
    server_info = racadm.get_server_info()
    if not server_info:
        message = 'Error fetching data. Make sure server is connected.'
        print message
        raise IOError(message)
    else:
        print server_info

    if 'drac' not in [x['name'].lower() for x in server_info.get('interfaces')]:
        message = 'Error getting server drac info.'
        print message
        return message

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

    server.held_by = user.id
    server.make = 'Dell'

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
        message = 'Server is not powered on. Cannot get drive info.'
        print message
        return message


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

        # check if drive MODEL is already in database
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

        # add UNIQUE devices (with serial number) to server_storage table
        for slot, _sn in drive['sns'].items():
            try:
                if not _sn:
                    message = 'No serial number found for drive in slot {}. ' \
                              'Check that server is powered on.'.format(slot)
                    print message
                device_id = models.StorageDevices.query.\
                    filter_by(model=drive['model'], capacity=drive['capacity'])\
                    .first()
                if not device_id:
                    message = 'No info found for drive in slot {}. ' \
                              'Not adding drive to inventory.'\
                        .format(drive.get('slot'))
                    print message
                    continue
                existing_drive = models.ServerStorage.query\
                    .filter_by(id=_sn).first()
                if existing_drive:
                    print 'Drive {} already in database.'.format(_sn)
                    db.session.delete(existing_drive)
                    try:
                        db.session.commit()
                    except:
                        print 'Error deleting existing drive. Rolling back.'
                        db.session.rollback()
                        continue
                add_drive = models.ServerStorage(device_id=device_id.id,
                                                 server_id=server.id,
                                                 slot=slot)
                # add serial number, if found
                if _sn:
                    add_drive.serial_number = _sn
                db.session.add(add_drive)
                db.session.commit()
            except InvalidRequestError:
                db.session.rollback()
            except IntegrityError as e:
                print 'Could not add drive {} to server_storage: {}'\
                    .format(_sn, e)


def main():

    with myapp.app_context():
        mac = '00:50:56:81:7b:ee'
        print get_ip_from_mac(mac)

if __name__ == '__main__':
    main()
