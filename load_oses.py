#!/usr/bin/python
from autobench import db as _db, models


def load_oses(db):
    oses = [{'flavor': 'CentOS',
             'version': '7 Latest',
             'kernel': 'centos/7/os/x86_64/images/pxeboot/vmlinuz',
             'initrd': 'centos/7/os/x86_64/images/pxeboot/initrd.img',
             'append': 'centos/7.0.1503/autobench-base.ks ramdisk_size=100000',
             'validated': True},
            {'flavor': 'CentOS',
             'version': '7.0.1503',
             'kernel': 'centos/7.0.1503/os/x86_64/images/pxeboot/vmlinuz',
             'initrd': 'centos/7.0.1503/os/x86_64/images/pxeboot/initrd.img',
             'append': 'centos/7.0.1503/minimal.ks ramdisk_size=100000'},
            {'flavor': 'CentOS',
             'version': '6 Latest',
             'kernel': 'centos/6/os/x86_64/images/pxeboot/vmlinuz',
             'initrd': 'centos/6/os/x86_64/images/pxeboot/initrd.img',
             'append': 'centos/6.7/minimal.ks ramdisk_size=100000'},
            {'flavor': 'CentOS',
             'version': '6.7',
             'kernel': 'centos/6.7/os/x86_64/images/pxeboot/vmlinuz',
             'initrd': 'centos/6.7/os/x86_64/images/pxeboot/initrd.img',
             'append': 'centos/6.7/minimal.ks ramdisk_size=100000'},
            {'flavor': 'CentOS',
             'version': '6.6',
             'kernel': 'centos/6.6/os/x86_64/images/pxeboot/vmlinuz',
             'initrd': 'centos/6.6/os/x86_64/images/pxeboot/initrd.img',
             'append': 'centos/6.6/minimal.ks ramdisk_size=100000'},
            {'flavor': 'openSUSE',
             'version': 'Tumbleweed',
             'kernel': '',
             'initrd': '',
             'append': ''},
            {'flavor': 'Windows',
             'version': 'Server 2012',
             'kernel': '',
             'initrd': '',
             'append': ''}]

    # delete all oses in database, if any
    all_oses = models.OS.query.all()
    for os in all_oses:
        db.session.delete(os)
    db.session.commit()

    # add all oses
    for os in oses:
        s = models.OS(**os)
        db.session.add(s)
    db.session.commit()

if __name__ == '__main__':
    load_oses(_db)
