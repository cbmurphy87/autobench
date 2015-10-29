from app import db
from werkzeug.security import check_password_hash

# ================ Users for Flask Login ==================


class Users(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(32), index=True)
    last_name = db.Column(db.String(32), index=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password = db.Column(db.String(120))
    authenticated = db.Column(db.Boolean, default=False)
    admin = db.Column(db.Boolean, default=False)

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

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return '<User {}>'.format(self.email)

    def __str__(self):
        return '{} {}'.format(self.first_name, self.last_name)


# ================= Server Inventory ======================


class Servers(db.Model):

    # parameters
    id = db.Column(db.String(16), primary_key=True)
    host_name = db.Column(db.String(16))
    model = db.Column(db.String(16))
    cpu_count = db.Column(db.Integer)
    cpu_model = db.Column(db.String(16))
    memory_capacity = db.Column(db.String(16))
    bios = db.Column(db.String(16))
    rack = db.Column(db.Integer, default='?')
    u = db.Column(db.Integer, default='?')
    available = db.Column(db.Boolean, default=False)
    held_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # relationships
    interfaces = db.relationship('NetworkDevices',
                                 backref='servers', lazy='dynamic')
    unique_drives = db.relationship('StorageDevices',
                                    secondary="server_storage")
    drives = db.relationship('ServerStorage',
                             backref='servers', lazy='dynamic')
    virtual_drives = db.relationship('VirtualStorageDevices',
                                     backref='servers', lazy='dynamic')
    holder = db.relationship('Users', backref='servers')

    # magic methods
    def __repr__(self):
        return '<Server id {}>'.format(self.id)


class StorageDevices(db.Model):

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    manufacturer = db.Column(db.String(16))
    model = db.Column(db.String(16))
    capacity = db.Column(db.Integer)
    standard = db.Column(db.String(8))
    type = db.Column(db.String(8))

    def __repr__(self):
        return '<StorageDevice id {}>'.format(self.id)


class VirtualStorageDevices(db.Model):

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    name = db.Column(db.String(16))
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'))
    number = db.Column(db.Integer)
    capacity = db.Column(db.Integer)
    raid = db.Column(db.String(16))

    def __repr__(self):
        return '<VirtualStorageDevice {}.{}>'.format(self.server_id,
                                                     self.name)


class CommunicationDevices(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(16), unique=True)
    type = db.Column(db.String(16))
    protocol = db.Column(db.String(16))
    speed = db.Column(db.String(16))
    port_count = db.Column(db.Integer)


class ServerStorage(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(64), unique=True)
    device_id = db.Column(db.Integer, db.ForeignKey('storage_devices.id'))
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'))
    slot = db.Column(db.Integer)
    info = db.relationship('StorageDevices')

    def __repr__(self):
        return '<ServerStorage id {}>'.format(self.id)


class ServerCommunication(db.Model):

    id = db.Column(db.String(64), db.ForeignKey('communication_devices.id'),
                   primary_key=True)
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'))
    type = db.Column(db.String(16),
                     db.CheckConstraint('type="network" '
                                        'or type="storage"'))
    slot = db.Column(db.Integer)


class NetworkDevices(db.Model):

    mac = db.Column(db.String(12), primary_key=True)
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'))
    ip = db.Column(db.String(15), unique=True, nullable=True)
    name = db.Column(db.String(3))
    slot = db.Column(db.Integer)
    type = db.Column(db.String(3),
                     db.CheckConstraint('type="ib" or type="oob"'))


# =========================== OS Models ==========================
class OS(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    flavor = db.Column(db.String(16))
    version = db.Column(db.String(16))
    kernel = db.Column(db.String(128))
    initrd = db.Column(db.String(128))
    append = db.Column(db.String(128))
    validated = db.Column(db.Boolean, default=False)

    def __repr__(self):

        return '<OS: {} {}>'.format(self.flavor, self.version)


# =========================== Projects ==========================
class Projects(db.Model):

    id = db.Column(db.String('16'), primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date_created = db.String('32')
