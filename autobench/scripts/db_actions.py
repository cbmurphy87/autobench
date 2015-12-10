#!/usr/bin/python

from datetime import datetime
import re
from subprocess import Popen, PIPE

from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from aaebench.testautomation.syscontrol.smcipmi import SMCIPMIManager
from werkzeug.security import generate_password_hash

from autobench import myapp, db, models
from autobench_exceptions import *
import requests

from aaebench import customlogger


# ============== User METHODS ======================
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
        logger.error('Error updating user info: {}'.format(e))
        db.session.rollback()
        return 'Could not update info.'

    return 'Successfully updated your info.'


# ============== Server METHODS ===================
def is_mac(check):

    search_string = re.compile(r'(?is)'
                               r'^(?:[0-9a-fA-F]{2}[:-]?){5}[0-9a-fA-F]{2}$')
    return bool(search_string.search(check))


def format_mac(mac):

    mac = mac.replace(':', '')
    mac = mac.replace('-', '')
    mac = mac.lower()
    assert len(mac) == 12 and mac.isalnum(), 'MAC is in invalid form.'
    return ':'.join([mac[x:x+2].upper() for x in range(0, len(mac), 2)])


def get_ip_from_mac(mac):

    command = 'ssh aaebench@atxlab.aae.lcl ' \
              '"cat /var/lib/dhcp/db/dhcpd.leases"'
    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    leases, errors = p.communicate()

    if errors and not leases:
        logger.error("errors:\n{}".format(errors))
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
    raise Exception('No IP for MAC {} in DHCP leases file.'.format(mac))


def get_mac_from_ip(ip):

    command = 'ssh aaebench@atxlab.aae.lcl ' \
              '"cat /var/lib/dhcp/db/dhcpd.leases"'
    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    leases, errors = p.communicate()

    if errors and not leases:
        logger.error("errors:\n{}".format(errors))
        raise IOError("Could not read dhcpd leases file: {}".format(errors))

    sstring = r'(?is)' \
              r'lease\s+' \
              r'(?P<ip_address>\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}).*?' \
              r'hardware\s+ethernet\s+' \
              r'(?P<mac>\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2})'

    addresses = [m.groupdict() for m in re.finditer(sstring, leases)
                 if m.groupdict().get('ip_address') == ip]

    if addresses:
        return addresses.pop().get('mac')
    raise Exception('Could not get mac address.')


def edit_server_info(form, _id):

    server = models.Servers.query.filter_by(id=_id).first()
    if not server:
        return 'Could not find server.'

    for field, data in form.data.items():
        if hasattr(server, field) and type(data) in (str, unicode):
            logger.debug('Setting field {} to {}.'.format(field, data))
            setattr(server, field, data)
        elif hasattr(server, field):
            if not data:
                message = 'Setting other field {} to None.'.format(field)
                setattr(server, field, None)
            else:
                message = 'Setting other field {} to {}.'.format(field, data.id)
                setattr(server, field, data.id)
            logger.debug(message)

    try:
        db.session.add(server)
        db.session.commit()
    except Exception as e:
        logger.error('Error updating server info: {}'.format(e))
        db.session.rollback()
        return 'Could not update server info.'

    return 'Successfully updated server info.'


# ============== Inventory METHODS =================
def get_inventory():

    servers = models.Servers.query.order_by('rack', 'u', 'make', 'model').all()
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
    if is_mac(form.network_address.data):
        mac_address = format_mac(form.network_address.data)
        try:
            ip_address = get_ip_from_mac(mac_address)
        except:
            ip_address = 'unknown'
    else:
        ip_address = form.network_address.data
        try:
            mac_address = get_mac_from_ip(ip_address)
        except:
            mac_address = 'unknown'

    nic_info = {'ip_address': ip_address,
                'mac_address': mac_address}

    job = create_job(user, message='Adding server at {}'.format(ip_address))

    # get vendor info
    r = requests.get('http://api.macvendors.com/{}'.format(mac_address))
    vendor = r.text
    logger.debug('Detected server vendor: {}'.format(vendor))
    if 'dell' in vendor.lower():
        message = 'Detected server as Dell.'
        logger.info(message)
        return add_dell_info(nic_info=nic_info, form=form, user=user)
    elif 'super' in vendor.lower():
        message = 'Detected server as Supermicro.'
        logger.info(message)
        return add_smc_info(nic_info=nic_info, form=form, user=user)
    else:
        message = 'Could not explicitly detect server type.'
        logger.warning(message)
        try:
            return add_dell_info(nic_info=nic_info, form=form, user=user)
        except IOError:
            # else, it's supermicro, do this
            logger.debug('Not a dell server. try supermicro.')
            return add_smc_info(nic_info=nic_info, form=form, user=user)


