#!/usr/bin/python
import os
import unittest
import tempfile

from coverage import coverage
cov = coverage(branch=True, omit=['/opt/*',
                                  '/usr/*',
                                  'unit_tests.py',
                                  '*__init__.py'])
cov.start()

from config import basedir
from app import myapp, db
from app.models import Servers, Users, OS
from app.scripts.db_actions import get_inventory, get_ip_from_mac, \
    get_mac_from_ip
from werkzeug.security import generate_password_hash

db.session.remove()


class TestCase(unittest.TestCase):

    def setUp(self):
        db.session.remove()
        self.db_fd, myapp.config['DATABASE'] = tempfile.mkstemp()
        myapp.config['TESTING'] = True
        myapp.config['WTF_CSRF_ENABLED'] = False
        myapp.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
                                                  os.path.join(basedir,
                                                               'test.db')
        self.app = myapp.test_client()
        db.create_all()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(myapp.config['DATABASE'])
        db.drop_all()
        db.session.remove()

    def test_get_inventory(self):

        inventory = Servers.query.all()
        assert type(inventory) is list, type(inventory)
        inventory = [x for x in inventory]
        assert len(inventory) == 0, len(inventory)

    def test_get_inventory_method(self):
        inventory = get_inventory()
        assert type(inventory) == list, type(inventory)
        assert len(inventory) == 0, len(inventory)

        new_server = Servers(id='TESTID', host_name='testhostname',
                             model='test model', cpu_count='5',
                             cpu_model='test cpu', memory_capacity='999 TB',
                             bios='1.2.3.4', rack='12', u='13')
        try:
            db.session.add(new_server)
            db.session.commit()
        except:
            db.session.rollback()
            assert False, 'Could not add server to db.'

        inventory = get_inventory()
        assert type(inventory) == list, type(inventory)
        assert len(inventory) == 1, len(inventory)

    def test_users(self):

        users = Users.query.all()
        assert type(users) == list
        assert len(users) == 0
        password = generate_password_hash('testpassword')
        new_user = Users(first_name='test',
                         last_name='user',
                         email='testuser@aaebench.micron.com',
                         password=password,
                         admin=False)
        try:
            db.session.add(new_user)
            db.session.commit()
        except:
            db.session.rollback()
            assert False, 'Could not add user to db.'

        users = Users.query.order_by('email')
        all_users = users.all()
        assert type(all_users) == list
        assert len(all_users) == 1

        test_user = users.first()
        assert int(test_user.get_id()) == 1, test_user.get_id()
        assert repr(test_user) == '<User testuser@aaebench.micron.com>', \
            repr(test_user)
        assert str(test_user) == 'test user', \
            str(test_user)
        assert test_user.check_password('testpassword'), \
            'password check failed: {}'.format(test_user.password)
        assert not test_user.check_password('wrongpassword'), \
            'wrong password check failed'

    def test_get_oses(self):

        oses = OS.query.all()
        assert type(oses) == list
        assert len(oses) == 0, len(oses)
        nos = {'flavor': 'CentOS',
               'version': '7 Latest',
               'kernel': 'centos/7/os/x86_64/images/pxeboot/vmlinuz',
               'initrd': 'centos/7/os/x86_64/images/pxeboot/initrd.img',
               'append': 'centos/7.0.1503/minimal.ks ramdisk_size=100000',
               'validated': True}
        new_os = OS(**nos)
        try:
            db.session.add(new_os)
            db.session.commit()
        except:
            db.session.rollback()

        validated_oses = OS.query.filter_by(validated=True).all()
        assert type(validated_oses) == list, type(validated_oses)
        assert len(validated_oses) == 1, len(validated_oses)

    def test_add_server(self):

        servers = Servers.query
        all_servers = servers.all()
        assert type(all_servers) == list, type(all_servers)
        assert len(all_servers) == 0, len(all_servers)

        new_server = Servers(id='TESTID', host_name='testhostname',
                             model='test model', cpu_count='5',
                             cpu_model='test cpu', memory_capacity='999 TB',
                             bios='1.2.3.4', rack='12', u='13')
        try:
            db.session.add(new_server)
            db.session.commit()
        except:
            db.session.rollback()
            assert False, 'Could not add server to db.'

        servers = Servers.query
        all_servers = servers.all()
        first_server = servers.first()
        assert type(all_servers) == list, type(all_servers)
        assert len(all_servers) == 1, len(all_servers)
        assert str(first_server) == '<Server id TESTID>'

    def test_ipmac(self):

        ip = '172.16.7.156'
        mac = '0c:c4:7a:66:ac:87'

        assert get_mac_from_ip(ip).lower() == mac.lower(), "mac doesn't match"
        assert get_ip_from_mac(mac).lower() == ip.lower(), "ip doesn't match"


if __name__ == '__main__':
    db.session.remove()
    try:
        unittest.main()
    except:
        pass
    cov.stop()
    cov.save()
    print("\n\nCoverage Report:\n")
    cov.report()
    print("HTML version: " + os.path.join(basedir, "tmp/coverage/index.html"))
    pth = 'tmp/coverage'
    for _file in os.listdir(pth):
        os.remove(os.path.join(pth, _file))
    cov.html_report(directory=pth)
    cov.erase()
    db.session.remove()
