#!/usr/bin/python

from autobench import db, models
from sqlalchemy.orm import subqueryload
from sqlalchemy import func


def get_all_server_info():
    servers = models.Servers.query\
        .options(subqueryload(models.DeviceAddress.ip_address)).all()
    for server in servers:
        print server


def test_relationships():

    servers = models.Servers.query.all()
    for server in servers:
        devs = server.network_devs.all()
        for dev in devs:
            print dev.mac


def delete_drives():

    server = models.Servers.query.filter_by(id='79RNR52').first()
    old_entries = models.ServerStorage.query\
        .filter_by(server_id=server.id).all()
    print old_entries
    for entry in old_entries:
        print entry


def get_drives():
    server = models.Servers.query.filter_by(id='HZKDR22').first()
    #for drive in server.unique_drives:
    #    print drive.model, drive.capacity
    #for drive in server.drives.order_by('slot'):
    #    print drive.slot, drive.id, drive.info.model, drive.info.capacity

    print type(server.drives)
    result = server.drives.order_by('slot').all()
    for drive in result:
        print drive.slot


def get_drive_counts():
    """
    my_query = db.session.query(models.ServerStorage, models.StorageDevices) \
        .filter(models.StorageDevices.id == models.ServerStorage.device_id).all()
    for query in my_query:
        print query[1].model, query[0].slot
    """

    result = db.engine.execute("select count(model), model "
                               "from server_storage as S "
                               "join storage_devices as D "
                               "where S.device_id=D.id "
                               "group by D.model;")
    for row in result:
        print row['count(model)'], row.model


def main():
    get_drives()


if __name__ == '__main__':
    main()
