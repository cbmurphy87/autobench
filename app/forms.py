import re
from flask.ext.wtf import Form
from wtforms import StringField, BooleanField, TextAreaField, PasswordField, \
    SelectField, IntegerField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, \
    required
from wtforms.validators import ValidationError
from sqlalchemy import collate
from app import models

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


def MacAddress(separator=':'):
    message = 'Must be in the format "ab{0}cd{0}ef{0}01{0}23{0}45"' \
        .format(separator)

    def _mac(form, field):
        pattern = re.compile('^(?:[a-fA-F0-9]{2}[:\- ]?){5}(?:[a-fA-F0-9]{2})$')
        if not pattern.match(field.data):
            raise ValidationError(message)

    return _mac


def IPAddress(separator='.'):
    message = 'Must be in the format "xxx{0}xxx{0}xxx{0}xxx"' \
        .format(separator)

    def _ip(form, field):
        pattern = re.compile('^(?:\d{1,3}\.?){3}(?:\d{1,3})$')
        if not pattern.match(field.data):
            raise ValidationError(message)

    return _ip


def NotCurrentPassword():
    message = 'New password cannot be same as old password.'

    def _new_password(form, field):
        if field.data == form.password.data:
            raise ValidationError(message)

    return _new_password


def MatchNewPassword():
    message = 'Passwords do not match.'

    def _check_password(form, field):
        if field.data != form.new_password.data:
            raise ValidationError(message)

    return _check_password


# ================ Forms =======================
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

    def get_held_servers():
        return models.Servers.query \
            .filter_by(available=True) \
            .order_by('id').all

    target = QuerySelectField('Target', query_factory=get_held_servers(),
                              get_label='id', allow_blank=True,
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
    drac_ip = StringField('iDRAC/IPMI IP Address',
                          validators=[DataRequired(), IPAddress()])
    rack = IntegerField('Rack', validators=[DataRequired(),
                                            NumberRange(min=1, max=15)])
    u = IntegerField('U', validators=[DataRequired(),
                                      NumberRange(min=1, max=42)])


class EditInfoForm(Form):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    user_name = StringField('User Name', validators=[DataRequired()])
    new_password = PasswordField('New Password',
                                 validators=[Optional(),
                                             Length(8, 32, 'New password must '
                                                           'be at least 8 '
                                                           'characters'),
                                             NotCurrentPassword()])
    verify_new_password = PasswordField('Verify New Password',
                                        validators=[Optional(),
                                                    NotCurrentPassword(),
                                                    MatchNewPassword()])
    password = PasswordField('Current Password',
                             validators=[DataRequired()])
