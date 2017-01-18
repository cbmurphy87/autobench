#!/usr/bin/python

# standard imports
from bson import DBRef, ObjectId
import fnmatch
from multiprocessing import Process
import os
import re
from datetime import datetime, date
from pymongo.errors import DuplicateKeyError
from subprocess import Popen, PIPE
from sqlalchemy import or_

# Flask imports
from flask import render_template, flash
import requests
from werkzeug.security import generate_password_hash

# autobench imports
from autobench import myapp, mongo_alchemy, mongo_models, \
    mongo_forms
from autobench_exceptions import *
from mongoalchemy.exceptions import BadReferenceException

# aaebench imports
from aaebench import customlogger
from aaebench.parents.managers import GenericManager
from aaebench.testautomation.syscontrol.file_transfer import SFTPManager
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from aaebench.testautomation.syscontrol.smcipmi import SMCIPMIManager

not_admin_message = 'YOU ARE NOT AN ADMIN AND SHOULD NOT BE HERE!!!'


# ___________________________ HELPER METHODS __________________________
def get_date_last_modified():
    date = '?'
    try:
        matches = []
        for root, dirnames, filenames in os.walk(os.getcwd()):
            for filename in fnmatch.filter(filenames, '*.html'):
                matches.append(os.path.join(root, filename))
        date = datetime.fromtimestamp(
                os.path.getctime(max(matches,
                                     key=os.path.getctime)))\
            .strftime('%b %d %Y')
    except:
        date = '?'
    finally:
        return date


def update_server(server_id, user):
    update_job = create_job(user, 'Update server {}'.format(server_id))
    try:
        server = mongo_models.Servers.query.filter_by(id=server_id).first()
        logger.info('Updating server {}.'.format(server.id))
        make = server.model.make.name.lower()
        if 'dell' in make:
            logger.debug('This server is a Dell')
            target = update_dell_server
        elif 'super' in make:
            logger.debug('This server is a Supermicro')
            target = update_smc_server
        else:
            message = 'Could not get server make'
            logger.error(message)
            raise Exception(message)
        p = Process(target=target, args=(server, user, update_job))
        p.start()
    except Exception as e:
        logger.error('Could not update server {}.: {}'.format(server_id, e))


# ________________________ Management METHODS _________________________
# method to run new debug
def _run_debug():
    test_path = os.path.join(os.getcwd(), 'unit_tests.py')
    p = Popen(test_path, stdout=PIPE, stderr=PIPE)
    response, err = p.communicate()
    with open(os.path.join(os.getcwd(), 'last_debug.out'), 'w+') as f:
        f.write(response)
        if err:
            f.write('\n\nErrors:\n')
            f.write(err)


# =========================== User METHODS ============================
def update_my_info(form, user):

    user = mongo_models.Users.query.filter_by(mongo_id=user.mongo_id).first()
    if not user:
        return 'Could not update info.'

    for field, data in form.data.items():
        if field in dir(user) and field != 'password':
            setattr(user, field, data)
    if form.new_password.data:
        if form.new_password.data == form.verify_new_password.data:
            new_password = generate_password_hash(form.new_password.data)
            if new_password:
                user.password = new_password
        else:
            return 'Passwords did not match.'

    try:
        user.save()
    except Exception as e:
        message = 'Could not update info: {}'.format(e)
        logger.error(message)
        return message

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


def flatten_mac(mac):
    mac = mac.replace('-', '')
    mac = mac.replace(':', '')
    return mac.lower()


def get_ip_from_mac(mac):

    host = 'aaebench@atxlab.aae.lcl'
    command = '"cat /var/lib/dhcp/db/dhcpd.leases"'
    p = Popen(' '.join(['ssh', host, command]), stdout=PIPE, stderr=PIPE,
              shell=True)
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
    raise Exception('No IP for MAC {} in DHCP leases file.'
                    .format(mac.lower()))


def get_mac_from_ip(ip):

    host = 'aaebench@atxlab.aae.lcl'
    command = '"cat /var/lib/dhcp/db/dhcpd.leases"'
    p = Popen(' '.join(['ssh', host, command]), stdout=PIPE, stderr=PIPE,
              shell=True)
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


# =========================== Admin METHODS ===========================
def add_user(form, user):

    if not user.admin:
        return not_admin_message

    # First, check if user with that email already exists
    existing_user = mongo_models.Users.query\
        .filter_by(email=form.email.data).first()
    if existing_user:
        return 'A user with that E-mail already exists!'
    # If a username if given, check if that username already exists
    if form.user_name.data:
        existing_user = mongo_models.Users.query\
            .filter_by(user_name=form.user_name.data).first()
        if existing_user:
            return 'That username is already taken!'
    password = generate_password_hash(form.password.data)
    new_user = mongo_models.Users(first_name=form.first_name.data,
                                  last_name=form.last_name.data,
                                  user_name=form.user_name.data,
                                  email=form.email.data,
                                  password=password)
    #for field, data in form.data.items():
    #    if hasattr(new_user, field):
    #        if field == 'password':
    #            setattr(new_user, field, generate_password_hash(data))
    #        else:
    #            setattr(new_user, field, data)
    try:
        new_user.save()
    except Exception as e:
        message = 'Could not add user: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully added user {}.'.format(new_user)


