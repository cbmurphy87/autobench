from autobench import mongo_alchemy as ma
from autobench.mongo_addons import DateField, SparseIndex
# noinspection PyUnresolvedReferences
from bson import DBRef, ObjectId
from mongoalchemy.document import Index
from mongoalchemy.fields import computed_field, PrimitiveField
from mongoalchemy.exceptions import BadValueException
from math import pow
import re
import sys
from werkzeug.security import check_password_hash


# ______________________________ SCALES _______________________________
# Metric scale based on meter
# noinspection SpellCheckingInspection
metric_scale = {
    'scale': {
        'atto': pow(10, -18),
        'femto': pow(10, -15),
        'pico': pow(10, -12),
        'nano': pow(10, -9),
        'micro': pow(10, -6),
        'milli': pow(10, -3),
        'centi': pow(10, -2),
        'deci': pow(10, -1),
        '': pow(10, 0),
        'deca': pow(10, 1),
        'hecto': pow(10, 2),
        'kilo': pow(10, 3),
        'mega': pow(10, 6),
        'giga': pow(10, 9),
        'tera': pow(10, 12),
        'peta': pow(10, 15),
        'exa': pow(10, 18)
    },
    'bases': {
        'mass': 'gram',
        'length': 'meter',
        'power': 'watt',
        'energy': 'joule',
        'force': 'newton',
        'frequency': 'hertz',
        'torque': {'numerator': 'force',
                   'denominator': 'length'}
    },
    'abbreviations': {
            'frequency': ['hz']
        }
}

# Imperial scale based on feet
imperial_scale = {
    'inch': 1.0 / 12.0,
    'feet': 1.0,
    'yard': 3.0,
    'mile': 5280.0
}


# _____________________________ VALIDATORS ____________________________
def _validate_location(loc_ref):
    return type(loc_ref) and \
           loc_ref.collection in ('Rooms', 'Racks', 'RackUnits', 'Chassis')


# ______________________________ MODELS _______________________________
# ---------------------------- Backend Models -------------------------
class UnitsSystems(ma.Document):

    name = ma.EnumField(ma.StringField(), 'Metric', 'Imperial')


# ______________________________ UNITS ________________________________
class LengthUnits(ma.Document):

    def _validate_unit(value):
        if value.endswith('meter'):
            if self.unit.rstrip('meter') in \
                    (metric_scale['scale'].keys() + ['']):
                return True
        elif value.lower() in imperial_scale.keys():
            return True
        return False

    # unit should not end with 's'
    system_ref = ma.RefField('UnitsSystems')
    system = system_ref.rel()
    unit = ma.StringField(validator=_validate_unit)
    abbreviation = ma.StringField()

    # meters are the base unit to work off of
    def convert_to_meters(self, value):
        if 'inch' in self.unit.lower():
            return value * 0.0254
        elif self.unit.lower().endswith('meter'):
            current_scale = self.unit.lower().rstrip('meter')
            return value * current_scale


class ByteUnits(ma.Document):

    mapping = {
        'kilo': pow(1024, 1),
        'mega': pow(1024, 2),
        'giga': pow(1024, 3),
        'tera': pow(1024, 4),
        'peta': pow(1024, 5),
        'exa': pow(1024, 5),
        'zeta': pow(1024, 6)
    }

    #def _validate_unit(value):
    #    # match prefixes, or first letter of prefix
    #    match = re.match(r'(?is)'
    #                     r'(?:{})|'
    #                     r'(?:[{}](?=b))'
    #                     .format('|'.join(mapping.keys()),
    #                             ''.join([c[0].lower()
    #                                      for c in mapping.keys()])),
    #                     value)
    #    if match:
    #        prefix = match.group()
    #        if prefix:
    #            return True
    #    raise BadValueException

    name = ma.StringField()

    @property
    def abbreviation(self):
        return '{}B'.format(self.name[0].upper())

    # indexes
    unit_index = Index().ascending('name').unique()

    # magic methods
    def __str__(self):
        return '{}'.format(self.abbreviation)


