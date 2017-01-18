import datetime
import re
from jinja2 import evalcontextfilter, Markup
from time import strftime


def _split(s, idx=None, char=' '):
    split_list = str(s).split(char)
    if type(idx) == str:
        try:
            idx = int(idx)
        except:
            return 'bad'
    if type(idx) == int:
        return str(split_list[0])
    return split_list


def _datetime_format(s, fmt='%Y-%m-%d %H:%M:%S'):
    if not s:
        return s
    if isinstance(s, datetime.datetime):
        s = s.timetuple()
    return strftime(fmt, s)