def delete_user(user_name, user):
    if not user.admin:
        return not_admin_message

    user_to_delete = mongo_models.Users.query \
        .filter_by(user_name=user_name).first()
    if user_to_delete == user:
        return 'YOU CANNOT DELETE YOURSELF!'
    try:
        user_to_delete.remove()
    except Exception as e:
        return 'Could not delete user {}: {}'.format(user_name, e)

    return 'Successfully deleted user {}.'.format(user_name)


def update_user_info(form, user_id, user):

    if not user.admin:
        return not_admin_message

    try:
        update_user = mongo_models.Users.query.filter_by(
            mongo_id=user_id).first()

        for field, data in form.data.items():
            if field in dir(update_user):
                if field == 'password':
                    if data:
                        setattr(update_user, field,
                                generate_password_hash(data))
                else:
                    setattr(update_user, field, data)

        update_user.save()
    except Exception as e:
        message = 'Could not update user info: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully updated user info.'


def add_group(form, user):

    if not user.admin:
        return not_admin_message

    # check if the group exists
    if mongo_models.Groups.query.filter_by(name=form.name.data).first():
        return 'Already a group with that name.'
    try:
        group = mongo_models.Groups(name=form.name.data,
                                    description=form.description.data)
        group.save()
    except Exception as e:
        return 'Could not add group: {}'.format(e)

    return 'Successfully added group {}'.format(form.name.data)


def delete_group(group_id, user):
    if not user.admin:
        return not_admin_message

    try:
        group_to_delete = mongo_models.Groups.query \
            .filter_by(mongo_id=group_id).first()
        group_to_delete.remove()
    except Exception as e:
        message = 'Could not delete group {}: {}'.format(group_id, e)
        logger.error(message)
        return message

    return 'Successfully deleted group {}.'.format(group_id)


# untested
def update_group_info(form, group_id, user):

    if not user.admin:
        return not_admin_message

    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()

    for field, data in form.data.items():
        if field in dir(group):
            setattr(group, field, data)

    try:
        group.save()
    except Exception as e:
        message = 'Could not update group info: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully updated group info.'


def add_group_member(form, group_id, user):

    if not user.admin:
        return not_admin_message

    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
    user = mongo_models.Users.query.filter_by(mongo_id=form.member.data.mongo_id) \
        .first()

    group.member_refs.append(user.to_ref())

    try:
        group.save()
    except Exception as e:
        message = 'Could not add group member: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully added group member.'


def remove_group_member(group_id, user_id, user):

    if not user.admin:
        return not_admin_message

    try:
        group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
        user = mongo_models.Users.query.filter_by(mongo_id=user_id).first()
        print type(group.members), group.members
        group.member_refs.remove(user.to_ref())
        group.save()
    except Exception as e:
        message = 'Could not remove group member: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully removed group member.'


def add_group_server(form, group_id, user):

    if not user.admin:
        return not_admin_message

    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
    server = mongo_models.Servers.query\
        .filter_by(mongo_id=form.server.data.mongo_id).first()

    server.group_ref = group.to_ref()

    try:
        server.save()
    except Exception as e:
        message = 'Could not add group server: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully added group server.'


def remove_group_server(group_id, server_id, user):

    if not user.admin:
        return not_admin_message

    try:
        # get group and server objects
        group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
        server = mongo_models.Servers.query.filter_by(id=server_id).first()
        if server.group != group:
            return 'This server is not in the group {}.'.format(group)
        # set server group
        server.group_ref = None
        # save server
        server.save()
    except Exception as e:
        message = 'Could not remove server from group: {}'.format(e)
        logger.error(message)
        return message
    message = 'Successfully removed server from group.'
    logger.debug(message)
    return message


# untested
def add_room(form, user):

    if not user.admin:
        return not_admin_message

    # check if the room exists
    if mongo_models.Rooms.query.filter_by(name=form.name.data).first():
        return 'Already a room with that name.'
    room = mongo_models.Rooms(name=form.name.data,
                              type_ref=form.type.data.to_ref(),
                              description=form.description.data)
    try:
        room.save()
    except Exception as e:
        message = 'Could not add room: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully added room {}'.format(form.name.data)


# untested
def delete_room(room_id, user):

    if not user.admin:
        return not_admin_message

    try:
        room_to_delete = mongo_models.Rooms.query \
            .filter_by(mongo_id=room_id).first()
        room_to_delete.remove()
    except Exception as e:
        message = 'Could not delete room {}: {}'.format(room_id, e)
        logger.error(message)
        return message

    return 'Successfully deleted room {}.'.format(room_id)