class Bytes(ma.Document):

    # parameters
    value = ma.IntField()
    units_ref = ma.RefField('ByteUnits')
    units = units_ref.rel()

    # magic methods
    def __str__(self):
        return '{} {}'.format(self.value, self.units)


class FrequencyUnits(ma.Document):

    # parameters
    system_ref = ma.RefField('UnitsSystems', required=False, allow_none=True,
                             ignore_missing=True)
    system = system_ref.rel(allow_none=True)
    name = ma.StringField()
    abbreviation = ma.StringField(required=False, allow_none=True,
                                  ignore_missing=True)

    # indexes
    unit_index = Index().ascending('name').unique()

    # magic methods
    def __str__(self):
        return '{}'.format(self.abbreviation or self.name)


class Frequency(ma.Document):

    # parameters
    value = ma.IntField()
    units_ref = ma.RefField('FrequencyUnits')
    units = units_ref.rel()

    # magic methods
    def __str__(self):
        return '{} {}'.format(self.value, self.units)


# -------------------------- User/Group Models ------------------------
class Users(ma.Document):

    first_name = ma.StringField()
    last_name = ma.StringField()
    user_name = ma.StringField()
    email = ma.StringField()
    password = ma.StringField()
    authenticated = ma.BoolField(default=True)
    admin = ma.BoolField(default=False)

    # link to info page
    @property
    def link(self):
        return "/admin/users/{}".format(self.mongo_id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.user_name)

    # relationships
    @property
    def groups(self):
        return Groups.query.filter({'member_refs': self.to_ref()}).all()

    @property
    def rendered_groups(self):
        return ','.join([g.render for g in self.groups])

    @property
    def projects_owned(self):
        return Projects.query.filter({'owner_ref': self.to_ref()}).all()

    @property
    def member_of_projects(self):
        return Projects.query.filter({'member_refs': self.to_ref()}).all()

    # helper methods
    def is_authenticated(self):
        return self.authenticated

    # noinspection PyMethodMayBeStatic
    def is_active(self):
        return True

    # noinspection PyMethodMayBeStatic
    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.mongo_id)
        except NameError:
            return str(self.mongo_id)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def full_name(self):

        return "{} {}".format(self.first_name, self.last_name)

    # magic methods

    def __repr__(self):
        return '<User {}>'.format(self.email)

    def __str__(self):
        return '{} {}'.format(self.first_name, self.last_name)

    # indexes
    user_name_index = Index().ascending('user_name').unique()
    email_index = Index().ascending('email').unique()


class Groups(ma.Document):

    name = ma.StringField(required=True)
    description = ma.StringField()
    member_refs = ma.ListField(ma.RefField('Users'), required=False,
                               allow_none=True, ignore_missing=True,
                               default_empty=True)
    members = member_refs.rel(ignore_missing=True)

    # link to info page
    @property
    def link(self):
        return "/groups/{}".format(self.mongo_id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.name)

    # relationships
    @property
    def servers(self):
        group_ref = DBRef('Groups', ObjectId(self.mongo_id))
        return Servers.query.filter(Servers.group_ref == group_ref).all()

    # magic methods
    def __repr__(self):
        return "<Groups {}>".format(self.name)

    def __str__(self):
        return str(self.name)

    # indexes
    name_index = Index().ascending('name').unique()


class Manufacturers(ma.Document):

    name = ma.StringField()
    logo = ma.StringField(required=False, allow_none=True, ignore_missing=True)

    def __str__(self):
        return "{}".format(self.name)

    # indexes
    name_index = Index().ascending('name').unique()


class RoomTypes(ma.Document):

    # parameters
    type = ma.StringField()

    # magic methods
    def __str__(self):
        return str(self.type)

    def __repr__(self):
        return "<RoomType '{}'>".format(self.type)

    # indexes
    type_index = Index().ascending('type').unique()


class Rooms(ma.Document):

    # parameters
    name = ma.StringField()
    type_ref = ma.RefField('RoomTypes')
    type = type_ref.rel()
    description = ma.StringField()

    # link to info page
    @property
    def link(self):
        return "/rooms/{}".format(self.mongo_id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.name)

    # magic methods
    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return "<Room '{}'>".format(self.name)

    # indexes
    name_index = Index().ascending('name').unique()


