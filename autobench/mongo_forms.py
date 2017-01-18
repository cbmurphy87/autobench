import operator
from bson import DBRef, ObjectId
from flask_wtf import Form
from wtforms import BooleanField, StringField, TextAreaField, \
    PasswordField, SelectField, widgets, IntegerField, FloatField
from wtforms.fields.html5 import DateField, DateTimeField, EmailField
from wtforms.validators import DataRequired, ValidationError, email, \
    Optional, Length, EqualTo, required

from autobench import mongo_alchemy as ma
from autobench import mongo_models
from autobench.mongo_addons import QuerySelectField, MacOrIP, NotEqualTo


# =========================== Generic Forms ===========================
class MongoForm(Form):

    device_ref = SelectField('Device Reference', coerce=str,
                             validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired()])


class LoginForm(Form):
    email = StringField('E-mail or username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


def make_add_server_form(group_ids):

    class AddServerForm(Form):
        network_address = StringField('Management Mac/IP Address',
                                      validators=[DataRequired(), MacOrIP()])
        user_name = StringField('Username', default='root')
        password = StringField('Password', default='Not24Get')
        group = QuerySelectField('Group', allow_blank=True,
                                 get_label='name',
                                 blank_text='Select Group',
                                 query_factory=mongo_models.Groups.query
                                 .filter(mongo_models.Groups.mongo_id
                                         .in_(*group_ids)).all,
                                 validators=[DataRequired()])
        room = QuerySelectField('Room', allow_blank=False,
                                query_factory=mongo_models.Rooms.query.all)

    return AddServerForm


def make_add_server_manual_form(group_ids):

    def get_makes():
        distinct_makes = mongo_models.ServerModels.query.distinct('make_ref')
        print distinct_makes, dir(distinct_makes[0]), distinct_makes[0].collection
        print 'Manufacturers: {}'.format(mongo_models.Manufacturers
                                         .get_collection_name())
        make_ids = [make.id for make in distinct_makes]
        makes = mongo_models.Manufacturers.query \
            .filter(mongo_models.Manufacturers.mongo_id.in_(*make_ids))
        print makes.all()
        return makes

    class AddServerManualForm(Form):
        make = QuerySelectField('Make', allow_blank=True,
                                blank_text='Select Make',
                                query_factory=get_makes)
        model = QuerySelectField('Model', allow_blank=True,
                                 blank_text='Select Model',
                                 query_factory=mongo_models
                                 .ServerModels.query.all)
        network_address = StringField('Management Mac/IP Address',
                                      validators=[Optional(), MacOrIP()])
        user_name = StringField('Username', default='root',
                                validators=[Optional()])
        password = StringField('Password', default='Not24Get',
                               validators=[Optional()])
        group = QuerySelectField('Group', allow_blank=True,
                                 get_label='name',
                                 blank_text='Select Group',
                                 query_factory=mongo_models.Groups.query
                                 .filter({'mongo_id': {'$in': group_ids}})
                                 .all, validators=[DataRequired()])
        room = QuerySelectField('Room', allow_blank=False,
                                query_factory=mongo_models.Rooms.query.all)

    return AddServerManualForm


def make_add_switch_form(group_ids):

    class AddSwitchForm(Form):
        id = StringField('Switch ID', validators=[DataRequired()])
        model = QuerySelectField('Model', allow_blank=False,
                                 blank_text='Select Model',
                                 query_factory=mongo_models.SwitchModels
                                 .query.all)
        group = QuerySelectField('Group', allow_blank=True,
                                 get_label='name',
                                 blank_text='Select Group',
                                 query_factory=mongo_models.Groups.query
                                 .filter({'mongo_id': {'$in': group_ids}})
                                 .all)
        location = QuerySelectField('Room', allow_blank=False,
                                    query_factory=mongo_models.Rooms.query.all)

    return AddSwitchForm


class AddSwitchModelForm(Form):
    make = QuerySelectField('Manufacturer', allow_blank=False,
                            blank_text='Select Make',
                            query_factory=mongo_models.Manufacturers
                            .query.all)
    name = StringField('Model', validators=[DataRequired()])


def make_edit_server_form(user, server):

    if user.admin:
        group_query_factory = mongo_models.Groups.query.all
        project_query_factory = mongo_models.Projects.query.all
    else:
        user_group_ids = [g.mongo_id for g in user.groups]
        user_group_refs = [g.to_ref() for g in user.groups]

        group_query_factory = mongo_models.Groups.query \
            .filter(mongo_models.Groups.mongo_id.in_(*user_group_ids)).all
        project_query_factory = mongo_models.Projects.query \
            .filter(mongo_models.Projects.group_ref.in_(*user_group_refs)).all

    if server.group:
        default_group = mongo_models.Groups.query \
            .filter_by(mongo_id=server.group.mongo_id).first
    else:
        default_group = None
    if server.project:
        default_project = mongo_models.Projects.query \
            .filter_by(mongo_id=server.project.mongo_id).first
    else:
        default_project = None

    class EditServerForm(Form):

        name = StringField('Name')
        user_name = StringField('Username')
        password = StringField('Password')
        group = QuerySelectField('Group', get_label='name',
                                 allow_blank=True, blank_text='None',
                                 query_factory=group_query_factory,
                                 default=default_group)
        project = QuerySelectField('Project', get_label='name',
                                   allow_blank=True, blank_text='None',
                                   query_factory=project_query_factory,
                                   default=default_project)

    return EditServerForm


def make_edit_switch_form(user, switch):

    if user.admin:
        group_query_factory = mongo_models.Groups.query.all
    else:
        user_group_ids = [g.mongo_id for g in user.groups]
        group_query_factory = mongo_models.Groups.query \
            .filter(mongo_models.Groups.mongo_id.in_(*user_group_ids)).all

    if switch.group:
        default_group = mongo_models.Groups.query \
            .filter_by(mongo_id=switch.group.mongo_id).first
    else:
        default_group = None

    class EditSwitchForm(Form):

        name = StringField('Name')
        group = QuerySelectField('Group', get_label='name',
                                 allow_blank=True, blank_text='None',
                                 query_factory=group_query_factory,
                                 default=default_group)
        location = QuerySelectField('Location', get_label='name',
                                    allow_blank=True, blank_text='None',
                                    query_factory=mongo_models.Rooms.query.all,
                                    default=switch.location)

    return EditSwitchForm


def make_add_project_form(user):

    if user.admin:
        groups = mongo_models.Groups.query.all
    else:
        group_ids = [g.mongo_id for g in user.groups]
        groups = mongo_models.Groups.query \
            .filter(mongo_models.Groups.mongo_id.in_(*group_ids)).all

    class AddProjectForm(Form):

        name = StringField('Project Name', validators=[DataRequired()])
        group = QuerySelectField('Primary group',
                                 query_factory=groups,
                                 get_label='name')
        start_date = DateField('Start Date', format='%Y-%m-%d')
        target_end_date = DateField('Target Completion Date')
        description = TextAreaField('Project Description')

    return AddProjectForm


def make_edit_project_form(project):

    class EditProjectForm(Form):

        name = StringField('Project Name', validators=[DataRequired()])
        group = QuerySelectField('Primary group',
                                 query_factory=mongo_models.Groups
                                 .query.all)
        owner = QuerySelectField('Owner',
                                 query_factory=mongo_models.Users.query.all,
                                 default=mongo_models.Users.query
                                 .filter_by(mongo_id=project.owner
                                            .mongo_id).first())
        start_date = DateField('Start Date')
        target_end_date = DateField('Target Completion Date')
        status = QuerySelectField('Status',
                                  query_factory=mongo_models.
                                  ProjectStatusTypes.query.all,
                                  default=project.status)
        description = TextAreaField('Project Description')
        archived = BooleanField('Archived')

    return EditProjectForm


class AddProjectStatusForm(Form):

    datetime = DateTimeField('Date', validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired()])