# untested
def edit_room_id(form, room_id, user):
    if not user.admin:
        return not_admin_message

    room = mongo_models.Rooms.query.filter_by(mongo_id=room_id).first()
    if not room:
        return 'Could not find room.'
    logger.debug("Found room {}".format(room))

    try:
        for field, data in form.data.items():
            if (field in dir(room)) and (type(data) in (str, unicode)):
                logger.debug('Setting field {} to {}.'.format(field, data))
                setattr(room, field, data)
            elif hasattr(room, field):
                if not data:
                    message = 'Setting other field {} to None.'.format(field)
                    setattr(room, field, None)
                else:
                    message = 'Setting other field {} to {}.'.format(field,
                                                                     data.id)
                    setattr(room, field, data.id)
                logger.debug(message)
        room.save()
    except Exception as e:
        message = 'Could not update room info: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully updated room info.'


def add_rack(form, user):

    if not user.admin:
        return not_admin_message

    # check if rack with that serial number exists,
    # since this is a unique identifier
    rack = None
    if form.serial_number.data:
        rack = mongo_models.Racks.query\
            .filter_by(serial_number=form.serial_number.data).first()
    if not rack:
        # else, check if the rack with that number exists in that room
        rack = mongo_models.Racks.query\
            .filter_by(location_ref=form.location.data.to_ref(),
                       number=form.number.data).first()
    if rack:
        message = 'Already a rack {} in room: {}' \
            .format(form.number.data, rack)
        logger.warning(message)
        return message

    try:
        rack = mongo_models.Racks(location_ref=form.location.data.to_ref(),
                                  model_ref=form.model.data.to_ref(),
                                  number=form.number.data,
                                  serial_number=form.serial_number.data)
        rack.save()
    except Exception as e:
        message = 'Could not add rack: {}'.format(e)
        logger.error(message)
        return message

    message = 'Successfully added rack {} to {}'.format(form.number.data,
                                                        form.location.name)
    logger.debug(message)
    return message


def add_rack_model(form, user):

    if not user.admin:
        return not_admin_message

    # check if that model already exists
    model = mongo_models.RackModels.query.filter_by(name=form.name.data) \
        .first()
    if model:
        message = 'Model {} already exists'.format(form.name.data)
        logger.warning(message)
        return message

    try:
        # first, create dimension document
        dimensions = mongo_models\
            .RackDimensionDocuments(units_ref=form.units.data.to_ref(),
                                    display_units_ref=form.units.data.to_ref(),
                                    width=form.width.data,
                                    height=form.height.data,
                                    depth=form.depth.data)
        model = mongo_models.RackModels(make_ref=form.make.data.to_ref(),
                                        name=form.name.data,
                                        dimensions=dimensions,
                                        number_of_units=form.number_of_units
                                        .data)
        model.save()

    except Exception as e:
        message = 'Could not add model: {}'.format(e)
        logger.error(message)
        return message

    message = 'Successfully added model {}.'.format(form.name.data)
    logger.debug(message)
    return message


# untested
def delete_rack(rack_id, user):
    if not user.admin:
        return not_admin_message

    rack_to_delete = mongo_models.Racks.query \
        .filter_by(mongo_id=rack_id).first()
    logger.debug('deleting rack {}'.format(rack_to_delete))

    try:
        rack_to_delete.remove()
    except Exception as e:
        message = 'Could not delete rack {}: {}'.format(rack_id, e)
        logger.error(message)
        return message

    return 'Successfully deleted rack {}.'.format(rack_id)


# untested
def edit_rack_id(form, rack_id, user):
    if not user.admin:
        return not_admin_message

    rack = mongo_models.Racks.query.filter_by(mongo_id=rack_id).first()
    if not rack:
        return 'Could not find rack.'
    logger.debug("Updating rack {}".format(rack))

    try:
        print dir(rack)
        print rack.__dict__
        for field, data in form.data.items():
            message = 'Rack does not have attr {}.'.format(field)
            if field in dir(rack):
                if type(data) in (str, unicode):
                    message = 'Setting field {} to {}.'.format(field, data)
                    setattr(rack, field, data)
                else:
                    if not data:
                        message = 'Setting other field {} to None.'\
                            .format(field)
                        setattr(rack, field, None)
                    else:
                        setattr(rack, field, data)
            logger.debug(message)
        rack.save()
    except Exception as e:
        message = 'Could not update rack info: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully updated rack info.'


# ========================= Inventory METHODS =========================
# unfinished
def get_inventory(user):

    inventory = {
        'servers': mongo_models.Servers.query.all(),
        'switches': mongo_models.Switches.query.all()
    }
    return inventory