def add_interface(form, server_id, user):

    """
    Add interface to server. Used to add oob interface for management.
    """

    # get server object
    server = models.Servers.query.filter_by(id=server_id).first()

    # create job
    job = create_job(user, message='Add oob interface to {}'.format(server))

    # set job as pending
    pending_job(job)

    # get ip address either from field, or translate from mac address
    if is_mac(form.network_address.data):
        mac_address = format_mac(form.network_address.data)
        try:
            ip_address = get_ip_from_mac(mac_address)
            add_job_detail(job, message='Got ip address {}'.format(ip_address))
        except:
            ip_address = None
            message = 'Could not get ip address for mac {}'.format(mac_address)
            logger.warning(message)
            add_job_detail(job, message=message)
    else:
        ip_address = form.network_address.data
        try:
            mac_address = get_mac_from_ip(ip_address)
        except:
            message = 'Could not get mac address for ip {}'.format(ip_address)
            logger.error(message)
            fail_job(job, message=message)

    server_make = server.make

    new_interface = models.NetworkDevices(server_id=server_id)
    new_interface.mac = format_mac(mac_address)
    new_interface.ip = ip_address
    if server_make.lower() == 'dell':
        new_interface.name = 'DRAC'
    else:
        new_interface.name = 'ipmi'
    new_interface.slot = 'Dedicated'
    new_interface.type = 'oob'

    try:
        db.session.add(new_interface)
        db.session.commit()
        add_job_detail(job, 'Added {}'.format(new_interface))
    except Exception as e:
        message = 'Error adding {}: {}'.format(new_interface, e)
        logger.error(message)
        fail_job(job, message=message)

    finish_job(job)


def add_smc_info(nic_info, form, user, job):

    ip_address = nic_info.get('ip_address')

    # get server info here
    ipmi = SMCIPMIManager(hostname=ip_address, verbose=True)
    server_info = ipmi.get_server_info()

    if server_info:
        message = 'Got server info.'
        logger.debug(message)
        add_job_detail(job, message=message)
    else:
        message = 'Failed to get server info.'
        logger.error(message)
        fail_job(job, message=message)
        raise IOError(message)

    # add models objects for server and its interfaces
    logger.info('Creating server and interface objects.')
    server = models.Servers(rack=form.rack.data, u=form.u.data)
    server.held_by = user.id
    server.make = 'Supermicro'

    for interface in server_info['interfaces']:
        _i = models.NetworkDevices()
        for _k, _v in interface.items():
            if hasattr(_i, _k):
                setattr(_i, _k, _v)
        server.interfaces.append(_i)
    logger.info('Updating server object.')
    logger.debug(server_info.items())
    for _k, _v in server_info.items():
        if _k != 'interfaces':
            if hasattr(server, _k):
                setattr(server, _k, _v)
            else:
                logger.debug('key "{}" not in server:'.format(_k))
                logger.debug('-> {}: {}'.format(_k, _v))
    add_job_detail(job, message='Created interface objects.')

    # add objects to database
    logger.info('Adding objects to database')
    logger.debug(server.interfaces.all())
    try:
        for interface in server.interfaces:
            db.session.add(interface)
        db.session.add(server)
        db.session.commit()
        add_job_detail(job, message='Added interface objects to database.')
    except InvalidRequestError as e:
        db.session.rollback()
        logger.debug("Non-unique server entry. Rolling back.")
        fail_job(job, message='Failed to add interface '
                              'objects to database: {}'.format(e))
        return
    except IntegrityError as e:
        db.session.rollback()
        logger.debug('Server {} already there: {}'.format(server, e))
        fail_job(job, message='Failed to add interface '
                              'objects to database: {}'.format(e))
        return

    # get server drive info
    powered_on = ipmi.get_power_status()
    message = 'Server is{} powered on'.format('' if powered_on else ' not')
    add_job_detail(job, message=message)
    logger.debug(message)

    drives = ipmi.get_drive_info()
    if drives:
        message = 'Got drive info.'
        check_or_add_drives(server, drives, job)
    else:
        message = 'Could not get drive info.'
    add_job_detail(job, message=message)

    # delete server virtual drive info
    try:
        old_drives = models.VirtualStorageDevices.query \
            .filter_by(server_id=server.id).all()
        for _drive in old_drives:
            db.session.delete(_drive)
        db.session.commit()
        add_job_detail(job, message='Deleted all old VD entries.')
    except Exception as e:
        db.session.rollback()
        message = 'Error deleting VDs: {}'.format(e)
        logger.error(message)
        fail_job(job, message=message)

    # get virtual drive info
    drives = ipmi.get_vdisks()
    for _drive in drives:
        new_vd = models.VirtualStorageDevices(server_id=server.id)
        for k, v in _drive.items():
            if hasattr(new_vd, k):
                setattr(new_vd, k, v)
        try:
            db.session.add(new_vd)
            db.session.commit()
            message = 'Added {}'.format(new_vd)
            logger.info(message)
            add_job_detail(job, message=message)
        except IntegrityError:
            db.session.rollback()
            message = 'Could not add {}.'.format(new_vd)
            logger.error(message)
            fail_job(job, message=message)
            return
        except InvalidRequestError as e:
            db.session.rollback()
            fail_job(job, message=e.message)
            return

    finish_job(job)