class RackDimensionDocuments(ma.Document):

    units_ref = ma.RefField('LengthUnits')
    units = units_ref.rel()
    display_units_ref = ma.RefField('LengthUnits')
    display_units = display_units_ref.rel()
    width = ma.FloatField()
    height = ma.FloatField()
    depth = ma.FloatField()

    # magic methods
    def __str__(self):
        return '{1}{0} x {2}{0} x {3}{0}' \
            .format(self.display_units.abbreviation,
                    self.width, self.height, self.depth)


class RackModels(ma.Document):

    make_ref = ma.RefField('Manufacturers', required=True)
    make = make_ref.rel()
    name = ma.StringField()
    dimensions = ma.DocumentField('RackDimensionDocuments')
    number_of_units = ma.IntField(min_value=1)

    # link to info page
    @property
    def link(self):
        return "/admin/racks/models/{}".format(self.mongo_id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.name)

    # magic methods
    def __repr__(self):
        return "<RackModels {} {}>".format(self.make, self.name)

    def __str__(self):
        return "{}".format(self.name)


class RackUnits(ma.Document):

    number = ma.IntField(required=True)

    # magic methods
    def __str__(self):
        return str(self.number)

    def __repr__(self):
        return "<RackUnit '{}'>".format(self.number)


class Racks(ma.Document):

    model_ref = ma.RefField('RackModels', required=True)
    model = model_ref.rel()
    serial_number = ma.StringField(required=False, allow_none=True)
    location_ref = ma.RefField('Rooms')
    location = location_ref.rel()
    number = ma.IntField(min_value=0)
    name = ma.StringField(required=False)
    notes = ma.StringField(required=False)
    units = ma.ListField(ma.DocumentField('RackUnits'), default_empty=True)

    # link to info page
    @property
    def link(self):
        return "/racks/{}".format(self.mongo_id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.name)

    # magic methods
    def __str__(self):
        return 'Rack {}'.format(self.number)

    def __repr__(self):
        return "<Rack '{}'>".format(self.number)


class CpuCaches(ma.Document):

    # parameters
    level = ma.IntField()
    capacity = ma.DocumentField('Bytes')


class CpuModels(ma.Document):

    # parameters
    make_ref = ma.RefField('Manufacturers')
    make = make_ref.rel()
    name = ma.StringField()
    speed = ma.DocumentField('Frequency')
    cores = ma.IntField()
    cache = ma.ListField(ma.DocumentField('CpuCaches'), required=False,
                         default_empty=True)

    # magic methods
    def __str__(self):
        return '{}'.format(self.name)


# noinspection SpellCheckingInspection
class Cpus(ma.Document):

    # parameters
    socket_number = ma.IntField()
    model_ref = ma.RefField('CpuModels')
    model = model_ref.rel()

    def __str__(self):
        return '{}'.format(self.model)


class DriveTypes(ma.Document):

    # form factor: 1.8", 2.5", 3.5"
    form_factor = ma.StringField()
    # protocol: ATA, SATA, SAS, NVMe
    protocol = ma.StringField()
    # media: NAND, spinning, 3DXpoint/SCM, PCM
    media = ma.StringField()
    # speed (optional): 7.2k, 10k, 15k
    speed = ma.StringField()
    # capacity: in GB
    capacity = ma.IntField(required=True)

    # magic methods
    def __repr__(self):
        return "<DriveType {} {} {}>".format(self.capacity,
                                             self.protocol,
                                             self.media)

    def __str__(self):
        return "{} {}".format(self.make, self.model)


class DriveModels(ma.Document):

    # parameters
    make_ref = ma.RefField(Manufacturers)
    make = make_ref.rel()
    type_ref = ma.RefField('DriveTypes')
    type = type_ref.rel()
    model = ma.StringField()

    # indexes
    model_index = Index().ascending('model').unique()

    # magic methods
    def __repr__(self):
        return "<DriveModel {} {}>".format(self.make, self.model)

    def __str__(self):
        return "{} {}".format(self.make, self.model)