def add_server(form, user):

    """
    Add hardware to inventory
    :return: success of adding entry
    :rtype: bool
    """

    # get ip address either from field, or translate from mac address
    fail_job_message = ''
    if is_mac(form.network_address.data):
        mac_address = format_mac(form.network_address.data)
        try:
            print 'mac: {}'.format(mac_address)
            ip_address = get_ip_from_mac(mac_address)
        except:
            fail_job_message = 'Could not get an IP address for that ' \
                               'MAC address.'
    else:
        ip_address = form.network_address.data
        try:
            mac_address = get_mac_from_ip(ip_address)
        except:
            fail_job_message = 'Could not get a MAC address for that ' \
                               'IP address.'

    job = create_job(user, description='Add new server.')
    if fail_job_message:
        fail_job(job, fail_job_message)
        return

    nic_info = {'ip_address': ip_address,
                'mac_address': mac_address}

    # get vendor info
    r = requests.get('http://api.macvendors.com/{}'.format(mac_address))
    vendor = r.text
    logger.debug('Detected server vendor: {}'.format(vendor))

    if 'dell' in vendor.lower():
        message = 'Detected server as Dell.'
        logger.info(message)
        return add_update_dell_server(idrac=nic_info, form=form, user=user,
                                      job=job)
    elif 'super' in vendor.lower():
        message = 'Detected server as Supermicro.'
        logger.info(message)
        return add_smc_server(nic_info=nic_info, form=form, user=user, job=job)
    else:
        message = 'Could not explicitly detect server type.'
        logger.warning(message)
        try:
            # assume it's a Dell, and try anyways
            return add_update_dell_server(idrac=nic_info, form=form, user=user,
                                          job=job)
        except IOError:
            # Else, it's possibly a Supermicro, so try that...
            logger.debug('Not a dell server. Trying supermicro...')
            return add_smc_info(nic_info=nic_info, form=form, user=user,
                                job=job)


def add_interface(form, server_id, user):

    """
    Add interface to server. Used to add oob interface for management.
    """

    # get server object
    server = mongo_models.Servers.query.filter_by(id=server_id).first()

    # create job
    job = create_job(user,
                     description='Add oob interface to {}'.format(server))

    # set job as pending
    pending_job(job)

    # get ip address either from field, or translate from mac address
    if is_mac(form.network_address.data):
        mac_address = format_mac(form.network_address.data)
        try:
            ip_address = get_ip_from_mac(mac_address)
            add_job_detail(job, message='Got ip address {}'.format(
                ip_address))
        except:
            ip_address = None
            message = 'Could not get ip address for mac {}'.format(
                mac_address)
            logger.warning(message)
            add_job_detail(job, message=message)
    else:
        ip_address = form.network_address.data
        try:
            mac_address = get_mac_from_ip(ip_address)
        except:
            message = 'Could not get mac address for ip {}'.format(
                ip_address)
            logger.error(message)
            fail_job(job, message=message)
            return

    server_make = server.model.make

    new_interface = mongo_models \
        .NetworkInterfaces(mac=flatten_mac(mac_address),
                           name='iDRAC' if 'dell' in str(server_make).lower()
                           else 'IPMI',
                           slot_type='Embedded',
                           slot=1,
                           type='oob')
    if ip_address:
        new_interface.ip = ip_address

    try:
        # delete orphaned interfaces, first
        new_int_ref_set = set()
        for interface_ref in server.interface_refs:
            try:
                logger.debug('Checking reference {}.'.format(interface_ref))
                mongo_alchemy.session.dereference(interface_ref)
                new_int_ref_set.add(interface_ref)
            except BadReferenceException:
                logger.warning('Bad reference. Removing reference {}.'
                               .format(interface_ref))
            except Exception as e:
                print 'Other exception: {}'.format(e)

        server.interface_refs = new_int_ref_set

        server.save()
        print 'new interface: {}'.format(new_interface)
        new_interface.save()
        for k, v in new_interface.__dict__['_values'].items():
            print k, v
        found = mongo_models.NetworkInterfaces.query\
            .filter_by(mac=new_interface.mac).first()
        print 'Found: {}'.format(found)
        print 'New: {}'.format(new_interface)
        new_interface.save()
        server.interface_refs.add(new_interface.to_ref())
        server.save()
        add_job_detail(job, 'Added {}'.format(new_interface))
    except Exception as e:
        message = 'Error adding {}: {}'.format(new_interface, e)
        logger.error(message)
        fail_job(job, message=message)
        print 'Failed'
        return

    finish_job(job)


