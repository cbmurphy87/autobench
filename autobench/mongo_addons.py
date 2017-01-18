from autobench import mongo_alchemy as ma

from bson import DBRef, ObjectId
from datetime import date, datetime
import operator
from wtforms.validators import Regexp, DataRequired, ValidationError, IPAddress
from wtforms.fields import SelectFieldBase
from wtforms import widgets
from mongoalchemy.document import Document, Index
from mongoalchemy.fields import Field


# ================ Validators =======================
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


# =========================== Helper Methods ==========================
def identity_key(obj):

    if not isinstance(obj, Document):
        raise TypeError('identity_key function requires obj to be an '
                        'instance of type "Mongoalchemy.Document".'
                        ' obj, type(obj): {}, {}'.format(dir(obj), type(obj)))
    try:
        return DBRef(collection=obj.collection, id=ObjectId(obj.mongo_id))
    except:
        return DBRef(collection=obj.get_collection_name(),
                     id=ObjectId(obj.mongo_id))


# =========================== Custom Fields ===========================
class DateField(ma.DateTimeField):

    def __init__(self, **kwargs):
        super(DateField, self).__init__(**kwargs)

    def validate_wrap(self, value):
        if not isinstance(value, date):
            self._fail_validation_type(value, date)

        # min/max
        if self.min is not None and value < self.min:
            self._fail_validation(value, 'Date too old')
        if self.max is not None and value > self.max:
            self._fail_validation(value, 'Date too new')

    def wrap(self, value):
        self.validate_wrap(value)
        combine = datetime.combine(value, datetime.min.time())
        return self.constructor(combine)

    def validate_unwrap(self, value):
        if not isinstance(value, datetime):
            self._fail_validation_type(value, datetime)

    def unwrap(self, value, session=None):
        self.validate_unwrap(value)
        return value.date()


class QuerySelectField(SelectFieldBase):
    widget = widgets.Select()

    def __init__(self, label=None, validators=None, query_factory=None,
                 get_pk=None, get_label=None, allow_blank=False,
                 blank_text='', **kwargs):
        super(QuerySelectField, self).__init__(label, validators, **kwargs)
        self.query_factory = query_factory

        if get_pk is None:
            self.get_pk = identity_key
        else:
            self.get_pk = get_pk

        if get_label is None:
            self.get_label = lambda x: x
        elif isinstance(get_label, (basestring, str, unicode)):
            self.get_label = operator.attrgetter(get_label)
        else:
            self.get_label = get_label

        self.allow_blank = allow_blank
        self.blank_text = blank_text
        self.query = None
        self._object_list = None

    def _get_data(self):
        if self._formdata is not None:
            for pk, obj in self._get_object_list():
                if pk == self._formdata:
                    self._set_data(obj)
                    break
        return self._data

    def _set_data(self, data):
        self._data = data
        self._formdata = None

    data = property(_get_data, _set_data)

    def _get_object_list(self):
        if self._object_list is None:
            query = self.query or self.query_factory()
            self._object_list = list(
                (str(self.get_pk(obj)), obj) for obj in query)
        return self._object_list

    def iter_choices(self):
        if self.allow_blank:
            yield ('__None', self.blank_text, self.data is None)

        for pk, obj in self._get_object_list():
            yield (pk, self.get_label(obj), obj == self.data)

    def process_formdata(self, valuelist):
        if valuelist:
            if self.allow_blank and valuelist[0] == '__None':
                self.data = None
            else:
                self._data = None
                self._formdata = valuelist[0]

    def pre_validate(self, form):
        data = self.data
        if data is not None:
            for pk, obj in self._get_object_list():
                if data == obj:
                    break
            else:
                raise ValidationError(self.gettext('Not a valid choice'))
        elif self._formdata or not self.allow_blank:
            raise ValidationError(self.gettext('Not a valid choice'))


# ============================= Subclasses ============================
class SparseIndex(Index):

    """
    Custom Index class to add 'sparse' option for fields that need to be
    unique, but may be null
    """

    def __init__(self):
        super(SparseIndex, self).__init__()
        self.__sparse = True
        for attr, value in self.__dict__.items():
            if attr.startswith('_Index__'):
                new_attr = attr.replace('Index', 'SparseIndex')
                self.__dict__[new_attr] = self.__dict__.pop(attr)

    def ensure(self, collection):
        """
        Call the pymongo method ``ensure_index`` on the passed collection.

        :param collection: the ``pymongo`` collection to ensure this index \
                is on
        """
        components = []
        for c in self.components:
            if isinstance(c[0], Field):
                c = (c[0].db_field, c[1])
            components.append(c)

        extras = {}
        if self.__min is not None:
            print 'setting min'
            extras['min'] = self.__min
        if self.__max is not None:
            print 'setting max'
            extras['max'] = self.__max
        if self.__bucket_size is not None:
            print 'setting bucket_size'
            extras['bucket_size'] = self.__bucket_size
        if self.__expire_after is not None:
            print 'setting expire_after'
            extras['expireAfterSeconds'] = self.__expire_after
        if self.__sparse is not None:
            extras['sparse'] = True
        collection.ensure_index(components, unique=self.__unique,
                                drop_dups=self.__drop_dups, **extras)
        return self
