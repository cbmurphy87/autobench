import re
from flask.ext.wtf import Form
from wtforms import StringField, BooleanField, TextAreaField, PasswordField, \
    SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from wtforms.validators import ValidationError


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


class CreateForm(Form):

    job_name = StringField('job_name', validators=[DataRequired()])
    build = BooleanField('build', default=True)
    target = SelectField('target', choices=[('mysql', 'MySQL')])
    command = StringField('command', validators=[DataRequired()])
    args = StringField('args')
    kwargs = StringField('kwargs')


class BuildStepForm(Form):

    target = SelectField('target', choices=[('mysql', 'MySQL')])
    command = StringField('command', validators=[DataRequired()])
    args = StringField('args', validators=[Optional()])
    kwargs = StringField('kwargs', validators=[Optional()])
    order = ('target', 'command', 'args', 'kwargs')


class LoginForm(Form):

    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])


class AddInventoryForm(Form):

    id = StringField('id', validators=(DataRequired(),))
    oob_mac = StringField('oob_mac', validators=(MacAddress(),))
    ib_mac = StringField('ib_mac', validators=(MacAddress(),))
    model = StringField('model')
    cpu_count = IntegerField('cpu_count',
                             validators=(Optional(),
                                         NumberRange(min=0, max=10)))
    cpu_model = StringField('oob_mac')
    memory_capacity = StringField('memory_capacity')
    rack = IntegerField('rack', validators=(DataRequired(),
                                            NumberRange(min=1, max=15)))
    u = IntegerField('u', validators=(DataRequired(),
                                      NumberRange(min=1, max=42)))
