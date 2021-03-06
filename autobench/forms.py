from flask_wtf import Form
from wtforms import StringField, BooleanField, TextAreaField, PasswordField, \
    SelectField, IntegerField
from wtforms.ext.sqlalchemy.fields import QuerySelectField, \
    QuerySelectMultipleField
from wtforms.fields.html5 import DateField, DateTimeField, EmailField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, \
    required, IPAddress, EqualTo, Regexp, email
from wtforms import widgets
from wtforms.validators import ValidationError
from sqlalchemy import collate, or_
from autobench import mysql_models, mongo_models


# =========================== Custom Fields ===========================
class ShowPasswordField(StringField):
    """
    Original source: https://github.com/wtforms/wtforms/blob/2.0.2/wtforms/
        fields/simple.py#L35-L42

    A StringField, except renders an ``<input type="password">``.
    Also, whatever value is accepted by this field is not rendered back
    to the browser like normal fields.
    """
    widget = widgets.PasswordInput(hide_value=False)


# ================ Validators =======================
def dynamic_job_form(build_steps):
    class F(Form):
        pass

    F.job_name = StringField('job_name', validators=[DataRequired()])
    F.build = BooleanField('build', default=True)

    for i, step in enumerate(build_steps):
        for field in step.order:
            setattr(F, field + str(i + 1), field)

    return F


class NotEqualTo(object):
    """
    Compares the values of two fields.

    :param fieldname:
        The name of the other field to compare to.
    :param message:
        Error message to raise in case of a validation error. Can be
        interpolated with `%(other_label)s` and `%(other_name)s` to provide a
        more helpful error.
    """

    def __init__(self, fieldname, message=None):
        self.fieldname = fieldname
        self.message = message

    def __call__(self, form, field):
        try:
            other = form[self.fieldname]
        except KeyError:
            raise ValidationError(field.gettext("Invalid field name '%s'.")
                                  .format(self.fieldname))
        if field.data == other.data:
            d = {
                'other_label': hasattr(other, 'label') and other.label.text
                               or self.fieldname,
                'other_name': self.fieldname
            }
            message = self.message
            if message is None:
                message = field.gettext('Field must not be equal to '
                                        '%(other_name)s.')

            raise ValidationError(message % d)


class MacAddress(Regexp):
    """
    Validates a MAC address.

    :param message:
        Error message to raise in case of a validation error.
    """

    def __init__(self, message=None):
        pattern = r'^(?:[0-9a-fA-F]{2}[:-]?){5}[0-9a-fA-F]{2}$'
        super(MacAddress, self).__init__(pattern, message=message)

    def __call__(self, form, field):
        message = self.message
        if message is None:
            message = field.gettext('Invalid Mac address.')

        super(MacAddress, self).__call__(form=form, field=field,
                                         message=message)


class MacOrIP(object):
    def __init__(self, message=None):
        self.message = message or 'Invalid Mac or IP address.'

    def __call__(self, form, field):
        try:
            try_mac = MacAddress(message=self.message)
            try_mac(form, field)
        except ValidationError:
            try_ip = IPAddress(message=self.message)
            try_ip(form, field)


# =========================== Generic Forms ===========================
class CreateJobForm(Form):

    def get_name(self):
            return self.get_name()

    job_name = StringField('Job Name', validators=[DataRequired()])
    build = BooleanField('Build', default='checked')
    target = QuerySelectField('Target', query_factory=mysql_models.Servers.query
                              .order_by('id').all,
                              get_label=get_name, allow_blank=True,
                              blank_text='Select a target')
    command = StringField('Command', validators=[DataRequired()])
    args = StringField('Args')
    kwargs = StringField('Kwargs')


class DeployForm(Form):

    # helper methods
    def make_name(self):
        return '{} {}'.format(getattr(self, 'flavor'),
                              getattr(self, 'version'))

    # fields
    target = QuerySelectField('Target', get_label='id', allow_blank=True,
                              blank_text='Select a target',
                              validators=[required()])
    os = QuerySelectField('OS', query_factory=mysql_models.OS.query
                          .filter_by(validated=True)
                          .order_by(mysql_models.OS.flavor,
                                    mysql_models.OS.version.desc()).all,
                          get_label=make_name, allow_blank=True,
                          blank_text='Select an OS',
                          validators=[required()])


class BuildStepForm(Form):
    target = QuerySelectField(query_factory=mysql_models.Servers.query
                              .order_by('id'))
    # target2 = QuerySelectField(query_factory=models.Servers.query
    #                            .filter_by(available=True)
    #                            .order_by('id'))
    command = StringField('Command', validators=[DataRequired()])
    args = StringField('Args', validators=[Optional()])
    kwargs = StringField('Kwargs', validators=[Optional()])
    order = ('target', 'command', 'args', 'kwargs')


