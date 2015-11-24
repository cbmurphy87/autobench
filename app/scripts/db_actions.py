#!/usr/bin/python

from datetime import datetime
import re
from subprocess import Popen, PIPE

from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from aaebench.testautomation.syscontrol.smcipmi import SMCIPMIManager
from werkzeug.security import generate_password_hash

from app import myapp, db, models
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
    return ':'.join([mac[x:x+2] for x in range(0, len(mac), 2)])


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
    raise Exception('Could not get ip address.')


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


def update_server_info(form, _id):

    server = models.Servers.query.filter_by(id=_id).first()
    if not server:
        return 'Could not find server.'

    for field, data in form.data.items():
        if hasattr(server, field):
            setattr(server, field, data)

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

    # get vendor info
    r = requests.get('http://api.macvendors.com/{}'.format(mac_address))
    vendor = r.text
    logger.debug('Detected server vendor: {}'.format(vendor))
    if 'dell' in vendor.lower():
        logger.info('This server is a dell')
        return add_dell_info(nic_info=nic_info, form=form, user=user)
    elif 'supermicro' in vendor.lower():
        logger.info('This server is a Supermicro')
        return add_smc_info(nic_info=nic_info, form=form, user=user)
    else:
        logger.warning('Could not detect server type. Trying both.')

        try:
            return add_dell_info(nic_info=nic_info, form=form, user=user)
        except IOError:
            # else, it's supermicro, do this
            logger.debug('Not a dell server. try supermicro.')
            return add_smc_info(nic_info=nic_info, form=form, user=user)


def add_smc_info(nic_info, form, user):

    ip_address = nic_info.get('ip_address')

    # get server info here
    ipmi = SMCIPMIManager(hostname=ip_address, verbose=True)
    server_info = ipmi.get_server_info()

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

    # add objects to database
    logger.info('Adding objects to database')
    logger.debug(server.interfaces.all())
    try:
        for interface in server.interfaces:
            db.session.add(interface)
        db.session.add(server)
        db.session.commit()
    except InvalidRequestError:
        db.session.rollback()
        logger.debug("Non-unique server entry. Rolling back.")
    except IntegrityError as e:
        logger.debug('Server {} already there: {}'.format(server, e))
        return


