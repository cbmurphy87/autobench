#!/usr/bin/python

from datetime import datetime
import re
from subprocess import Popen, PIPE

from flask import render_template
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from aaebench.testautomation.syscontrol.smcipmi import SMCIPMIManager
from werkzeug.security import generate_password_hash

from autobench import myapp, db, models
from autobench_exceptions import *
import requests

from aaebench import customlogger
from aaebench.testautomation.syscontrol.file_transfer import SFTPManager
from aaebench.parents.managers import GenericManager


# =========================== User METHODS ============================
def update_my_info(form, user):

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


# ========================== Server METHODS ===========================
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


# =========================== Admin METHODS ===========================
def add_user(form, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    # First, check if user with that email already exists
    existing_user = models.Users.query.filter_by(email=form.email.data).first()
    if existing_user:
        return 'A user with that E-mail already exists!'
    # If a username if given, check if that username already exists
    if form.user_name.data:
        existing_user = models.Users.query\
            .filter_by(user_name=form.user_name.data).first()
        if existing_user:
            return 'That username is already taken!'

    new_user = models.Users()
    for field, data in form.data.items():
        if hasattr(new_user, field):
            if field == 'password':
                setattr(new_user, field, generate_password_hash(data))
            else:
                setattr(new_user, field, data)
    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        logger.error('Error updating user info: {}'.format(e))
        db.session.rollback()
        return 'Could not add user.'

    return 'Successfully added user {}.'.format(new_user)


def update_user_info(form, user_id, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    update_user = models.Users.query.filter_by(id=user_id).first()

    for field, data in form.data.items():
        if hasattr(update_user, field):
            if field == 'password':
                if data:
                    setattr(update_user, field, generate_password_hash(data))
            else:
                setattr(update_user, field, data)

    try:
        db.session.add(update_user)
        db.session.commit()
    except Exception as e:
        logger.error('Error updating user info: {}'.format(e))
        db.session.rollback()
        return 'Could not update info.'

    return 'Successfully updated user info.'


def delete_user(user_name, user):
    if not user.admin:
        return 'YOU ARE NOT ADMIN!'
    user_to_delete = models.Users.query.filter_by(user_name=user_name).first()
    if user_to_delete == user:
        return 'YOU CANNOT DELETE YOURSELF!'
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
    except:
        db.session.rollback()
        return 'Could not delete user {}'.format(user_name)

    return 'Successfully deleted user {}.'.format(user_name)


def add_group(form, user):

    # check if the group exists
    if models.Groups.query.filter_by(group_name=form.group_name.data).first():
        return 'Already a group with that name.'
    group = models.Groups(group_name=form.group_name.data,
                          description=form.description.data)
    try:
        db.session.add(group)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return 'Could not add group.'

    return 'Successfully added group {}'.format(form.group_name.data)


def delete_group(gid, user):
    if not user.admin:
        return 'YOU ARE NOT ADMIN!'
    group_to_delete = models.Groups.query.filter_by(id=gid).first()

    try:
        db.session.delete(group_to_delete)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return 'Could not delete group {}: {}'.format(gid, e)

    return 'Successfully deleted group {}.'.format(gid)


def update_group_info(form, group_id, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    group = models.Groups.query.filter_by(id=group_id).first()

    for field, data in form.data.items():
        if hasattr(group, field):
            setattr(group, field, data)

    try:
        db.session.add(group)
        db.session.commit()
    except Exception as e:
        logger.error('Error updating group info: {}'.format(e))
        db.session.rollback()
        return 'Could not update group info.'

    return 'Successfully updated group info.'


def add_group_member(form, group_id, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    group = models.Groups.query.filter_by(id=group_id).first()
    user = models.Users.query.filter_by(id=form.member.data.id).first()

    group.members.append(user)

    try:
        db.session.add(group)
        db.session.commit()
    except Exception as e:
        logger.error('Error adding group member: {}'.format(e))
        db.session.rollback()
        return 'Could not add group member.'

    return 'Successfully added group member.'


def remove_group_member(gid, uid, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    group = models.Groups.query.filter_by(id=gid).first()
    user = models.Users.query.filter_by(id=uid).first()

    group.members.remove(user)

    try:
        db.session.add(group)
        db.session.commit()
    except Exception as e:
        logger.error('Error removing group member: {}'.format(e))
        db.session.rollback()
        return 'Could not remove group member.'

    return 'Successfully removed group member.'


def add_group_server(form, group_id, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    group = models.Groups.query.filter_by(id=group_id).first()
    server = models.Servers.query.filter_by(id=form.server.data.id).first()

    group.servers.append(server)

    try:
        db.session.add(group)
        db.session.commit()
    except Exception as e:
        logger.error('Error adding group member: {}'.format(e))
        db.session.rollback()
        return 'Could not add group member.'

    return 'Successfully added group member.'


def remove_group_server(gid, sid, user):

    if not user.admin:
        return 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'

    group = models.Groups.query.filter_by(id=gid).first()
    server = models.Servers.query.filter_by(id=sid).first()

    group.servers.remove(server)

    try:
        db.session.add(group)
        db.session.commit()
    except Exception as e:
        logger.error('Error removing group server: {}'.format(e))
        db.session.rollback()
        return 'Could not remove server from group.'

    return 'Successfully removed server from group.'


# ========================= Inventory METHODS =========================
def get_inventory(user):
    # return only servers in your group
    if user.admin:
        server_list = [s.id for s in models.Servers.query.all()]
    else:
        user_groups = set([group.id for group in user.groups])
        all_servers = []
        for group in user.groups:
            for server in group.servers:
                all_servers.append(server)
        server_list = set([s.id for s in all_servers])

    servers = models.Servers.query\
        .order_by('rack', 'u', 'make', 'model')\
        .filter(models.Servers.id.in_(server_list)).all()

    # add drive into to each selected server
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
        return add_dell_info(nic_info=nic_info, form=form, user=user, job=job)
    elif 'super' in vendor.lower():
        message = 'Detected server as Supermicro.'
        logger.info(message)
        return add_smc_info(nic_info=nic_info, form=form, user=user, job=job)
    else:
        message = 'Could not explicitly detect server type.'
        logger.warning(message)
        try:
            return add_dell_info(nic_info=nic_info, form=form, user=user,
                                 job=job)
        except IOError:
            # else, it's supermicro, do this
            logger.debug('Not a dell server. try supermicro.')
            return add_smc_info(nic_info=nic_info, form=form, user=user,
                                job=job)


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
        db.session.rollback()
        fail_job(job, message=message)

    finish_job(job)


def add_smc_info(nic_info, form, user, job):

    ip_address = nic_info.get('ip_address')

    # get server info here
    ipmi = SMCIPMIManager(hostname=ip_address, username=form.user_name.data,
                          password=form.password.data, verbose=True)
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
    server = models.Servers(rack=form.rack.data, u=form.u.data,
                            user_name=form.user_name.data,
                            password=form.password.data)
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
            'username': form.user_name.data,
            'password': form.password.data,
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
    server = models.Servers(rack=form.rack.data, u=form.u.data,
                            user_name=form.user_name.data,
                            password=form.password.data)
    # add primary group
    if form.group.data:
        server.group_id = form.group.data.id
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


def update_smc_server(server, user):

    if not server:
        logger.warning('No server selected.')
        return

    # create job
    job = create_job(user, message='Update server {}'.format(server.id))

    # check that the mac address is associated with an ip address
    try:
        interface = server.interfaces.filter_by(type='oob').first()
        ip = get_ip_from_mac(interface.mac)

    except Exception as e:
        message = 'Could not get an IP address from DHCP: {}'.format(e)
        logger.warning(message)
        add_job_detail(job, message=message)
        ip = interface.ip
        message = 'Trying stored IP address.'
        logger.debug(message)
        add_job_detail(job, message=message)

    if not ip:
        message = 'No ip address found for server {}.'.format(server)
        logger.error(message)
        fail_job(job, message=message)
        return

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


def update_dell_server(server, user):

    if not server:
        logger.warning('No server selected.')
        return

    # create job
    job = create_job(user, message='Update server {}'.format(server.id))

    # check that the mac address is associated with an ip address
    interface = server.interfaces.filter_by(type='oob').first()
    try:
        ip = get_ip_from_mac(interface.mac)

    except Exception as e:
        message = 'Could not get an IP address from DHCP: {}'.format(e)
        logger.warning(message)
        add_job_detail(job, message=message)
        ip = interface.ip
        message = 'Trying stored IP address: {}'.format(ip)
        logger.debug(message)
        add_job_detail(job, message=message)

    if not ip:
        message = 'No ip address found for server {}.'.format(server)
        logger.error(message)
        fail_job(job, message=message)
        return

    # set job as pending
    pending_job(job)

    logger.info('Updating server at {}'.format(ip))
    if not server.user_name:
        logger.info('No username in database.')
        fail_job(job, 'No username found. Please add username to server info.')
        return
    if not server.password:
        logger.info('No password in database.')
        fail_job(job, 'No password found. Please add password to server info.')

    s = {
            'hostname': ip,
            'username': server.user_name,
            'password': server.password,
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
    except Exception as e:
        message = 'Error updating server info: {}'.format(e)
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
            db.session.rollback()
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
        db.session.rollback()
        message = 'Error deleting interfaces: {}'.format(e)
        logger.error(message)
        add_job_detail(job, message=message)


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
        db.session.rollback()
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
                    db.session.rollback()
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


# ============================ JOB METHODS ============================
def deploy_server(form, user):
    message = 'Deploying {} {} to {} with ks {}.'.format(form.os.data.flavor,
                                                         form.os.data.version,
                                                         form.target.data.id,
                                                         form.os.data.append)
    logger.info(message)

    pxe_file = render_template('pxeboot',
                               kernel=form.os.data.kernel,
                               initrd=form.os.data.initrd,
                               append=form.os.data.append)

    # gather data
    server = form.target.data
    server_type = server.make
    interfaces = server.interfaces
    eth0_interface = interfaces.filter_by(name='NIC.1').first()
    eth0 = eth0_interface.mac.lower().replace(':', '-')
    logger.debug('eth0 mac: {}'.format(eth0))
    ipmi_int = interfaces.filter_by(name='DRAC').first() or \
               interfaces.filter_by(name='ipmi').first()
    if not ipmi_int:
        raise Exception('Could not find ipmi interface!')
    ipmi_ip = ipmi_int.ip

    logger.debug('IPMI ip address is: {}'.format(ipmi_ip))

    # send unique config file to pxe server
    sftp = SFTPManager('pxe.aae.lcl')
    client = sftp.create_sftp_client()
    filename = '/tftpboot/pxelinux.cfg/01-{}'.format(eth0)
    # write file
    with client.open(filename, 'w') as f:
        f.write(pxe_file)
    # delete salt key
    logger.debug(server.id)
    salt_master_manager = GenericManager(hostname='salt-gru.aae.lcl',
                                         username='salt',
                                         password='Not24Get',
                                         local=False,
                                         ending='$')
    command = ['salt-key', '-d', str(server.id), '-y']
    salt_master_manager.connection.exec_command(' '.join(command))

    # reboot server to PXE
    if server_type.lower() == 'dell':
        logger.debug('Detected server is a Dell. Using RACADM.')
        ipmi = RacadmManager(ipmi_ip)
    else:
        logger.debug('Detected server is not a Dell. Using IPMI.')
        ipmi = SMCIPMIManager(ipmi_ip)

    ipmi.boot_once('PXE', reboot=True)

    # make server unavailable
    try:
        server = models.Servers.query.filter_by(id=server.id).first()
        server.available = False
        server.held_by = user.id
        db.session.commit()
        logger.info('Server {} now unavailable.'.format(server))
    except Exception as e:
        logger.error('Error making server unavailable: {}'.format(e))
        db.session.rollback()


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


def get_job(id_):

    job = models.Jobs.query.filter_by(id=id_).first()
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


# ========================== PROJECT METHODS ==========================
def get_all_projects():

    all_projects = models.Projects.query \
        .order_by(models.Projects.id.desc()).all()
    if all_projects:
        return all_projects
    return []


def get_project_by_id(id_):

    project = models.Projects.query \
        .filter_by(id=id_).first()
    return project


def get_project_by_name(name):

    project = models.Projects.query \
        .filter_by(name=name).first()
    return project


def add_project(form, user):

    new_project = models.Projects(owner_id=user.id)
    for field, value in form.data.items():
        if hasattr(new_project, field):
            setattr(new_project, field, value)
        else:
            logger.debug('Attr {} from form is not in project.'.format(field))

    try:
        db.session.add(new_project)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        message = 'Error adding project: {}'.format(e)
        logger.debug(message)
        return message


def delete_project(project, user):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'

    try:
        db.session.delete(project)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        message = 'Failed to delete project: {}'.format(e)
        logger.error(message)
        return message

    message = 'Successfully deleted project.'
    logger.debug(message)
    return message


def edit_project(project_id, user, form):

    project = models.Projects.query.filter_by(id=project_id).first()

    if not ((project.owner == user) or user.admin):
        return 'You do not own this project!'

    for field, data in form.data.items():
        if hasattr(project, field) and data:
            if field == 'owner_id':
                data = data.id
            setattr(project, field, data)

    try:
        db.session.add(project)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        message = 'Error editing project info: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully updated project info.'


def add_project_member(form, user, project):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'
    new_member = form.member.data
    project.members.append(new_member)

    try:
        db.session.add(project)
        db.session.commit()
    except Exception as e:
        error = 'Error adding member: {}'.format(e)
        logger.error(error)
        db.session.rollback()
        return error

    return 'Successfully added member!'


def remove_project_member(user, project, member):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'

    project.members.remove(member)

    try:
        db.session.add(project)
        db.session.commit()
    except Exception as e:
        error = 'Error removing member: {}'.format(e)
        logger.error(error)
        db.session.rollback()
        return error

    return 'Successfully removed member!'


def add_project_server(form, user, project):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'
    server = models.Servers.query.filter_by(id=form.server.data.id).first()
    server.project_id = project.id

    try:
        db.session.add(server)
        db.session.commit()
    except Exception as e:
        error = 'Error adding server: {}'.format(e)
        logger.error(error)
        db.session.rollback()
        return error

    return 'Successfully added server!'


def remove_project_server(user, project, server_id):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'
    server = models.Servers.query.filter_by(id=server_id).first()
    server.project_id = None

    try:
        db.session.add(server)
        db.session.commit()
    except Exception as e:
        error = 'Error removing server from project: {}'.format(e)
        logger.error(error)
        db.session.rollback()
        return error

    return 'Successfully removed server!'


def add_project_status(form, user, project_id):

    project = models.Projects.query.filter_by(id=project_id).first()

    if not ((user == project.owner) or (user in project.members) or user.admin):
        return 'You are not the project owner!'

    new_status = models.ProjectStatus(pid=project.id,
                                      date=form.date.data,
                                      engineer_id=user.id,
                                      message=form.message.data)
    project.statuses.append(new_status)
    try:
        db.session.add(project)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        message = 'Error adding status: {}'.format(e)
        logger.error(message)
        return message

    message = 'Successfully added status!'
    logger.debug(message)
    return message


def remove_project_status(user, project_id, status_id):

    project = models.Projects.query.filter_by(id=project_id).first()
    status = models.ProjectStatus.query.filter_by(pid=project_id,
                                                  id=status_id).first()
    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'

    try:
        project.statuses.remove(status)
        db.session.add(project)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        message = 'Error removing status: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully removed status!'


def main():

    with myapp.app_context():
        mac = '00:50:56:81:7b:ee'
        print get_ip_from_mac(mac)

if __name__ == '__main__':
    logger = customlogger.create_logger(__name__)
    main()
else:
    logger = customlogger.get_logger(__name__)