class Drives(ma.Document):

    serial_number = ma.StringField(required=False, ignore_missing=True)
    model_ref = ma.RefField('DriveModels')
    model = model_ref.rel()
    group_ref = ma.RefField('Groups', required=False, allow_none=True,
                            ignore_missing=True)
    group = group_ref.rel()

    # properties
    @property
    def server(self):
        return Servers.query.filter()

    # indexes
    serial_number_index = SparseIndex().ascending('serial_number').unique()


class VirtualDrives(ma.Document):

    # parameters
    name = ma.StringField()
    number = ma.IntField()
    capacity = ma.IntField()
    raid = ma.StringField()

    # magic methods
    def __repr__(self):
        return "<VirtualDrives {}>".format(self.name)

    def __str__(self):
        return str(self.name)


class NetworkInterfaceModels(ma.Document):

    make = ma.RefField('Manufacturers')
    name = ma.StringField()
    port_count = ma.IntField(required=False, ignore_missing=True)
    speed = ma.IntField()  # change to BitRate


class NetworkInterfaces(ma.Document):

    def _validate_type(type_):
        if type_ not in ('oob', 'ib'):
            raise BadValueException('Wrong interface type.')

    def _validate_mac(value):
        if value != value.replace(':', '').lower():
            raise BadValueException('MAC Address must be in all lower case,'
                                    'and with no special characters')

    # parameters
    serial_number = ma.StringField(required=False, allow_none=True)
    model_ref = ma.RefField('NetworkInterfaceModels', required=False,
                            allow_none=True, ignore_missing=True)
    model = model_ref.rel(allow_none=True)
    mac = ma.StringField(validator=_validate_mac)
    ip = ma.StringField(required=False, allow_none=True, ignore_missing=True)
    name = ma.StringField()
    slot_type = ma.StringField(required=False, allow_none=True,
                               ignore_missing=True)
    slot = ma.IntField()
    port = ma.IntField(required=False, allow_none=True, ignore_missing=True)
    type = ma.StringField(validator=_validate_type)

    @property
    def formatted_mac(self):
        return ":".join(s.encode('hex') for s in
                        self.mac.decode('hex')).upper()

    # indexes
    serial_number_index = SparseIndex().ascending('serial_number').unique()
    mac_index = Index().ascending('mac').unique()

    # magic methods
    def __str__(self):
        return "<NetworkInterfaces {}>".format(self.formatted_mac)


class MemoryModels(ma.Document):

    make = ma.RefField('Manufacturers')
    model = ma.StringField()
    type = ma.StringField()
    part_number = ma.StringField()
    capacity = ma.DocumentField('Bytes')
    speed = ma.DocumentField('Frequency')


class Memory(ma.Document):

    # parameters
    model_ref = ma.RefField('MemoryModels')
    serial_number = ma.StringField(allow_none=True)

    # indexes
    sn_index = Index().ascending('serial_number').unique()


class ServerMemory(ma.Document):

    # parameters
    module_ref = ma.RefField('Memory')
    module = module_ref.rel()
    bank = ma.StringField()
    slot = ma.StringField()
    current_speed = ma.IntField()

    # indexes
    module_index = Index().ascending('module_ref').unique()


class ManagementCredentials(ma.Document):

    user_name = ma.StringField(allow_none=True)
    password = ma.StringField(allow_none=True)
    ssh_key = ma.StringField(required=False, ignore_missing=True,
                             allow_none=True)


class ServerModels(ma.Document):

    make_ref = ma.RefField('Manufacturers')
    make = make_ref.rel()
    name = ma.StringField()
    height = ma.IntField(min_value=1)
    drive_slots = ma.IntField(required=False, allow_none=True)
    modular = ma.BoolField(default=False)

    def __str__(self):
        return "{}".format(self.name)

    # indexes
    make_model_index = Index().ascending('make_ref') \
        .ascending('name').unique()


