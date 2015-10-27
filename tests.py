#!/usr/bin/python
import os
import unittest

from coverage import coverage
cov = coverage(branch=True, omit=['/opt/*',
                                  '/usr/*',
                                  'tests.py',
                                  '*__init__.py'])
cov.start()

from config import basedir
from app import app, db
from app.models import Servers, Users, OS
from app.scripts.jenkinsMethods import make_job
from app.forms import CreateJobForm

db.session.remove()


class TestCase(unittest.TestCase):

    def setUp(self):
        db.session.remove()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
                                                os.path.join(basedir, 'test.db')
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_inventory(self):

        inventory = Servers.query.all()
        assert type(inventory) is list, type(inventory)
        inventory = [x for x in inventory]
        assert len(inventory) == 0, len(inventory)

    def test_get_users(self):

        users = Users.query.order_by('email').all()
        assert type(users) == list
        assert len(users) == 0

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

    def test_make_job(self):
        job_name = 'test_job_coverage'
        form = CreateJobForm()
        form.job_name.data = job_name
        form.build.data = False
        form.target.data = 'notarget'
        form.command = 'nocommand'
        make_job(form)


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
