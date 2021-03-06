from autobench import db
import datetime
from datetime import datetime
import enum
from sqlalchemy.dialects.mysql import DATE, DATETIME, TINYINT
from sqlalchemy.orm import backref
import re
from werkzeug.security import check_password_hash


# ======================= Users for Flask Login =======================


class Users(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(32))
    last_name = db.Column(db.String(32))
    user_name = db.Column(db.String(32), index=True,
                          unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True,
                      nullable=False)
    password = db.Column(db.String(120))
    authenticated = db.Column(db.Integer, default=False)
    admin = db.Column(db.Integer, default=False)

    # relationships
    jobs = db.relationship('Jobs', backref='creator', lazy='dynamic',
                           cascade='all, delete')
    groups = db.relationship('Groups', secondary='user_group',
                             backref='members', lazy='dynamic')

    # methods
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

    def full_name(self):

        return str(self)

    def __repr__(self):
        return '<User {}>'.format(self.email)

    def __str__(self):
        return '{} {}'.format(self.first_name, self.last_name)


# ========================= Physical Location =========================
class RoomTypes(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.String(32))

    # relationships
    rooms = db.relationship('Rooms', backref='type')

    def __str__(self):
        return str(self.type)

    def __repr__(self):
        return "<RoomType '{}'>".format(self.type)


class Rooms(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(32), unique=True)
    type_id = db.Column(db.Integer, db.ForeignKey('room_types.id'))
    description = db.Column(db.String(128))

    # relationships
    racks = db.relationship('Racks', backref=db.backref('room', uselist=False),
                            order_by='Racks.number')

    # magic methods
    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return "<Room '{}'>".format(self.name)