class Servers(ma.Document):

    # parameters
    id = ma.StringField()
    model_ref = ma.RefField('ServerModels')
    model = model_ref.rel()
    host_name = ma.StringField(required=False, ignore_missing=True)
    name = ma.StringField(required=False, ignore_missing=True, allow_none=True)
    bios_version = ma.StringField(required=False, allow_none=True)
    bios_date = DateField(required=False, allow_none=True, ignore_missing=True)

    # cpu info
    cpus = ma.ListField(ma.DocumentField('Cpus'), required=False,
                        ignore_missing=True, default_empty=True)

    # memory info
    memory_refs = ma.SetField(ma.RefField('ServerMemory'), default_empty=True)
    memory = memory_refs.rel(ignore_missing=True)

    @property
    def memory_capacity(self):
        return sum([m.capacity for m in self.memory])

    # management info
    management = ma.DocumentField('ManagementCredentials', required=False,
                                  ignore_missing=True, allow_none=True)

    # group
    group_ref = ma.RefField('Groups', allow_none=True, ignore_missing=True)
    group = group_ref.rel(allow_none=True)

    # project
    project_ref = ma.RefField('Projects', required=False, allow_none=True,
                              ignore_missing=True, default=None)
    project = project_ref.rel(allow_none=True)

    # drives
    drive_refs = ma.ListField(ma.RefField('Drives'), required=False,
                              default_empty=True)
    drives = drive_refs.rel(ignore_missing=True)

    # virtual drives
    virtual_drives = ma.ListField(ma.DocumentField('VirtualDrives'),
                                  required=False, default_empty=True,
                                  ignore_missing=True)

    # interfaces
    interface_refs = ma.SetField(ma.RefField(), required=False,
                                  default_empty=True, ignore_missing=True)
    interfaces = interface_refs.rel(ignore_missing=True)

    # location
    location_ref = ma.RefField(required=False, validator=_validate_location,
                               allow_none=True, ignore_missing=True)
    location = location_ref.rel(allow_none=True)

    # properties
    @property
    def cpu_count(self):
        return len(self.cpus)

    @property
    def cpu_model(self):
        if len(self.cpus) > 0:
            return self.cpus[0]
        return None

    @property
    def link(self):
        return '/servers/{}'.format(self.id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.id)

    @property
    def management_link(self):
        if self.management:
            if self.management.link:
                return str(self.management.link)
            elif self.management.link:
                return self.management.link

    # indexes
    id_index = Index().ascending('id').unique()
    name_index = Index().ascending('name').unique()

    # magic methods
    def __str__(self):
        return "{} {}".format(self.model, self.id)


class SwitchModels(ma.Document):

    make_ref = ma.RefField('Manufacturers')
    make = make_ref.rel()
    name = ma.StringField()

    # indexes
    model_index = Index().ascending('make').ascending('name').unique()

    # magic_methods
    def __str__(self):
        return "{}".format(self.name)


class Switches(ma.Document):

    id = ma.StringField(required=True)
    # model
    model_ref = ma.RefField('SwitchModels')
    model = model_ref.rel()
    name = ma.StringField(required=False, allow_none=True)
    # group
    group_ref = ma.RefField('Groups', allow_none=True, ignore_missing=True)
    group = group_ref.rel(allow_none=True)
    # location
    location_ref = ma.RefField(required=False, validator=_validate_location,
                               allow_none=True, ignore_missing=True)
    location = location_ref.rel(allow_none=True)

    # properties
    @property
    def link(self):
        return '/switches/{}'.format(self.id)

    @property
    def management_link(self):
        if self.management:
            if self.management.link:
                return str(self.management.link)
            elif self.management.link:
                return self.management.link

    # indexes
    id_index = Index().ascending('id').unique()


