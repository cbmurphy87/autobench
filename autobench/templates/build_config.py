#!/usr/bin/python
import jinja2
import os

templateLoader = jinja2.FileSystemLoader(searchpath=os.getcwd())
templateEnv = jinja2.Environment(loader=templateLoader)

template = templateEnv.get_template(os.path.join('/configs/config.xml'))


class Salt(object):

    def __init__(self, target, command, args='', kwargs=''):
        super(Salt, self).__init__()
        self.target = target
        self.command = command
        self.args = args
        self.kwargs = kwargs

builder1 = Salt('mysql', 'cmd.run', '~/testvd.py')
builder2 = Salt('mysql2', 'cmd.run2', '~/testvd2.py')
builders = [builder1, builder2]

print template.render(builders=builders)