class Racks(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    number = db.Column(db.Integer)
    min_u = db.Column(db.Integer)
    max_u = db.Column(db.Integer)

    # constraints
    __table_args__ = (
        db.UniqueConstraint('room_id', 'number'),
    )

    # relationships
    units = db.relationship('RackUnits',
                            backref=backref('rack', uselist=False),
                            order_by='RackUnits.number')

    # magic methods
    def __str__(self):
        return 'Rack {}'.format(self.number)

    def __repr__(self):
        return "<Rack '{}' in {}>".format(self.number, repr(self.room))


class RackUnits(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rack_id = db.Column(db.Integer, db.ForeignKey('racks.id'))
    number = db.Column(db.Integer, primary_key=True)

    # constraints
    __table_args__ = (
        db.UniqueConstraint('rack_id', 'number'),
    )

    # magic methods
    def __str__(self):
        return str(self.number)

    def __repr__(self):
        return "<RackUnit '{}' in {}>".format(self.number,
                                              repr(self.rack))


class Cabinets(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    number = db.Column(db.Integer)

    # constraints
    __table_args__ = (
        db.UniqueConstraint('room_id', 'number'),
    )

    # relationships
    room = db.relationship('Rooms', backref='cabinets',
                           uselist=False)

    # magic methods
    def __str__(self):
        return 'Cabinet {}'.format(self.number)

    def __repr__(self):
        return "<Cabinet '{}' in {}>".format(self.number, repr(self.room))


class ChassisModels(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    make = db.Column(db.String(64))
    model = db.Column(db.String(64))
    height = db.Column(db.Integer)
    min_slot = db.Column(db.Integer)
    max_slot = db.Column(db.Integer)


class Chassis(db.Model):

    # parameters
    id = db.Column(db.String(64), primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('chassis_models.id'))


# ============================= Inventory =============================
class CpuModels(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    make = db.Column(db.String(16))
    model = db.Column(db.String(16))
    speed = db.Column(db.Integer)
    cores = db.Column(db.Integer)

    # constraints
    __table_args__ = (
        db.UniqueConstraint('make', 'model'),
    )


class ServerCpus(db.Model):

    # parameters
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'),
                          primary_key=True)
    cpu_id = db.Column(db.Integer, db.ForeignKey('cpu_models.id'),
                       primary_key=True)
    count = db.Column(db.Integer)


class ServerModels(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    make = db.Column(db.String(16))
    model = db.Column(db.String(16))
    height = db.Column(db.Integer)
    sockets = db.Column(db.Integer)
    modular = db.Column(TINYINT, default=False)


class Servers(db.Model):

    # parameters
    id = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.String(16))
    host_name = db.Column(db.String(16))
    model_id = db.Column(db.Integer, db.ForeignKey('server_models.id',
                                                   onupdate='CASCADE',
                                                   ondelete='SET NULL'))
    memory_capacity = db.Column(db.Integer)
    bios = db.Column(db.String(16))
    dirty = db.Column(db.SmallInteger)
    user_name = db.Column(db.String(64))
    password = db.Column(db.String(64))
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'),
                           nullable=True)

    # relationships
    cpus = db.relationship('ServerCpus',
                           backref='server', lazy='dynamic',
                           cascade='all, delete, delete-orphan')
    interfaces = db.relationship('NetworkDevices', cascade='all, delete',
                                 backref='server', lazy='dynamic',
                                 order_by='NetworkDevices.slot')
    unique_drives = db.relationship('StorageDevices',
                                    secondary="server_storage")
    drives = db.relationship('ServerStorage', lazy='dynamic',
                             backref='servers',
                             cascade='all, delete, delete-orphan',
                             order_by='ServerStorage.slot')
    virtual_drives = db.relationship('VirtualStorageDevices', backref='server',
                                     lazy='dynamic', cascade='all, delete')
    group = db.relationship('Groups', backref='servers')
    project = db.relationship('Projects', backref='servers')

    attributes = db.relationship('ServerModels', backref='servers')

    # magic methods
    def __repr__(self):
        return '<Server id {}>'.format(self.id)

    def get_name(self):
        return '{}'.format(self.name or self.host_name or self.id)


class Switches(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('switch_model.id'))


class SwitchModel(db.Model):

    # parameters
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    make = db.Column(db.String(64))
    model = db.Column(db.String(64))
    speed = db.Column(db.Integer)
    ports = db.Column(db.Integer)
    height = db.Column(db.Integer)


class StorageDevices(db.Model):

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    manufacturer = db.Column(db.String(16))
    model = db.Column(db.String(32))
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
                                                     self.number)


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
        return '<ServerStorage {}>'.format(self.serial_number
                                           if self.serial_number
                                           else 'id {}'.format(self.id))


class ServerCommunication(db.Model):

    id = db.Column(db.Integer, db.ForeignKey('communication_devices.id'),
                   primary_key=True)
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'))
    type = db.Column(db.String(16),
                     db.CheckConstraint('type="network" '
                                        'or type="storage"'))
    slot = db.Column(db.Integer)


class NetworkDevices(db.Model):

    mac = db.Column(db.String(17), primary_key=True)
    server_id = db.Column(db.String(16), db.ForeignKey('servers.id'))
    ip = db.Column(db.String(15), unique=True, nullable=True)
    name = db.Column(db.String(6))
    slot = db.Column(db.String(24))
    type = db.Column(db.String(3),
                     db.CheckConstraint('type="ib" or type="oob"'))

    def __repr__(self):
        return '<NetworkDevice mac {}>'.format(self.mac)


# =========================== Group Models ============================
class Groups(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True,
                   nullable=True)
    group_name = db.Column(db.String(16), unique=True)
    description = db.Column(db.String(128))

    def __str__(self):

        return str(self.group_name)

    def member_count(self):

        return str(len(self.members))


class UserGroup(db.Model):

    uid = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    gid = db.Column(db.Integer, db.ForeignKey('groups.id'), primary_key=True)


class ServerGroup(db.Model):

    sid = db.Column(db.String(16), db.ForeignKey('servers.id'),
                    primary_key=True)
    gid = db.Column(db.Integer, db.ForeignKey('groups.id'), primary_key=True)


# ============================= OS Models =============================
class OS(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    flavor = db.Column(db.String(16))
    version = db.Column(db.String(16))
    kernel = db.Column(db.String(128))
    initrd = db.Column(db.String(128))
    append = db.Column(db.String(128))
    validated = db.Column(db.Integer, default=False)

    def __repr__(self):

        return '<OS: {} {}>'.format(self.flavor, self.version)


# ============================= Projects ==============================
class Projects(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    gid = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    name = db.Column(db.String(32), unique=True)
    start_date = db.Column(db.DATE)
    target_end_date = db.Column(db.DATE)
    actual_end_date = db.Column(db.DATE, default=None)
    description = db.Column(db.Text())
    status = db.Column(db.Enum("Planned", "Cancelled", "On Hold", "Blocked",
                               "In Progress", "Completed"))

    owner = db.relationship('Users', backref='projects_owned')
    primary_group = db.relationship('Groups', backref='projects')
    members = db.relationship('Users', secondary='project_members',
                              backref='member_of_projects', lazy='dynamic')
    statuses = db.relationship('ProjectStatus', backref='project',
                               cascade='all, delete, delete-orphan',
                               order_by='desc(ProjectStatus.datetime)')
    archived = db.Column(db.Integer, default=False)

    def __repr__(self):
        return '<Projects {}>'.format(self.id)

    def __str__(self):
        return str(self.name)


class ProjectStatus(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pid = db.Column(db.Integer, db.ForeignKey('projects.id'))
    date = db.Column(db.DATE)
    datetime = db.Column(db.DATETIME)
    engineer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    message = db.Column(db.String(128))

    # relationships
    engineer = db.relationship('Users', backref='statuses')


class ProjectMembers(db.Model):

    pid = db.Column(db.Integer, db.ForeignKey('projects.id'), primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)


# =============================== Jobs ================================
class Jobs(db.Model):

    """
    Job status:
        0: unknown
        1: started
        2: pending
        3: finished
        4: failed
    """

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    start_time = db.Column(db.String(32))
    end_time = db.Column(db.String(32))
    status = db.Column(db.Integer, default=0)

    details = db.relationship('JobDetails', backref='job', lazy='dynamic',
                              cascade='all, delete, delete-orphan',
                              order_by=lambda: JobDetails.id.desc())

    def __repr__(self):
        return '<Jobs id {}>'.format(self.id)

    def __str__(self):
        return "JID {}".format(self.id)

    def get_status(self):
        mapping = {0: 'Unknown',
                   1: 'Started',
                   2: 'Pending',
                   3: 'Completed',
                   4: 'Failed'}

        return mapping[self.status]


class JobDetails(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'))
    time = db.Column(db.String(32))
    message = db.Column(db.Text)