class ProjectStatusTypes(ma.Document):

    def validate_color(color):
        match_string = re.compile(r'(?i)^(?:[0-9a-fA-F]{3}){1,2}$')
        return bool(match_string.search(color))

    status = ma.StringField()
    background_color = ma.StringField(validator=validate_color, required=False,
                                      ignore_missing=True, allow_none=True)
    text_color = ma.StringField(validator=validate_color, required=False,
                                ignore_missing=True, allow_none=True)

    @property
    def style(self):
        if not hasattr(self, 'background_color'):
            print "no background color for {}".format(self.status)
            if not hasattr(self, 'text_color'):
                print "no text color for {}".format(self.status)
                raise Exception('No colors!')

        style_string = ' style="'
        if hasattr(self, 'background_color'):
            style_string += 'background-color:{};'\
                .format(self.background_color)
        if hasattr(self, 'text_color'):
            style_string += 'color:{};'.format(self.text_color)

        return style_string

    def __repr__(self):
        return "<ProjectStatusTypes {}>".format(self.status)

    def __str__(self):
        return str(self.status)

    # indexes
    status_index = Index().ascending('status').unique()


class Projects(ma.Document):

    # parameters
    owner_ref = ma.RefField('Users')
    owner = owner_ref.rel()
    group_ref = ma.RefField('Groups')
    group = group_ref.rel()
    name = ma.StringField()
    description = ma.StringField(allow_none=True, ignore_missing=True,
                                 required=False)
    created_on = ma.CreatedField(tz_aware=True)
    modified_on = ma.ModifiedField(tz_aware=True)
    start_date = DateField(ignore_missing=True, allow_none=True,
                           required=False)
    target_end_date = DateField(ignore_missing=True, allow_none=True,
                                required=False)
    status_ref = ma.RefField('ProjectStatusTypes',
                             allow_none=True, ignore_missing=True)
    status = status_ref.rel(allow_none=True)
    updates = ma.ListField(ma.DocumentField('ProjectUpdates'),
                           required=False, allow_none=True,
                           default_empty=True)
    member_refs = ma.ListField(ma.RefField('Users'), required=False,
                               default_empty=True, ignore_missing=True)
    members = member_refs.rel(ignore_missing=True)
    archived = ma.BoolField(required=False, default=False)

    # link to info page
    @property
    def link(self):
        return "/projects/{}".format(self.mongo_id)

    @property
    def render(self):
        return '<a href="{}">{}</a>'.format(self.link, self.name)

    # relationships
    @property
    def servers(self):
        return Servers.query.filter(Servers.project_ref == self.to_ref()).all()

    # indexes
    project_name_index = Index().ascending('name').unique()

    # magic methods
    def __repr__(self):
        return "<Project {}>".format(self.name)

    def __str__(self):
        return str(self.name)


class ProjectUpdates(ma.Document):

    # parameters
    id_ = ma.ObjectIdField(auto=True)
    datetime = ma.DateTimeField(use_tz=False)
    user_ref = ma.RefField('Users')
    user = user_ref.rel()
    message = ma.StringField()


class JobDetails(ma.Document):

    # parameters
    datetime = ma.DateTimeField()
    message = ma.StringField()


class Jobs(ma.Document):

    _mapping = {0: 'Unknown',
                1: 'Started',
                2: 'Pending',
                3: 'Completed',
                4: 'Failed'}

    # parameters
    user_ref = ma.RefField('Users')
    user = user_ref.rel()
    description = ma.StringField()
    start_time = ma.DateTimeField(use_tz=False)
    end_time = ma.DateTimeField(use_tz=False, allow_none=True)
    status_number = ma.IntField()
    details = ma.ListField(ma.DocumentField('JobDetails'), default_empty=True)

    # properties
    def _get_status(self):
        return self._mapping[self.status_number]

    def _set_status(self, value):
        for k, v in self._mapping.items():
            if v.lower() == value.lower():
                self.status_number = int(k)
                break
        else:
            self.status_number = 0

    status = property(_get_status, _set_status)

    # magic methods
    def __repr__(self):
        return '<Jobs id {}>'.format(self.mongo_id)

    def __str__(self):
        return "JID {}".format(self.mongo_id)


# ============================= OS Models =============================
class OS(ma.Document):

    flavor = ma.StringField()
    version = ma.StringField()
    kernel = ma.StringField()
    initrd = ma.StringField()
    append = ma.StringField()
    validated = ma.BoolField(default=False)

    def __repr__(self):
        return '<OS: {} {}>'.format(self.flavor, self.version)

    def __str__(self):
        return '{} {}'.format(self.flavor, self.version)