def make_add_project_member_form(project):

    # get list of user ids in group
    members = project.group.members
    member_list = [member.mongo_id for member in members
                   if not ((member in project.members) or
                           (member == project.owner))]
    print member_list

    class AddProjectMemberForm(Form):

        member = QuerySelectField('Member', allow_blank=True,
                                  blank_text='Select member',
                                  query_factory=mongo_models.Users.query
                                  .filter(mongo_models.Users.mongo_id.
                                          in_(*member_list))
                                  .all, validators=[DataRequired()])

    return AddProjectMemberForm


def make_add_project_server_form(project):

    # get list of user ids in group
    servers = [str(server.mongo_id) for server in project.group.servers]

    class AddProjectServerForm(Form):

        server = QuerySelectField('Server', allow_blank=True,
                                  blank_text='Select server',
                                  get_label='name',
                                  query_factory=mongo_models.Servers.query
                                  .filter(mongo_models.Servers.mongo_id
                                          .in_(*servers)).all,
                                  validators=[DataRequired()])

    return AddProjectServerForm


class EditGroupForm(Form):
    name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])


def make_add_group_member_form(group_id):
    # get list of user ids in group
    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
    members = group.members
    member_list = [str(member.mongo_id) for member in members]
    print member_list

    class AddGroupMember(Form):
        member = QuerySelectField('Member', get_label='user_name',
                                  allow_blank=True,
                                  blank_text='Select Member',
                                  query_factory=mongo_models.Users.query
                                  .filter(mongo_models.Users.mongo_id
                                          .nin(*member_list)).all,
                                  validators=[DataRequired()])

    return AddGroupMember