class LoginForm(Form):
    email = StringField('E-mail or username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


def make_add_inventory_form(group_ids):
    class AddInventoryForm(Form):
        network_address = StringField('Management Mac/IP Address',
                                      validators=[DataRequired(), MacOrIP()])
        user_name = StringField('Username', default='root')
        password = StringField('Password', default='Not24Get')
        group = QuerySelectField('Group', allow_blank=True,
                                 get_label='group_name',
                                 blank_text='Select Group',
                                 query_factory=mysql_models.Groups.query
                                 .filter(mysql_models.Groups.id.in_(group_ids)).all)
        room = QuerySelectField('Room', allow_blank=False,
                                query_factory=mysql_models.Rooms.query.all)
        container = QuerySelectField('Container', allow_blank=False,
                                     query_factory=mysql_models.Containers.query.all)
        slot = QuerySelectField('Slot', allow_blank=False,
                                query_factory=mysql_models.ContainerSlots.query.all)

    return AddInventoryForm


def make_add_inventory_manual_form(group_ids):
    class AddInventoryForm(Form):
        network_address = StringField('Management Mac Address',
                                      validators=[DataRequired(),
                                                  MacAddress()])
        service_tag = StringField('Service Tag', validators=[DataRequired()])
        server_model = StringField('Model')
        user_name = StringField('Username', default='root')
        password = StringField('Password', default='Not24Get')
        group = QuerySelectField('Group', allow_blank=True,
                                 get_label='group_name',
                                 blank_text='Select Group',
                                 query_factory=mysql_models.Groups.query
                                 .filter(mysql_models.Groups.id.in_(group_ids)).all)

    return AddInventoryForm


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
                                                            message='Passwords '
                                                                    'must '
                                                                    'match')])
    password = PasswordField('Current Password',
                             validators=[DataRequired()])


class AddInterfaceForm(Form):
    network_address = StringField('Out of Band Mac/IP Address',
                                  validators=[DataRequired(), MacOrIP()])


class ChangeServerOwnerForm(Form):
    server = QuerySelectField('Server', get_label='id', allow_blank=True,
                              blank_text='Select a server',
                              query_factory=mysql_models.Servers.query.all)
    owner = QuerySelectField('Owner', query_factory=mysql_models.Users.query.all,
                             get_label='email')


def make_edit_inventory_form(current_server):
    class EditInventoryForm(Form):
        try:
            room_id = current_server.room.id
        except:
            room_id = None
        try:
            c_id = current_server.container.id
        except:
            c_id = None
        try:
            s_id = current_server.u.id
        except:
            s_id = None
        room = QuerySelectField('Room', id='room_input', get_label='name',
                                query_factory=mysql_models.Rooms.query.all,
                                default=mysql_models.Rooms.query
                                .filter(or_(mysql_models.Rooms.id == room_id,
                                            mysql_models.Rooms.id.is_(None))),
                                allow_blank=True, blank_text='Select a room')
        location = QuerySelectField('Location', id='location_input',
                                    get_label='location',
                                    query_factory=mongo_models.Location
                                    .query.all)
        name = StringField('Name')
        user_name = StringField('Username')
        password = StringField('Password')
        project_id = QuerySelectField('Project', get_label='name',
                                      allow_blank=True, blank_text='None',
                                      query_factory=mysql_models.Projects
                                      .query.all,
                                      default=mysql_models.Projects.query
                                      .filter_by(id=current_server.project_id)
                                      .first())

    return EditInventoryForm


# ============================ Admin Forms ============================
class EditUserInfoForm(Form):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    user_name = StringField('User Name', validators=[DataRequired()])
    email = EmailField('E-mail', validators=[email()])
    password = PasswordField('Password',
                             validators=[Optional(),
                                         Length(8, 32, 'New password must '
                                                       'be at least 8 '
                                                       'characters')])
    admin = BooleanField('Admin', default=False)


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


class DeleteUser(Form):
    user = QuerySelectField('User', get_label='email', allow_blank=True,
                            blank_text='Select User To Delete',
                            query_factory=mysql_models.Users.query
                            .order_by('email').all, validators=[DataRequired()])


class AddGroupForm(Form):
    group_name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])


class EditGroupForm(Form):
    group_name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])


class AddEditRoomForm(Form):
    name = StringField('Room Name', validators=[DataRequired()])
    type = QuerySelectField('Room Type', get_label='type', allow_blank=False,
                            query_factory=mysql_models.RoomTypes.query.all)
    description = TextAreaField('Description', validators=[DataRequired()])