# unfinished
def add_update_dell_server(idrac, form, user, job, server=None):

    if form:
        ip_address = idrac.get('ip_address')
    else:
        ip_address = get_ip_from_mac(idrac.formatted_mac)
    logger.info('Checking ip: {}'.format(ip_address))

    s = {
        'hostname': ip_address,
        'verbose': True,
    }
    if form:
        s.update({
            'username': form.user_name.data,
            'password': form.password.data,
        })
    elif idrac:
        s.update({
            'username': server.management.user_name,
            'password': server.management.password
        })
    else:
        fail_job(job, 'No iDRAC credentials. Can not complete update.')

    # get server info
    racadm = RacadmManager(**s)
    server_info = racadm.get_hw_inventory()

    if server_info:
        message = 'Got server info.'
        logger.debug(message)
        add_job_detail(job, message=message)
    else:
        message = 'Failed to get server info.'
        logger.error(message)
        fail_job(job, message=message)
        raise IOError(message)

    sys = server_info.get('system')[0]

    # check if manufacturer exists
    manufacturer = mongo_models.Manufacturers.query\
        .filter_by(name=sys.get('manufacturer')).first()
    if not manufacturer:
        manufacturer = mongo_models.Manufacturers(name=sys.get('manufacturer'))
        manufacturer.save()

    # check if model exists
    model = mongo_models.ServerModels.query \
        .filter_by(make_ref=manufacturer.to_ref(),
                   name=sys.get('model')).first()
    if not model:
        model = mongo_models.ServerModels(make_ref=manufacturer.to_ref(),
                                          name=sys.get('model'),
                                          height=int(
                                              sys.get('chassis_height')))
        if 'modular' in sys.get('system_generation').lower():
            model.modular = True
        model.save()

    server_id = sys.get('service_tag')
    server = mongo_models.Servers.query.filter_by(id=server_id).first()

    # add or update server
    if (not server) and (form is not None):
        credentials = mongo_models \
            .ManagementCredentials(user_name=form.user_name.data,
                                   password=form.password.data)
        try:
            server = mongo_models.Servers(id=server_id,
                                          model_ref=model.to_ref(),
                                          host_name=sys.get('host_name'),
                                          name=sys.get('host_name'),
                                          group_ref=form.group.data.to_ref(),
                                          bios_version=sys.get('bios_version'),
                                          management=credentials)

            # try to add bios date
            bios_date_search = re.compile(
                '(?is)'
                '(?P<month>\d+)/'
                '(?P<day>\d+)/'
                '(?P<year>\d+)'
            )
            bios_date = bios_date_search.search(sys.get('bios_date'))
            if bios_date:
                print 'setting server bios_date: {}'.format(bios_date)
                server.bios_date = date(**bios_date.groupdict())
            server.save()
            logger.debug('Successfully added server {}'.format(server.id))
            finish_job(job)
        except Exception as e:
            message = 'Could not create server: {}'.format(e)
            logger.error(message)
            fail_job(job=job, message=message)
    else:
        logger.debug('Server already exists. Updating server {}.'
                     .format(server.id))
        server.model_ref = model.to_ref()
        # try to add bios date
        server.bios_version = sys.get('bios_version')
        bios_date_search = re.compile(
            '(?is)'
            '(?P<month>\d+)/'
            '(?P<day>\d+)/'
            '(?P<year>\d+)'
        )
        bios_date = bios_date_search.search(sys.get('bios_date'))
        if bios_date:
            logger.debug('Setting server bios_date: {}'.format(bios_date))
            bios_dict = {k: int(v) for k, v in bios_date.groupdict().items()}
            server.bios_date = date(**bios_dict)
        server.host_name = sys.get('host_name')
        server.save()

    # add cpu info to server
    try:
        cpus = []
        for cpu in server_info.get('cpus'):
            model = get_cpu_model(cpu)
            socket_number = int(cpu.get('socket_number'))
            cpu_document = mongo_models.Cpus(model_ref=model.to_ref(),
                                             socket_number=socket_number)
            cpus.append(cpu_document)
        server.cpus = cpus
        server.save()
    except Exception as e:
        message = 'Could not add cpu info to server {}: {}'.format(server, e)
        logger.error(message)
        return message

    # add management info to server
    try:
        idrac = server_info.get('idrac')[0]
        # check if interface exists
        fmt_mac = idrac.get('mac_address').replace(':', '').lower()
        slot_type, slot = idrac.get('slot').split('.')[0:2]
        slot, port = slot.split('-')[:2]
        idrac_doc = mongo_models.NetworkInterfaces.query \
            .filter_by(mac=fmt_mac).first()
        if not idrac_doc:
            idrac_doc = mongo_models.NetworkInterfaces(
                mac=fmt_mac,
                name='iDRAC',
                slot_type=slot_type,
                slot=int(slot),
                port=int(port),
                type='oob')
            print idrac_doc
            if ip_address:
                idrac_doc.ip = ip_address
            idrac_doc.save()
        server.interface_refs.add(idrac_doc.to_ref())
        server.save()
    except Exception as e:
        message = 'Could not get iDRAC info: {}'.format(e)
        logger.warning(message)
        return message

    # add drives
    drive_info = racadm.get_drive_info()
    add_update_server_drives(server, drive_info)

    finish_job(job)

    logger.info('Successfully updated server {}.'.format(server.id))


def add_update_server_drives(server, drive_info):

    for drive in drive_info:
        # check if serial number already exists
        exists = mongo_models.Drives.query\
            .filter_by(serial_number=drive.get('serial_number')).first()
        if exists:
            continue


def update_dell_server(server, user, job):
    if not ((server.group in user.groups) or user.admin):
        return 'You do not have permission to update this server'
    # check that server has nic info
    server = mongo_models.Servers.query.filter_by(id=server.id).first()
    idrac = None
    for interface in server.interfaces:
        print interface, interface.type
        if interface.type == 'oob':
            idrac = interface

    add_update_dell_server(idrac=idrac, form=None, user=user, job=job,
                           server=server)


