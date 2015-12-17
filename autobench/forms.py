import re
from flask.ext.wtf import Form
from wtforms import StringField, BooleanField, TextAreaField, PasswordField, \
    SelectField, IntegerField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, \
    required, IPAddress, EqualTo, Regexp, email
from wtforms import widgets
from wtforms.validators import ValidationError
from sqlalchemy import collate
from autobench import models


# ================ Custom Fields =======================
class ShowPasswordField(StringField):
    """
    Original source: https://github.com/wtforms/wtforms/blob/2.0.2/wtforms/fields/simple.py#L35-L42

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

        super(MacAddress, self).__call__(form, field, message)


class MacOrIP(object):
    def __init__(self, message=None):
        self.message = message or 'Invalid Mac or IP address.'

    def __call__(self, form, field):
        try:
            print 'trying mac'
            try_mac = MacAddress(message=self.message)
            try_mac(form, field)
        except ValidationError:
            print 'trying ip'
            try_ip = IPAddress(message=self.message)
            try_ip(form, field)


# ================ Generic Forms =======================
class CreateJobForm(Form):
    job_name = StringField('Job Name', validators=[DataRequired()])
    build = BooleanField('Build', default=True)
    target = QuerySelectField('Target', query_factory=models.Servers.query
                              .order_by('id').all,
                              get_label='id', allow_blank=True,
                              blank_text='Select a target')
    command = StringField('Command', validators=[DataRequired()])
    args = StringField('Args')
    kwargs = StringField('Kwargs')


class DeployForm(Form):
    def make_name(self):
        return '{} {}'.format(getattr(self, 'flavor'), getattr(self, 'version'))

    target = QuerySelectField('Target', get_label='id', allow_blank=True,
                              blank_text='Select a target',
                              validators=[required()])
    os = QuerySelectField('OS', query_factory=models.OS.query
                          .filter_by(validated=True)
                          .order_by(collate(models.OS.flavor, 'NOCASE'),
                                    models.OS.version.desc()).all,
                          get_label=make_name, allow_blank=True,
                          blank_text='Select an OS',
                          validators=[required()])


class BuildStepForm(Form):
    target = QuerySelectField(query_factory=models.Servers.query
                              .filter_by(available=True)
                              .order_by('id'))
    target2 = QuerySelectField(query_factory=models.Servers.query
                               .filter_by(available=True)
                               .order_by('id'))
    command = StringField('Command', validators=[DataRequired()])
    args = StringField('Args', validators=[Optional()])
    kwargs = StringField('Kwargs', validators=[Optional()])
    order = ('target', 'command', 'args', 'kwargs')


class LoginForm(Form):
    email = StringField('E-mail', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class AddInventoryForm(Form):
    network_address = StringField('iDRAC/IPMI Mac/IP Address',
                                  validators=[DataRequired(), MacOrIP()])
    user_name = StringField('Username', default='root')
    password = StringField('Password', default='Not24Get')
    rack = IntegerField('Rack', validators=[DataRequired(),
                                            NumberRange(min=1, max=15)])
    u = IntegerField('U', validators=[DataRequired(),
                                      NumberRange(min=1, max=42)])


class EditMyInfoForm(Form):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    user_name = StringField('User Name', validators=[DataRequired()])
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
                              query_factory=models.Servers.query.all)
    owner = QuerySelectField('Owner', query_factory=models.Users.query.all,
                             get_label='email')


def makeEditForm(holder):
    class EditInventoryForm(Form):
        rack = StringField('Rack', validators=[DataRequired()])
        u = StringField('U', validators=[DataRequired()])
        name = StringField('Name')
        user_name = StringField('Username')
        password = StringField('Password')
        held_by = QuerySelectField('Owner', get_label='email', allow_blank=True,
                                   blank_text='None',
                                   query_factory=models.Users.query.
                                   order_by('email').all,
                                   default=models.Users.query.
                                   filter_by(id=holder).first())
        print held_by

    return EditInventoryForm


# ================ Admin Forms =======================
class EditUserInfoForm(Form):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    user_name = StringField('User Name', validators=[DataRequired()])
    password = PasswordField('Password',
                             validators=[Optional(),
                                         Length(8, 32, 'New password must '
                                                       'be at least 8 '
                                                       'characters')])
    admin = BooleanField('Admin', default=False)


class AddUser(Form):
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
                            query_factory=models.Users.query
                            .order_by('email').all, validators=[DataRequired()])