def add_dell_info(nic_info, form, user, job):

    ip_address = nic_info.get('ip_address')
    logger.info('Checking ip: {}'.format(ip_address))

    s = {
            'hostname': ip_address,
            'username': 'root',
            'password': 'Not24Get',
            'verbose': True,
        }

    # get server info
    racadm = RacadmManager(**s)
    server_info = racadm.get_server_info()

    if server_info:
        message = 'Got server info.'
        logger.debug(message)
        add_job_detail(job, message=message)
    else:
        message = 'Failed to get server info.'
        logger.error(message)
        fail_job(job, message=message)
        raise IOError(message)

    if 'drac' not in [x['name'].lower() for x in server_info.get('interfaces')]:
        message = 'Error getting server drac info.'
        logger.error(message)
        fail_job(job, message)
        return message

    # add models objects for server and its interfaces
    server = models.Servers(rack=form.rack.data, u=form.u.data)
    for interface in server_info.get('interfaces', tuple()):
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
                logger.debug('key "{}" not in server:'.format(_k))
                logger.debug('-> {}: {}'.format(_k, _v))

    server.held_by = user.id
    server.make = 'Dell'

    try:
        for interface in server.interfaces:
            db.session.add(interface)
        db.session.add(server)
        db.session.commit()
        for interface in server.interfaces:
            add_job_detail(job, message='Added {}'.format(interface))
    except InvalidRequestError:
        db.session.rollback()
        message = "Non-unique server entry. Rolling back."
        fail_job(job, message=message)
        logger.warning(message)
    except IntegrityError as e:
        db.session.rollback()
        message = 'Server {} already there: {}'.format(server, e)
        logger.debug(message)
        add_job_detail(job, message=message)
        return

    # get virtual disks
    drives = racadm.get_vdisks()
    for _drive in drives:
        new_vd = models.VirtualStorageDevices(server_id=server.id)
        for k, v in _drive.items():
            if hasattr(new_vd, k):
                setattr(new_vd, k, v)
        try:
            db.session.add(new_vd)
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            message = 'Could not add VD {}: {}'.format(new_vd, e)
            logger.error(message)
            add_job_detail(job, message=message)
        except InvalidRequestError as e:
            db.session.rollback()
            message = 'Could not add VD {}: {}'.format(new_vd, e)
            logger.error(message)
            add_job_detail(job, message=message)

    # get server drive info
    powered_on = racadm.get_power_status()
    message = 'Server is{} powered on'.format('' if powered_on else ' not')
    add_job_detail(job, message=message)
    logger.debug(message)

    if powered_on:
        drives = racadm.get_drive_info()
        check_or_add_drives(server, drives, job)
    else:
        message = 'Cannot get drive info.'
        logger.error(message)
        add_job_detail(job, message=message)
        finish_job(job)
        return message
    finish_job(job)