def get_cpu_model(cpu_info):

    # get manufacturer
    manufacturer = mongo_models.Manufacturers.query \
        .filter_by(name=cpu_info.get('manufacturer')).first()
    if not manufacturer:
        manufacturer = mongo_models.Manufacturers(name=cpu_info
                                                  .get('manufacturer'))
        manufacturer.save()
        logger.debug('Added manufacturer: {}'.format(manufacturer))
    else:
        logger.debug('Found existing manufacturer: {}'.format(manufacturer))
    # check if model exists
    cpu = mongo_models.CpuModels.query \
        .filter_by(make_ref=manufacturer.to_ref(),
                   name=cpu_info.get('model')).first()
    if cpu:
        logger.debug('Found existing CPU model: {}'.format(cpu))
        return cpu
    else:
        logger.debug("CPU model doesn't exist. Creating {}"
                     .format(cpu_info.get('model')))
        try:
            # get strings for value and units
            speed_value, speed_units = cpu_info.get('current_clock_speed')\
                .split()
            logger.debug('Found frequency {} with units {}.'
                         .format(speed_value, speed_units))
            # check if frequency unit already exists
            frequency_units = mongo_models.FrequencyUnits.query \
                .or_(mongo_models.FrequencyUnits.name == speed_units,
                     mongo_models.FrequencyUnits.abbreviation ==
                     speed_units).first()
            print 'Was there a frequency?: {}'.format(frequency_units)
            # if unit doesn't exist, create it
            if not frequency_units:
                logger.debug('Frequency unit not found. Creating unit {}.'
                             .format(speed_units))
                frequency_units = mongo_models\
                    .FrequencyUnits(name=speed_units,
                                    abbreviation=speed_units)
                frequency_units.save()
            else:
                logger.debug('Frequency unit {} already exists.'
                             .format(speed_units))
        except Exception as e:
            logger.error('Could not create FrequencyUnit object: {}'.format(e))
            raise e

        try:
            # create frequency document
            frequency = mongo_models.Frequency(value=int(speed_value),
                                               units_ref=frequency_units
                                               .to_ref())
            print frequency
            cpu = mongo_models.CpuModels(make_ref=manufacturer.to_ref(),
                                         name=cpu_info.get('model'),
                                         speed=frequency,
                                         cores=int(cpu_info.get('cores')))
            logger.debug('Added cpu model: {}'.format(cpu))
            # create caches
            for i in range(1, 4):
                print 'getting cache L{}'.format(i)
                capacity, unit_string = cpu_info.get('l{}_cache_size'
                                                     .format(i)).split()
                print 'found capacity {} {}'.format(capacity, unit_string)
                unit = mongo_models.ByteUnits.query \
                    .filter_by(name=unit_string).first()
                if not unit:
                    print 'No ByteUnits: {}'.format(unit_string)
                    unit = mongo_models.ByteUnits(name=unit_string)
                    unit.save()
                else:
                    print 'Found ByteUnits: {}'.format(unit)
                bytes = mongo_models.Bytes(value=int(capacity),
                                           units_ref=unit.to_ref())
                print 'bytes: {}'.format(bytes)
                cache = mongo_models.CpuCaches(level=i,
                                               capacity=bytes)
                print 'cache: {}'.format(cache)
                cpu.cache.append(cache)
            cpu.save()
            logger.debug('Added cache to cpu model: {}'.format(cpu.cache))
        except Exception as e:
            message = 'Could not add CPU model: {}: {}'\
                .format(type(e).__name__, e.args)
            logger.error(message)
            raise e

    return cpu


def edit_server_info(form, server_id):

    # get server object
    server = mongo_models.Servers.query.filter_by(id=server_id).first()
    if not server:
        return 'Could not find server {}.'.format(server_id)

    drac_info = mongo_models.ManagementCredentials()

    try:
        for field, data in form.data.items():
            if not data:
                if field in ('group', 'project'):
                    setattr(server, field + '_ref', None)
                else:
                    logger.debug('No data for field {}--skipping.'
                                 .format(field))
                continue
            elif field in ('user_name', 'password'):
                setattr(drac_info, field, data)
                continue
            # set basic fields
            elif field in dir(server):
                logger.debug('Setting string field {} to {}.'.format(field,
                                                                     data))
                setattr(server, field, data)
            # set object/ref fields
            elif field in dir(server):
                message = ''
                if not data:
                    message = 'Setting other field {} to None.'.format(field)
                    setattr(server, field, None)
                elif hasattr(data, 'id'):
                    message = 'Setting other field {} to {}.'.format(field,
                                                                     data.id)
                    setattr(server, field, data.id)
                else:
                    message = 'Could not determine data type for field {}.' \
                        .format(field, data)
                logger.debug(message)
        setattr(server, 'management', drac_info)
        server.save()
        return 'Successfully updated server {}'.format(server.id)
    except Exception as e:
        return 'Could not update server: {}'.format(e)


def delete_server(server_id, user):

    if not user.admin:
        return not_admin_message

    server = mongo_models.Servers.query.filter_by(id=server_id).first()
    if server:
        try:
            server.remove()
            return "Successfully deleted server."
        except Exception as e:
            return 'Error deleting server: {}'.format(e)
    return 'Could not delete server.'


