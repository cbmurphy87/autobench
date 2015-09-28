from app import db


class Users(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(32), index=True, unique=False)
    last_name = db.Column(db.String(32), index=True, unique=False)
    email = db.Column(db.String(120), index=True, unique=True)
    password = db.Column(db.String(120), unique=False)
    authenticated = db.Column(db.Boolean, default=False)

    def is_authenticated(self):
        return self.authenticated

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)
        except NameError:
            return str(self.id)

    def __repr__(self):
        return '<User {}>'.format(self.email)


class Servers(db.Model):

    id = db.Column(db.String(16), primary_key=True)
    oob_mac = db.Column(db.String(12), unique=True)
    ib_mac = db.Column(db.String(12), unique=True)
    model = db.Column(db.String(16))
    cpu_count = db.Column(db.Integer)
    cpu_model = db.Column(db.String(16))
    memory_capacity = db.Column(db.Integer)
    rack = db.Column(db.Integer)
    u = db.Column(db.Integer)
    available = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<Server id {}>'.format(self.id)


class StorageDevices(db.Model):

    model = db.Column(db.String(16), primary_key=True)
    capacity = db.Column(db.Integer)
    standard = db.Column(db.String(8))


class CommunicationDevices(db.Model):

    model = db.Column(db.String(16), primary_key=True)
    type = db.Column(db.String(16))
    protocol = db.Column(db.String(16))
    speed = db.Column(db.String(16))
    port_count = db.Column(db.Integer)


class ServerStorage(db.Model):

    id = db.Column(db.String(64), primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'))
    device_model = db.Column(db.String(16),
                             db.ForeignKey('storage_devices.model'))
    slot = db.Column(db.Integer)


class ServerCommunication(db.Model):

    id = db.Column(db.String(64), primary_key=True)
    server = db.Column(db.Integer)
    model = db.Column(db.String(16),
                      db.ForeignKey('communication_devices.model'))
    slot = db.Column(db.Integer)


class AddressAssignments(db.Model):

    mac = db.Column(db.String(12),
                    db.ForeignKey('servers.oob_mac'),
                    db.ForeignKey('servers.ib_mac'),
                    primary_key=True)
    ip_address = db.Column(db.String(15))