def get_power_status(mac):

    # check that a server in inventory has that mac address and ip
    interface = models.NetworkDevices.query.filter_by(mac=mac).first()
    if not interface:
        logger.warning('No server found with that mac address.')
        return

    # check that the mac address is associated with an ip address
    ip = interface.ip
    server = models.Servers.query.filter_by(id=interface.server_id).first()
    if not ip:
        logger.warning('No ip address found for server {}.'.format(server))
        return
    logger.info('Getting power status for server at {}'.format(ip))

    s = {
            'hostname': ip,
            'verbose': True,
        }

    if server.make.lower() == 'dell':
        racadm = RacadmManager(**s)
        return racadm.get_power_status()
    ipmi = SMCIPMIManager(**s)
    return ipmi.get_power_status()


def remove_inventory(_id):

    server = models.Servers.query.filter_by(id=_id).first()
    drives = server.drives
    try:
        for drive in drives:
            db.session.delete(drive)
        db.session.commit()
        db.session.delete(server)
        db.session.commit()
        logger.info('Server successfully deleted.')
    except Exception as e:
        logger.error('Error deleting server {}: {}'.format(_id, e))
        db.session.rollback()

    try:
        s = models.Servers.query.get(_id)
        logger.debug(s)
    except IntegrityError as e:
        logger.error('Could not remove hardware: {}'.format(e))
        return e


def update_smc_server(mac, user):

    # check that the mac address is associated with an ip address
    interface = models.NetworkDevices.query.filter_by(mac=mac).first()
    server = models.Servers.query.filter_by(id=interface.server_id).first()

    # create job
    job = create_job(user, message='Update server {}'.format(server.id))

    try:
        ip = get_ip_from_mac(mac)
    except Exception as e:
        message = 'Could not get an IP address: {}'.format(e)
        logger.warning(message)
        ip = interface.ip
        fail_job(job, message=message)

    if ip != interface.ip:
        interface.ip = ip
        try:
            db.session.add(interface)
            db.session.commit()
            add_job_detail(job, 'Changed interface {} ip to {}.'
                           .format(interface, ip))
        except Exception as e:
            message = 'Could not update interface {}: {}.'.format(interface, e)
            db.session.rollback()
            fail_job(job, message=message)

    pending_job(job)
    logger.info('Updating server {} at {}'.format(server, ip))

    s = {
            'hostname': ip,
            'verbose': True,
        }

    ipmi = SMCIPMIManager(**s)
    new_info = ipmi.get_server_info()

    # get new info
    if not new_info:
        message = 'Could not fetch info for server.'
        logger.error(message)
        fail_job(job, message=message)
        return

    # delete all interfaces
    logger.info('Deleting interfaces')
    interfaces = models.NetworkDevices.query \
        .filter_by(server_id=server.id).all()
    for _i in interfaces:
        if _i.type != 'oob':
            db.session.delete(_i)

    try:
        logger.debug('Committing interface deletes')
        db.session.commit()
        add_job_detail(job, "Deleted all existing ib interfaces.")
    except Exception as e:
        message = 'Could not delete interfaces. Rolling back: {}'.format(e)
        fail_job(job, message=message)
        logger.warning(message)
        db.session.rollback()

    try:
        update_server_info(server, new_info, job)
    except:
        message = 'Error updating server info.'
        logger.error(message)
        fail_job(job, message=message)
        return

    # get server drive info
    try:
        drives = ipmi.get_drive_info()
        logger.debug('Found drives: {}'.format(drives))
        check_or_add_drives(server, drives, job)
    except Exception as e:
        logger.warning('Cannot get drive info: {}'.format(e))

    # get server virtual drive info
    try:
        old_drives = models.VirtualStorageDevices.query \
            .filter_by(server_id=server.id).all()
        for _drive in old_drives:
            db.session.delete(_drive)
        db.session.commit()
    except Exception as e:
        message = 'Error deleting VDs: {}'.format(e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)

    # get virtual drive info
    logger.info('Adding VDs.')
    drives = ipmi.get_vdisks()
    for _drive in drives:
        new_vd = models.VirtualStorageDevices(server_id=server.id)
        for k, v in _drive.items():
            if hasattr(new_vd, k):
                setattr(new_vd, k, v)
        try:
            db.session.add(new_vd)
            db.session.commit()
        except IntegrityError:
            message = 'Could not add VD {}.'.format(new_vd)
            logger.error(message)
            db.session.rollback()
            fail_job(job, message=message)
            return
        except InvalidRequestError as e:
            db.session.rollback()
            fail_job(job, message=e.message)
            return

    # set job as finished
    finish_job(job)