def add_switch(form):

    try:
        new_switch = mongo_models.Switches(id=form.id.data,
                                           model_ref=form.model.data.to_ref(),
                                           group_ref=form.group.data.to_ref())
        if form.location.data:
            print 'adding location:', form.location.data
            new_switch.location_ref = form.location.data.to_ref()

        new_switch.save()
    except Exception as e:
        return "Error adding switch: {}".format(e)
    return "Successfully added switch."


def add_switch_model(form):

    try:
        new_switch = mongo_models.SwitchModels(make_ref=form.make.data
                                                .to_ref(),
                                                name=form.name.data)

        new_switch.save()
    except Exception as e:
        return "Error adding switch model: {}".format(e)
    return "Successfully added switch model."


def edit_switch_info(form, switch_id):

    # get switch object
    switch = mongo_models.Switches.query.filter_by(id=switch_id).first()
    if not switch:
        return 'Could not find switch {}.'.format(switch_id)

    try:
        for field, data in form.data.items():
            if not data:
                if field in ('group', 'project'):
                    setattr(switch, field + '_ref', None)
                else:
                    logger.debug('No data for field {}--skipping.'
                                 .format(field))
                continue
            elif field in ('user_name', 'password'):
                continue
            # set basic fields
            elif field in dir(switch):
                logger.debug('Setting string field {} to {}.'.format(field,
                                                                     data))
                setattr(switch, field, data)
            # set object/ref fields
            elif field in dir(switch):
                message = ''
                if not data:
                    message = 'Setting other field {} to None.'.format(field)
                    setattr(switch, field, None)
                elif hasattr(data, 'id'):
                    message = 'Setting other field {} to {}.'.format(field,
                                                                     data.id)
                    setattr(switch, field, data.id)
                else:
                    message = 'Could not determine data type for field {}.' \
                        .format(field, data)
                logger.debug(message)
        switch.save()
        return 'Successfully updated switch {}'.format(switch.id)
    except Exception as e:
        return 'Could not update switch: {}'.format(e)


# ============================ JOB METHODS ============================
def create_job(user, description=''):

    # create job
    now = datetime.utcnow()
    update_job = mongo_models.Jobs(user_ref=user.to_ref(),
                                   description=description,
                                   start_time=now,
                                   end_time=None,
                                   status_number=1)
    first_message = mongo_models.JobDetails(datetime=now,
                                            message='Job created')
    update_job.details.append(first_message)
    try:
        update_job.save()
    except Exception as e:
        logger.error('Could not create job: {}'.format(e))
        raise AutobenchException('Job creation failed')

    return update_job


def get_all_jobs(user=None):
    if not user or user.admin:
        jobs = mongo_models.Jobs.query \
            .descending(mongo_models.Jobs.start_time).all()
    else:
        group_members = set()
        for group in user.groups:
            group_members.update(group.members)
        group_member_refs = [g.to_ref() for g in group_members]

        jobs = mongo_models.Jobs.query.filter(mongo_models.Jobs.user_ref
                                              .in_(*group_member_refs)) \
            .descending(mongo_models.Jobs.start_time).all()
    return jobs


def delete_all_jobs(user):

    if not user.admin:
        return 'You are not admin, and should not be here!'

    try:
        mongo_alchemy.session.remove_query(mongo_models.Jobs).execute()
    except Exception as e:
        return 'Could not delete all jobs: {}'.format(e)

    return 'Successfully deleted all jobs.'


def get_job(id_):

    return mongo_models.Jobs.query.filter_by(mongo_id=id_).first()


def add_job_detail(job, message):

    detail = mongo_models.JobDetails(datetime=datetime.utcnow(),
                                     message=message)
    job.details.append(detail)
    try:
        job.save()
    except Exception as e:
        logger.error('Could not add detail to {}: {}'.format(job, e))


def pending_job(job):

    # set job as pending
    job.status = 'Pending'
    try:
        job.save()
    except Exception as e:
        logger.error('Could not set job to pending: {}'.format(e))


def fail_job(job, message=''):

    # set job as failed
    job.status = 'Failed'
    job.end_time = datetime.utcnow()
    add_job_detail(job, message)
    try:
        job.save()
    except Exception as e:
        logger.error('Could not fail job. Rolling back: {}'.format(e))


def finish_job(job):

    # set job as finished
    job.status = 'Completed'
    job.end_time = datetime.utcnow()
    try:
        job.save()
    except Exception as e:
        logger.error('Could not complete job: {}'.format(e))


# ========================== PROJECT METHODS ==========================
def get_all_projects(user):

    if user.admin:
        return mongo_models.Projects.query.all()
    user_group_ids = [g.mongo_id for g in user.groups]
    return mongo_models.Projects.query \
        .filter(mongo_models.Projects.group.in_(*user_group_ids)).all()


def get_project_by_id(id_):

    return mongo_models.Projects.query.filter_by(mongo_id=id_).first()