def make_add_edit_rack_form(room=None):
    try:
        r_id = room.id
    except:
        r_id = None

    class AddEditRackForm(Form):
        room_id = QuerySelectField('Room Name', get_label='name',
                                   allow_blank=True,
                                   blank_text='Select Room',
                                   query_factory=mysql_models.Rooms.query.all,
                                   default=mysql_models.Rooms.query
                                   .filter_by(id=r_id))
        number = IntegerField('Rack Number', validators=[DataRequired()])
        min_u = IntegerField('Minimum U Number',
                             validators=[DataRequired()])
        max_u = IntegerField('Maximum U Number',
                             validators=[DataRequired()])

    return AddEditRackForm


def make_add_group_member_form(gid):
    # get list of user ids in group
    group = mysql_models.Groups.query.filter_by(id=gid).first()
    members = group.members
    member_list = [member.id for member in members]

    class AddGroupMember(Form):
        member = QuerySelectField('Member', get_label='user_name',
                                  allow_blank=True,
                                  blank_text='Select Member',
                                  query_factory=mysql_models.Users.query
                                  .filter(~mysql_models.Users.id.in_(member_list))
                                  .all, validators=[DataRequired()])

    return AddGroupMember


def make_add_group_server_form(gid):
    # get list of user ids in group
    group = mysql_models.Groups.query.filter_by(id=gid).first()
    servers = group.servers
    server_list = [server.id for server in servers]

    class AddGroupServerForm(Form):
        def get_name(self):
            return self.get_name()

        server = QuerySelectField('Server', get_label=get_name,
                                  allow_blank=True,
                                  blank_text='Select Server',
                                  query_factory=mysql_models.Servers.query
                                  .filter(~mysql_models.Servers.id.in_(server_list))
                                  .all, validators=[DataRequired()])

    return AddGroupServerForm


# =========================== Project Forms ===========================
def make_add_project_form(user):

    if user.admin:
        groups = mysql_models.Groups.query.all
    else:
        groups = user.groups.all

    class AddProjectForm(Form):

        name = StringField('Project Name', validators=[DataRequired()])
        primary_group = QuerySelectField('Primary group',
                                         query_factory=groups,
                                         get_label='group_name')
        start_date = DateField('Start Date', format='%Y-%m-%d')
        target_end_date = DateField('Target Completion Date')
        description = TextAreaField('Project Description')

    return AddProjectForm


def make_edit_project_form(project, user):

    if user.admin:
        groups = mysql_models.Groups.query.all
    else:
        groups = user.groups.all

    class EditProjectForm(Form):

        name = StringField('Project Name', validators=[DataRequired()])
        primary_group = QuerySelectField('Primary group',
                                         query_factory=groups)
        owner_id = QuerySelectField('Owner', query_factory=mysql_models.Users.query
                                    .all, default=mysql_models.Users.query
                                    .filter_by(id=project.owner.id).first())
        start_date = DateField('Start Date', format='%Y-%m-%d')
        target_end_date = DateField('Target Completion Date')
        status = SelectField('Status', choices=map(lambda x: (x, x),
                                                   mysql_models.Projects.status
                                                   .property.columns[0].type
                                                   .enums))
        description = TextAreaField('Project Description')
        archived = BooleanField('Archived')

    return EditProjectForm


class AddProjectStatusForm(Form):

    datetime = DateTimeField('Date', validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired()])


def make_add_project_member_form(project):

    # get list of user ids in group
    group = mysql_models.Groups.query.filter_by(id=project.gid).first()
    members = group.members
    member_list = [member.id for member in members
                   if not ((member in project.members) or
                           (member == project.owner))]

    class AddProjectMemberForm(Form):

        member = QuerySelectField('Member', allow_blank=True,
                                  blank_text='Select member',
                                  query_factory=mysql_models.Users.query
                                  .filter(mysql_models.Users.id.in_(member_list))
                                  .all, validators=[DataRequired()])

    return AddProjectMemberForm


def make_add_project_server_form(project):

    # get list of user ids in group
    group = mysql_models.Groups.query.filter_by(id=project.gid).first()
    servers = group.servers
    server_list = [server.id for server in servers
                   if not ((server in project.servers) or
                           server.project_id)]

    class AddProjectServerForm(Form):

        server = QuerySelectField('Server', allow_blank=True,
                                  blank_text='Select server',
                                  get_label='id',
                                  query_factory=mysql_models.Servers.query
                                  .filter(mysql_models.Servers.id.in_(server_list))
                                  .all, validators=[DataRequired()])

    return AddProjectServerForm