def update_dell_server(mac, user):

    # check that a server in inventory has that mac address and ip
    interface = models.NetworkDevices.query.filter_by(mac=mac).first()
    if not interface:
        logger.warning('No server found with that mac address.')
        return

    server = models.Servers.query.filter_by(id=interface.server_id).first()

    # create job
    job = create_job(user, message='Update server {}'.format(server.id))

    # check that the mac address is associated with an ip address
    try:
        ip = get_ip_from_mac(mac)
    except Exception as e:
        message = 'Could not get an IP address: {}'.format(e)
        logger.warning(message)
        ip = interface.ip
        fail_job(job, message=message)
        return

    if not ip:
        logger.error('No ip address found for server {}.'.format(server))
        return

    # set job as pending
    pending_job(job)

    logger.info('Updating server at {}'.format(ip))

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
        message = 'Could not fetch info for server.'
        logger.error(message)
        fail_job(job, message=message)
        return

    try:
        delete_all_interfaces(server.id, job)
    except Exception as e:
        fail_job(job, message='Failed to delete interfaces: {}'.format(e))

    try:
        update_server_info(server, new_info, job)
    except Exception:
        message = 'Error updating server info.'
        logger.error(message)
        fail_job(job, message=message)
        return

    # get server drive info
    powered_on = racadm.get_power_status()

    if powered_on:
        drives = racadm.get_drive_info()
        check_or_add_drives(server, drives, job)
    else:
        logger.warning('Server is not powered on. Cannot get drive info.')

    # get server virtual drive info
    try:
        old_drives = models.VirtualStorageDevices.query \
            .filter_by(server_id=server.id).all()
        for _drive in old_drives:
            db.session.delete(_drive)
        db.session.commit()
    except Exception as e:
        message = 'Error deleting VDs: {}'.format(e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)

    # get virtual drive info
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
            message = 'Could not add VD {}.'.format(new_vd)
            logger.error(message)
            db.session.rollback()
            fail_job(job, message=message)
            return
        except InvalidRequestError as e:
            db.session.rollback()
            fail_job(job, message=e.message)
            return

    try:
        mark_server_as_dirty(server.id, dirty=False)
    except Exception as e:
        message = 'Error setting server to not dirty: {}'.format(e)
        logger.error(message)
        fail_job(job, message=message)

    # set job as finished
    finish_job(job)

    logger.info('Success')


def mark_server_as_dirty(server_id, dirty=True):

    server = models.Servers.query.filter_by(id=server_id).first()
    logger.debug('Marking {} as {}.'.format(server,
                                            'dirty' if dirty else 'clean'))
    server.dirty = dirty
    db.session.add(server)
    db.session.commit()
    logger.debug('Server {} is now {}.'.format(server,
                                               'dirty' if dirty else 'clean'))