def add_project(form, user):

    status = mongo_models.ProjectStatusTypes.query\
        .filter_by(status='Created').first()
    new_project = mongo_models.Projects(owner_ref=user.to_ref(),
                                        status_ref=status.to_ref())
    for field, value in form.data.items():
        if field in dir(new_project):
            print "Setting {} to {}".format(field, value)
            setattr(new_project, field, value)
        else:
            logger.debug('Attr {} from form is not in project.'.format(field))

    try:
        response = new_project.save()
        print 'successfully added project {}: {}'.format(new_project.name,
                                                         response)
        return 'Successfully added project.'
    except Exception as e:
        message = 'Error adding project: {}'.format(e)
        logger.debug(message)
        return message


def delete_project(project_id, user):

    project = mongo_models.Projects.query \
        .filter_by(mongo_id=project_id).first()

    if not ((project.owner.mongo_id == user.mongo_id) or user.admin):
        return 'You are not the project owner!'

    try:
        project.remove()
        print 'User {} deleted project {}'.format(user, project_id)
    except Exception as e:
        message = 'Failed to delete project: {}'.format(e)
        logger.error(message)
        return message

    message = 'Successfully deleted project.'
    logger.debug(message)
    return message


def edit_project(project_id, user, form):

    # get project
    project = mongo_models.Projects.query.filter_by(mongo_id=project_id) \
        .first()

    # check that user has permission to edit project
    if not ((user == project.owner) or (user in project.members)):
        return 'You are not a member of this project!'
    print "User {} updating project {}.".format(user, project)

    try:
        for field, data in form.data.items():
            if field in dir(project) and (data is not None):
                print 'setting {} to {}'.format(field, data)
                setattr(project, field, data)
            else:
                print 'Project does not have attribute {}.'.format(field)

        project.save()
    except Exception as e:
        return 'Updating project failed: {}'.format(e)

    return 'Project successfully updated.'


def add_project_member(form, user, project):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'

    try:
        project.member_refs.append(form.member.data.to_ref())
        project.save()
    except Exception as e:
        message = 'Error adding member: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully added member!'


def remove_project_member(user, project, member):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'

    project.member_refs.remove(member.to_ref())

    try:
        project.save()
    except Exception as e:
        message = 'Error removing member from project: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully removed member!'


def add_project_status(form, user, project_id):

    project = mongo_models.Projects.query\
        .filter_by(mongo_id=project_id).first()

    if not ((user == project.owner) or (user in project.members) or
            user.admin):
        return 'You are not part of this project!'
    print 'adding update {} to project {}.'.format(form.message.data,
                                                   project)
    user_ref = DBRef('Users', ObjectId(user.mongo_id))
    status_update = mongo_models.ProjectUpdates(datetime=form.datetime.data,
                                                user_ref=user_ref,
                                                message=form.message.data)

    try:
        project.updates.append(status_update)
        project.save()
    except Exception as e:
        message = 'Error adding status: {}'.format(e)
        logger.error(message)
        return message

    message = 'Successfully added status update!'
    logger.debug(message)
    return message


def remove_project_status(user, project_id, status_id):

    project = mongo_models.Projects.query.filter_by(mongo_id=project_id)\
        .first()

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'
    print 'you are part of this project'

    print status_id
    try:
        print 'removing status {}'.format(status_id)
        for update in project.updates:
            if str(update.id_) == str(status_id):
                project.updates.remove(update)
                break
        else:
            return 'No status matching that id.'
        project.save()
    except Exception as e:
        message = 'Error removing status: {}'.format(e)
        logger.error(message)
        return message

    return 'Successfully removed status!'


def add_project_server(form, user, project):

    if not ((project.owner == user) or user.admin):
        return 'You are not the project owner!'
    server = mongo_models.Servers.query\
        .filter_by(mongo_id=form.server.data.mongo_id).first()
    if not server:
        return "No server selected."

    project_ref = DBRef('Projects', ObjectId(project.mongo_id))
    server.project_ref = project_ref

    try:
        server.save()
    except Exception as e:
        error = 'Error adding server: {}'.format(e)
        logger.error(error)
        return error

    return 'Successfully added server!'


# =========================== TEST METHODS ============================
def mongo_upsert_device_location(form):

    print "Adding device {} to location {}." \
        .format(form.device_ref.data, form.location.data)

    # create DBRef object
    d_ref = DBRef(collection='Servers', id=ObjectId(form.device_ref.data))

    # upsert entry
    response = mongo_models.DeviceLocations.query \
        .filter_by(device_ref=d_ref) \
        .find_and_modify() \
        .set(location=form.location.data, device_ref=d_ref) \
        .upsert() \
        .execute()

    # flash message
    flash("Updated location for {}".format(response.device))


def main():

    with myapp.app_context():
        mac = '00:50:56:81:7b:ee'
        print get_ip_from_mac(mac)

if __name__ == '__main__':
    logger = customlogger.create_logger(__name__)
    main()
else:
    logger = customlogger.get_logger(__name__)
