#!/usr/bin/env python

import sys
import re
from csv import reader


def get_sqlite_create_mappings(tables):

    mappings = {}
    table_order = []

    create_string = re.compile(r'(?is)'
                               r'CREATE TABLE "?(?P<table_name>\w+)"?\s+\('
                               r'(?P<definitions>.*?)'
                               r'\);')
    column_string = re.compile(r'(?i)'
                               r'(?P<column_name>\w+)\s+'
                               r'(?P<data_type>[^\s]+)\s*'
                               r'(?P<options>.*)')
    constraint_string = re.compile(r'(?i)'
                                   r'^PRIMARY KEY|'
                                   r'^FOREIGN KEY|'
                                   r'^UNIQUE|'
                                   r'^CHECK')

    # loop over tables
    for table in tables:
        table_match = create_string.search(table)

        # make sure it matches table format
        if table_match:

            # get fields from table match
            fields = table_match.groupdict()
            table_name = fields.get('table_name')
            table_order.append(table_name)
            current_table = {'columns': [],
                             'constraints': []}
            definitions = fields.get('definitions')

            # loop over line in table definition, i.e. in parentheses
            # split by commas not enclosed in parenthesis
            # to avoid treating multiple definitions as one
            for line in re.split(r',(?![^\'()]*\))', definitions):
                line = line.strip()

                # check if line is a constraint, first
                is_constraint = constraint_string.search(line)
                if is_constraint:
                    current_table['constraints'].append(line)
                    continue

                # if not a constraint, check if it's a column
                is_column = column_string.search(line)
                if is_column:
                    current_table['columns'].append(is_column.groupdict())
                    continue
                else:
                    print 'Unrecognized command: {}'.format(line)

            # append table to mappings list
            mappings[table_name] = current_table

    return mappings, table_order


def get_sqlite_inserts(insert_commands, table_mappings):

    inserts = []

    insert_string = re.compile(r'(?i)'
                               r'INSERT\s+INTO\s+"(?P<table_name>\w+)"\s+'
                               r'VALUES\s*(?P<values>.*);')

    for command in insert_commands:
        insert = {}
        match = insert_string.search(command)
        if match:
            match = match.groupdict()
            table_name = match.get('table_name')
            insert['table_name'] = table_name
            values = match.get('values')
            value_list = split_commas(values.strip('()'))
            # get column order
            column_mapping = None
            try:
                column_mapping = table_mappings.get(table_name).get('columns')
            except:
                raise KeyError('No mapping for table {}.'.format(table_name))

            # ensure column length of mapping matches number of insert values
            if len(column_mapping) != len(value_list):
                raise ValueError('Length of mapping ({}) does not match insert '
                                 '({}) statement for table {}:'
                                 '\nINSERT: {}\nMAPPING: {}'
                                 .format(len(column_mapping),
                                         len(value_list), table_name,
                                         value_list, column_mapping))

            # process values, as they're all strings at this point
            for idx in range(len(value_list)):
                if (type(value_list[idx]) == str) and (
                        'gb' in value_list[idx].lower()):
                    try:
                        strip_value = int(value_list[idx].strip("'").split()[0])
                        value_list[idx] = strip_value
                    except:
                        value_list[idx] = strip_value
            insert['values'] = value_list

            inserts.append(insert)

    return inserts


def mysql_create_tables(create_objects, stream=sys.stdout):

    for table in create_objects:
        stream.write('CREATE TABLE {} ('.format(table.get('table')))
        columns = table.get('columns')
        constraints = table.get('constraints')
        last_column = columns[-1]
        for column in columns:
            # get row values
            column_name, data_type, options = column.get('column_name'), \
                                        column.get('data_type'), \
                                        column.get('options')

            # format line
            line = '    {} {}'.format(column_name, data_type)
            if options:
                line += ' {}'.format(options)
            if constraints or column != last_column:
                line += ','
            line += '\n'
            stream.write(line)
        for constraint in constraints:
            stream.write('    {}'.format(constraint))
            if constraint != constraints[-1]:
                stream.write(',')
        stream.write(');\n')


def mysql_insert_rows(rows, table_mappings, stream=sys.stdout):

    for row in rows:
        table_name = row.get('table_name')
        if table_name.lower().endswith('version'):
            continue
        table_mapping = [x.get('column_name') for x in
                         table_mappings.get(table_name).get('columns')]
        values = [str(x) for x in row.get('values')]
        # process values
        for idx in range(len(table_mapping)):
            # ensure BOOLEAN columns are 1 or 0
            if table_mapping[idx].lower().startswith('bool'):
                values[idx] = '1' if values[idx] in (1, '1', 't', 'T', True) \
                    else '0'


        stream.write('INSERT INTO {} ({})\nVALUES({});\n'
                     .format(table_name,
                             ','.join(table_mapping),
                             ','.join(values)))


def sql_to_objects():

    mappings = {}

    all_lines = sys.stdin.read()

    # get create table statements
    create_table_string = r'(?is)' \
                          r'CREATE TABLE.*?;'
    create_table_commands = [ct.group(0)
                             for ct in re.finditer(create_table_string,
                                                   all_lines)]
    print 'Found {} tables.'.format(len(create_table_commands))
    table_mappings, order = get_sqlite_create_mappings(create_table_commands)
    mappings['create'] = table_mappings

    # get insert statements
    insert_string = r'(?is)' \
                    r'INSERT INTO .*? VALUES.*?;'
    insert_commands = [ct.group(0) for ct in
                       re.finditer(insert_string, all_lines)]
    print 'Found {} inserts.'.format(len(insert_commands))
    inserts = get_sqlite_inserts(insert_commands, table_mappings)
    mappings['insert'] = inserts
    print 'Valid inserts: {}'.format(len(inserts))

    return mappings, order


def split_commas(text, delimiter=','):

    # loop over each character
    l = []
    s = r''
    opened = []
    for c in text:
        if c in ("'", '"'):
            if c in opened:
                opened.remove(c)
            else:
                opened.append(c)
            s += c
        elif c == '(':
            opened.append(c)
            s += c
        elif c == ')':
            if '(' in opened:
                opened.remove('(')
            s += c
        elif c == delimiter and not opened:
            l.append(s)
            s = ''
        else:
            s += c
    l.append(s)

    return l


def main():

    objects, order = sql_to_objects()
    creates = objects.get('create')
    inserts = objects.get('insert')
    print len(creates), len(inserts)
    #mysql_create_tables(objects.get('create'))
    inserts = objects.get('insert')
    with open('test.sql', 'w') as f:
        f.write('SET foreign_key_checks = 0;\n')
        mysql_insert_rows(inserts, creates, stream=f)
        f.write('SET foreign_key_checks = 1;\n')
    print 'Done!'


if __name__ == '__main__':
    main()