def add_dell_info(nic_info, form, user):

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
    if not server_info:
        message = 'Error fetching data. Make sure server is connected.'
        logger.error(message)
        raise IOError(message)
    else:
        logger.debug(server_info)

    if 'drac' not in [x['name'].lower() for x in server_info.get('interfaces')]:
        message = 'Error getting server drac info.'
        logger.error(message)
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
    except InvalidRequestError:
        db.session.rollback()
        logger.warning("Non-unique server entry. Rolling back.")
    except IntegrityError as e:
        logger.debug('Server {} already there: {}'.format(server, e))
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
        except IntegrityError:
            db.session.rollback()
            logger.error('Could not add VD {}.'.format(new_vd))
        except InvalidRequestError:
            db.session.rollback()

    # get server drive info
    powered_on = racadm.get_power_status()

    if powered_on:
        drives = racadm.get_drive_info()
        check_or_add_drives(server, drives)
    else:
        message = 'Server is not powered on. Cannot get drive info.'
        logger.error(message)
        return message


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

    ip = get_ip_from_mac(mac)
    if not ip:
        logger.warning('Could not fetch ip address from mac {}'.format(mac))
        ip = interface.ip

    if not ip:
        message = 'Could not get an IP address for mac {}'.format(mac)
        logger.error(message)
        fail_job(job, message=message)
        raise MissingEntry(message)

    if ip != interface.ip:
        interface.ip = ip
        try:
            db.session.add(interface)
            db.session.commit()
        except Exception as e:
            message = 'Could not update interface.'
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
    except Exception as e:
        fail_job(job, message=e.message)
        logger.warning('Could not delete interfaces. Rolling back.')
        db.session.rollback()

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
        db.session.commit()

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
    except InvalidRequestError as e:
        message = "Non-unique server entry. Rolling back."
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        return
    except IntegrityError as e:
        message = 'Server {} already there: {}'.format(server, e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        return
    except Exception as e:
        message = 'Unknown exception: {}'.format(e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        return

    # set job as finished
    finish_job(job)


def update_dell_server(mac, user):

    # check that a server in inventory has that mac address and ip
    interface = models.NetworkDevices.query.filter_by(mac=mac).first()
    if not interface:
        logger.warning('No server found with that mac address.')
        return

    # check that the mac address is associated with an ip address
    ip = get_ip_from_mac(mac)
    if not ip:
        logger.warning('Could not fetch ip address from mac {}'.format(mac))
        ip = interface.ip
    if not ip:
        logger.error('Could not get ip address from interface.')
        raise MissingEntry('Could not get an IP address for mac {}'.format(mac))

    server = models.Servers.query.filter_by(id=interface.server_id).first()

    # create job
    job = create_job(user, message='Update server {}'.format(server.id))

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
        logger.error('Could not fetch info for server.')
        return

    # delete all interfaces
    interfaces = models.NetworkDevices.query \
        .filter_by(server_id=server.id).all()
    for interface in interfaces:
        db.session.delete(interface)
    try:
        db.session.commit()
    except IntegrityError as e:
        logger.error('Error deleting interfaces: {}'.format(e))
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
                logger.debug('key "{}" not in server:'.format(_k))
                logger.debug('-> {}: {}'.format(_k, _v))

    try:
        db.session.add(server)
        for interface in server.interfaces:
            db.session.add(interface)
        db.session.commit()
    except InvalidRequestError:
        message = "Non-unique server entry. Rolling back."
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
    except IntegrityError as e:
        message = 'Server {} already there: {}'.format(server, e)
        logger.error(message)
        db.session.rollback()
        fail_job(job, message=message)
        return

    # get server drive info
    powered_on = racadm.get_power_status()

    if powered_on:
        drives = racadm.get_drive_info()
        check_or_add_drives(server, drives)
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

    # set job as finished
    finish_job(job)

    logger.info('Success')


def check_or_add_drives(server, drives):

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
    except Exception as e:
        logger.error('Failed to delete drives for server {}: {}.'
                     .format(server.id, e))

    for drive in drives:
        logger.debug(drive)
        # check if drive MODEL is already in database
        drive_model, capacity = drive.get('model'), drive.get('capacity')
        try:
            logger.info('Checking if {} {} in database already.'
                        .format(capacity, drive_model))
            check = models.StorageDevices.query.filter_by(model=drive_model,
                                                          capacity=capacity) \
                .first()

            if not check:
                logger.info('Adding new drive {} to database.'
                            .format(drive_model))
                new_drive = models.StorageDevices()
                logger.debug(drive.items())
                for k, v in drive.items():
                    if hasattr(new_drive, k):
                        setattr(new_drive, k, v)
                try:
                    db.session.add(new_drive)
                    db.session.commit()
                except (IntegrityError, InvalidRequestError):
                    logger.debug('Drive {} already in database.'
                                .format(new_drive))
            else:
                logger.debug('Drive {} already in database.'.format(drive_model))

        except InvalidRequestError:
            logger.error('Error filtering query. Rolling back.')
            db.session.rollback()

        # add UNIQUE devices (with serial number) to server_storage table
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
                # add serial number, if found
                if _sn:
                    add_drive.serial_number = _sn
                db.session.add(add_drive)
                db.session.commit()
            except InvalidRequestError:
                db.session.rollback()
            except IntegrityError as e:
                logger.error('Could not add drive {} to server_storage: {}'
                             .format(_sn, e))


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

    all_jobs = models.Jobs.query.order_by('id').all()
    if all_jobs:
        return all_jobs
    return []


def get_job(_id):

    job = models.Jobs.query.filter_by(id=_id).first()
    return job


def delete_all_jobs():

    all_jobs = models.Jobs.query.all()
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
    print 'getting logger with name: {}'.format(__name__)
    logger = customlogger.get_logger(__name__)
