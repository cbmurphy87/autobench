import re
from jinja2 import evalcontextfilter, Markup


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
