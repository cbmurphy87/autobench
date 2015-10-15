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


def dynamic_job_form(build_steps):

    class F(Form):
        pass

    F.job_name = StringField('job_name', validators=[DataRequired()])
    F.build = BooleanField('build', default=True)

    for i, step in enumerate(build_steps):
        for field in step.order:
            setattr(F, field + str(i+1), field)

    return F


def MacAddress(separator=':'):
    message = 'Must be in the format "ab{0}cd{0}ef{0}01{0}23{0}45"'\
        .format(separator)

    def _mac(form, field):
        pattern = re.compile('^(?:[a-fA-F0-9]{2}[:\- ]?){5}(?:[a-fA-F0-9]{2})$')
        if not pattern.match(field.data):
            raise ValidationError(message)

    return _mac


def IPAddress(separator='.'):
    message = 'Must be in the format "xxx{0}xxx{0}xxx{0}xxx"'\
        .format(separator)

    def _ip(form, field):
        pattern = re.compile('^(?:\d{1,3}\.?){3}(?:\d{1,3})$')
        if not pattern.match(field.data):
            raise ValidationError(message)

    return _ip


class CreateJobForm(Form):

    job_name = StringField('job_name', validators=[DataRequired()])
    build = BooleanField('build', default=True)
    target = QuerySelectField('target', query_factory=models.Servers.query
                              .order_by('id').all,
                              get_label='id', allow_blank=True,
                              blank_text='Select a target')
    command = StringField('command', validators=[DataRequired()])
    args = StringField('args')
    kwargs = StringField('kwargs')


class DeployForm(Form):

    def make_name(self):

        return '{} {}'.format(getattr(self, 'flavor'), getattr(self, 'version'))

    def get_vds():

        return models.VirtualStorageDevices.query\
            .filter_by(server_id='HZLBR22').all()

    target = QuerySelectField('target', query_factory=models.Servers.query
                              .filter_by(available=True).order_by('id').all,
                              get_label='id', allow_blank=True,
                              blank_text='Select a target',
                              validators=[required()])
    os = QuerySelectField('os', query_factory=models.OS.query
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
    command = StringField('command', validators=[DataRequired()])
    args = StringField('args', validators=[Optional()])
    kwargs = StringField('kwargs', validators=[Optional()])
    order = ('target', 'command', 'args', 'kwargs')


class LoginForm(Form):

    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])


class AddInventoryForm(Form):

    drac_ip = StringField('drac_ip', validators=[DataRequired(), IPAddress()])
    rack = IntegerField('rack', validators=[DataRequired(),
                                            NumberRange(min=1, max=15)])
    u = IntegerField('u', validators=[DataRequired(),
                                      NumberRange(min=1, max=42)])