def make_add_group_server_form():

    all_free_servers = mongo_models.Servers.query \
        .filter_by(group_ref=None).all()
    server_list = [server.mongo_id for server in all_free_servers]
    print 'server list: {}'.format(server_list)

    class AddGroupServerForm(Form):
        def get_name(self):
            return self.name or self.host_name or self.mongo_id

        server = QuerySelectField('Server', get_label=get_name,
                                  allow_blank=True,
                                  blank_text='Select Server',
                                  query_factory=mongo_models.Servers.query
                                  .filter(mongo_models.Servers.mongo_id
                                          .in_(*server_list)).all,
                                  validators=[DataRequired()])

    return AddGroupServerForm


class AddUserForm(Form):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    user_name = StringField('User Name',
                            validators=[Optional(),
                                        Length(6, 32, 'Username must be at '
                                                      'least 6 characters')])
    email = StringField('E-mail', validators=[DataRequired(), email()])
    password = PasswordField('Password',
                             validators=[DataRequired(),
                                         Length(8, 32, 'Password must be '
                                                       'at least 8 '
                                                       'characters')])


class EditMyInfoForm(Form):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    user_name = StringField('User Name', validators=[DataRequired()])
    email = EmailField('E-mail', validators=[email()])
    new_password = PasswordField('New Password',
                                 validators=[Optional(),
                                             Length(8, 32, 'New password must '
                                                           'be at least 8 '
                                                           'characters'),
                                             NotEqualTo('password')])
    verify_new_password = PasswordField('Verify New Password',
                                        validators=[Optional(),
                                                    EqualTo('new_password',
                                                            message='Passwords'
                                                                    ' must '
                                                                    'match')])
    password = PasswordField('Current Password',
                             validators=[DataRequired()])


class DeployForm(Form):

    # helper methods
    def make_name(self):
        return '{} {}'.format(getattr(self, 'flavor'),
                              getattr(self, 'version'))

    # fields
    target = QuerySelectField('Target', get_label='name', allow_blank=True,
                              blank_text='Select a target',
                              validators=[required()],
                              get_pk=lambda x: x.id)
    os = QuerySelectField('OS', query_factory=mongo_models.OS.query
                          .filter_by(validated=True)
                          .descending(mongo_models.OS.flavor)
                          .descending(mongo_models.OS.version).all,
                          get_label=make_name, allow_blank=True,
                          blank_text='Select an OS',
                          validators=[required()])


class AddGroupForm(Form):
    name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])


def make_add_edit_rack_form(location=None):

    def default_room():
        if location:
            return mongo_models.Rooms.query\
                .filter_by(mongo_id=location.mongo_id).first()
        return None

    class AddEditRackForm(Form):
        location = QuerySelectField('Location', get_label='name',
                                    allow_blank=True,
                                    blank_text='Select Room',
                                    query_factory=mongo_models.Rooms.query.all,
                                    default=default_room)
        make = QuerySelectField('Make', get_label='name',
                                blank_text='Select Make',
                                query_factory=mongo_models.Manufacturers.query
                                .all)
        model = QuerySelectField('Model', get_label='name',
                                 blank_text='Select Model',
                                 query_factory=mongo_models.RackModels.query
                                 .all)
        serial_number = StringField('Serial Number', validators=[Optional()])
        number = IntegerField('Rack Number', validators=[DataRequired()])

    return AddEditRackForm


class AddEditRackModelForm(Form):

    make = QuerySelectField('Make', get_label='name', allow_blank=False,
                            blank_text='Select Manufacturer',
                            query_factory=mongo_models.Manufacturers.query.all)
    name = StringField('Model', validators=[DataRequired()])
    height = FloatField('Height', validators=[DataRequired()])
    width = FloatField('Width', validators=[DataRequired()])
    depth = FloatField('Depth', validators=[DataRequired()])
    units = QuerySelectField('Dimension Units', get_label='unit',
                             blank_text='Select units',
                             query_factory=mongo_models.LengthUnits
                             .query.all,
                             validators=[DataRequired()])
    number_of_units = IntegerField(validators=[DataRequired()])


class AddEditRoomForm(Form):

    name = StringField('Name')
    type = QuerySelectField('Room Type', allow_blank=False,
                            query_factory=mongo_models.RoomTypes.query.all)
    description = TextAreaField('Description')


class AddInterfaceForm(Form):
    network_address = StringField('Out of Band Mac/IP Address',
                                  validators=[DataRequired(), MacOrIP()])