def update_server_info(server, new_info, job):

    # add found interfaces
    logger.info('Adding interfaces')
    for interface in new_info['interfaces']:
        # check if same interface already exists
        try:
            mac = interface.get('mac').lower()
            exists = models.NetworkDevices.query \
                .filter(and_(func.lower(models.NetworkDevices.mac) == mac,
                             models.NetworkDevices.server_id == server.id)) \
                .first()
        except IntegrityError as e:
            logger.debug('Skipping interface {}: {}'
                         .format(interface.get('mac'), e))
            continue
        if exists:
            logger.debug('Interface {} exists.'.format(exists))
            new_interface = exists
        else:
            logger.debug('Interface {} does not exist; creating new interface.'\
                .format(interface.get('mac')))
            new_interface = models.NetworkDevices()
        logger.debug('Setting attrs for interface {}.'.format(new_interface))
        for _k, _v in interface.items():
            if hasattr(new_interface, _k):
                logger.debug('Current {}: {}'.format(_k, getattr(new_interface,
                                                                 _k)))
                setattr(new_interface, _k, _v)
                logger.debug('New {}: {}'.format(_k, getattr(new_interface,
                                                             _k)))
        if not exists:
            logger.debug('Appending new interface')
            server.interfaces.append(new_interface)
        try:
            db.session.commit()
            add_job_detail(job, 'Added {}.'.format(new_interface))
        except Exception as e:
            message = 'Could not add {}: {}'.format(new_interface, e)
            logger.error(message)
            add_job_detail(job, message)

    logger.info('Adding server info')
    for _k, _v in new_info.items():
        if _k != 'interfaces':
            if hasattr(server, _k):
                if getattr(server, _k) != _v:
                    logger.debug("key '{}' hasn't changed:".format(_k))
                    logger.debug('-> {}: {}'.format(_k, _v))
                else:
                    logger.debug("key '{}' has changed:".format(_k))
                    logger.debug('-> {}: {}'.format(_k, _v))
                    setattr(server, _k, _v)
            else:
                logger.debug('key "{}" not in server:'.format(_k))
                logger.debug('-> {}: {}'.format(_k, _v))

    try:
        logger.info('Adding server to database.')
        db.session.add(server)
        logger.debug('Committing server')
        db.session.commit()
        add_job_detail(job, 'Added new server info to database.')
    except InvalidRequestError as e:
        message = "Non-unique server entry. Rolling back."
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        raise e
    except IntegrityError as e:
        message = 'Server {} already there: {}'.format(server, e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        raise e
    except Exception as e:
        message = 'Unknown exception: {}'.format(e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        raise e


def delete_all_interfaces(_id, job):

    # delete all interfaces
    interfaces = models.NetworkDevices.query \
        .filter_by(server_id=_id).all()
    for interface in interfaces:
        if interface.type != 'oob':
            db.session.delete(interface)
    try:
        db.session.commit()
        add_job_detail(job, message='Deleted all interfaces.')
    except IntegrityError as e:
        message = 'Error deleting interfaces: {}'.format(e)
        logger.error(message)
        add_job_detail(job, message=message)
        db.session.rollback()


def check_or_add_drives(server, drives, job):

    """
    Check if drives are in database, else add them, since they are foreign
    keys for the ServerStorage model.

    :param drives: list of dictionaries of discovered drives
    :type drives: list
    """

    # delete old entries to allow for new updated ones
    try:
        logger.info('Deleting all drives for server {}.'.format(server.id))
        old_entries = models.ServerStorage.query\
            .filter_by(server_id=server.id).all()
        for entry in old_entries:
            db.session.delete(entry)
        db.session.commit()
        add_job_detail(job, message='Deleted all drive info.')
    except Exception as e:
        logger.error('Failed to delete drives for server {}: {}.'
                     .format(server.id, e))
        add_job_detail(job, message='Failed to delete drive info.')

    for drive in drives:
        # check if drive MODEL is already in database
        drive_model, capacity = drive.get('model'), drive.get('capacity')
        try:
            logger.info('Checking if {} {} in database already.'
                        .format(capacity, drive_model))
            check = models.StorageDevices.query.filter_by(model=drive_model,
                                                          capacity=capacity) \
                .first()

            if not check:
                logger.info('Adding new drive {} {} to database.'
                            .format(capacity, drive_model))
                new_drive = models.StorageDevices()
                logger.debug(drive.items())
                for k, v in drive.items():
                    if hasattr(new_drive, k):
                        setattr(new_drive, k, v)
                try:
                    db.session.add(new_drive)
                    db.session.commit()
                    add_job_detail(job, message='Added new {} {} to database.'
                                   .format(capacity, drive_model))
                except (IntegrityError, InvalidRequestError) as e:
                    logger.debug('Drive {} already in database: {}'
                                 .format(new_drive, e))
            else:
                logger.debug('Drive {} already in database.'.format(drive_model))

        except InvalidRequestError as e:
            db.session.rollback()
            message = 'Error adding {}: {}'.format(drive, e)
            logger.error(message)
            add_job_detail(job, message=message)

        # add devices (with serial number) to server_storage table
        for slot, _sn in drive['sns'].items():
            try:
                if not _sn:
                    message = 'No serial number found for drive in slot {}. ' \
                              'Check that server is powered on.'.format(slot)
                    logger.warning(message)
                device_id = models.StorageDevices.query.\
                    filter_by(model=drive['model'], capacity=drive['capacity'])\
                    .first()
                if not device_id:
                    message = 'No info found for drive in slot {}. ' \
                              'Not adding drive to inventory.'\
                        .format(drive.get('slot'))
                    logger.error(message)
                    continue
                existing_drive = models.ServerStorage.query\
                    .filter_by(id=_sn).first()
                if existing_drive:
                    logger.debug('Drive {} already in database.'.format(_sn))
                    db.session.delete(existing_drive)
                    try:
                        db.session.commit()
                    except:
                        logger.error('Error deleting existing drive. '
                                     'Rolling back.')
                        db.session.rollback()
                        continue
                add_drive = models.ServerStorage(device_id=device_id.id,
                                                 server_id=server.id,
                                                 slot=slot)
                # add serial number, if found, else keep as None (NULL)
                if _sn:
                    add_drive.serial_number = _sn
                db.session.add(add_drive)
                db.session.commit()
                add_job_detail(job, message='Added {}'.format(drive))
            except IntegrityError:
                # drive is probably already in database; just change ownership
                db.session.rollback()
                try:
                    existing_drive = models.ServerStorage.query\
                        .filter_by(serial_number=_sn).first()

                    # make old drive owner server dirty
                    mark_server_as_dirty(existing_drive.server_id)

                    # change drive ownership
                    existing_drive.server_id = server.id
                    existing_drive.slot = slot
                    db.session.add(existing_drive)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    message = 'Error changing ownership of {}: {}'\
                        .format(existing_drive, e)
                    logger.error(message)
                    add_job_detail(job, message)
            except InvalidRequestError as e:
                db.session.rollback()
                message = 'Could not add {} to server_storage: {}'\
                    .format(drive, e)
                logger.warning(message)
                add_job_detail(job, message=message)

    finish_job(job)


# ============== JOB METHODS ======================
def create_job(user, message=''):

    # create job
    now = datetime.now().strftime('%y/%m/%d %H:%M:%S')
    update_job = models.Jobs(message=message,
                             owner_id=user.id, start_time=now,
                             status=1)
    try:
        db.session.add(update_job)
        db.session.commit()
    except:
        logger.error('Could not create job. Rolling back.')
        db.session.rollback()
        raise AutobenchException('Job creation failed')

    return update_job


def finish_job(job):

    # set job as finished
    job.status = 3
    job.end_time = datetime.now().strftime('%y/%m/%d %H:%M:%S')
    try:
        db.session.add(job)
        db.session.commit()
    except:
        logger.error('Could not finish job. Rolling back.')
        db.session.rollback()


def pending_job(job):

    # set job as finished
    job.status = 2
    try:
        db.session.add(job)
        db.session.commit()
    except Exception as e:
        logger.error('Could not set job to pending. Rolling back: {}'.format(e))
        db.session.rollback()


def add_job_detail(job, message):

    detail = models.JobDetails()
    detail.time = datetime.now().strftime('%y/%m/%d %H:%M:%S')
    detail.message = message
    job.details.append(detail)
    try:
        db.session.commit()
    except Exception as e:
        logger.error('Could not add detail to {}: {}'.format(job, e))
        db.session.rollback()


def fail_job(job, message=''):

    # set job as failed
    job.status = 4
    job.end_time = datetime.now().strftime('%y/%m/%d %H:%M:%S')
    add_job_detail(job, message)
    try:
        db.session.add(job)
        db.session.commit()
    except Exception as e:
        logger.error('Could not fail job. Rolling back: {}'.format(e))
        db.session.rollback()


def get_all_jobs():

    all_jobs = models.Jobs.query.order_by(models.Jobs.id.desc()).all()
    if all_jobs:
        return all_jobs
    return []


def get_job(_id):

    job = models.Jobs.query.filter_by(id=_id).first()
    return job


def delete_all_jobs():

    all_jobs = models.Jobs.query\
        .filter(models.Jobs.status != 2).all()
    for job in all_jobs:
        db.session.delete(job)
    try:
        db.session.commit()
        logger.info('Successfully deleted all jobs.')
    except Exception as e:
        logger.error('Could not delete all jobs. Rolling back: {}'.format(e))
        db.session.rollback()
        raise Exception('Could not delete jobs.')


def main():

    with myapp.app_context():
        mac = '00:50:56:81:7b:ee'
        print get_ip_from_mac(mac)

if __name__ == '__main__':
    logger = customlogger.create_logger(__name__)
    main()
else:
    logger = customlogger.get_logger(__name__)
