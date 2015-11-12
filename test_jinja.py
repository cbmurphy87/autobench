Skip to content
Sign up Sign in
This repository  
Search
Explore
Features
Enterprise
Pricing
 Watch 50  Star 40  Fork 169 saltstack-formulas/mysql-formula
 Branch: master  mysql-formula/mysql/server.sls
e72c1c1  28 days ago
@pprkut pprkut Add states for optional dedicated salt user instead of root.
17 contributors @whiteinge @roock @cheuschober @babilen @madflojo @tiger-seo @madkinder @pprkut @RonWilliams @gravyboat @ogabrielsantos @davidjb @D3r3ck @phil-lavin @thatch45 @AlfonsFoubert @aboe76
RawBlameHistory     112 lines (102 sloc)  3.52 KB
{% from "mysql/defaults.yaml" import rawmap with context %}
{%- set mysql = salt['grains.filter_by'](rawmap, grain='os', merge=salt['pillar.get']('mysql:lookup')) %}

{% set os = salt['grains.get']('os', None) %}
{% set os_family = salt['grains.get']('os_family', None) %}
{% set mysql_root_user = salt['pillar.get']('mysql:server:root_user', 'root') %}
{% set mysql_root_password = salt['pillar.get']('mysql:server:root_password', salt['grains.get']('server_id')) %}
{% set mysql_host = salt['pillar.get']('mysql:server:host', 'localhost') %}
{% set mysql_salt_user = salt['pillar.get']('mysql:salt_user:salt_user_name', mysql_root_user) %}
{% set mysql_salt_password = salt['pillar.get']('mysql:salt_user:salt_user_password', mysql_root_password) %}

{% if mysql_root_password %}
    {% if os_family == 'Debian' %}
    mysql_debconf_utils:
      pkg.installed:
        - name: {{ mysql.debconf_utils }}

    mysql_debconf:
      debconf.set:
        - name: {{ mysql.server }}
        - data:
            '{{ mysql.server }}/root_password': {'type': 'password', 'value': '{{ mysql_root_password }}'}
            '{{ mysql.server }}/root_password_again': {'type': 'password', 'value': '{{ mysql_root_password }}'}
            '{{ mysql.server }}/start_on_boot': {'type': 'boolean', 'value': 'true'}
        - require_in:
          - pkg: mysqld
        - require:
          - pkg: mysql_debconf_utils
    {% elif os_family == 'RedHat' or 'Suse' %}
    mysql_root_password:
      cmd.run:
        - name: mysqladmin --user {{ mysql_root_user }} password '{{ mysql_root_password|replace("'", "'\"'\"'") }}'
        - unless: mysql --user {{ mysql_root_user }} --password='{{ mysql_root_password|replace("'", "'\"'\"'") }}' --execute="SELECT 1;"
        - require:
          - service: mysqld
    include:
      - mysql.python
        {% for host in ['localhost', 'localhost.localdomain', salt['grains.get']('fqdn')] %}
        mysql_delete_anonymous_user_{{ host }}:
          mysql_user:
            - absent
            - host: {{ host or "''" }}
            - name: ''
            - connection_host: '{{ mysql_host }}'
            - connection_user: '{{ mysql_salt_user }}'
            {% if mysql_salt_password %}
            - connection_pass: '{{ mysql_salt_password }}'
            {% endif %}
            - connection_charset: utf8
            - require:
              - service: mysqld
              - pkg: mysql_python
              {%- if (mysql_salt_user == mysql_root_user) and mysql_root_password %}
              - cmd: mysql_root_password
              {%- endif %}
        {% endfor %}
    {% endif %}
{% endif %}

{% if os_family == 'Arch' %}
# on arch linux: inital mysql datadirectory is not created
mysql_install_datadir:
  cmd.run:
    - name: mysql_install_db --user=mysql --basedir=/usr --datadir=/var/lib/mysql
    - user: root
    - creates: /var/lib/mysql/mysql/user.frm
    - require:
      - pkg: mysqld
      - file: mysql_config
    - require_in:
      - service: mysqld
{% endif %}

mysqld:
  pkg.installed:
    - name: {{ mysql.server }}
{% if os_family == 'Debian' and mysql_root_password %}
    - require:
      - debconf: mysql_debconf
{% endif %}
  service.running:
    - name: {{ mysql.service }}
    - enable: True
    - watch:
      - pkg: mysqld
mysql_config:
  file.managed:
    - name: {{ mysql.config.file }}
    - template: jinja
    - source: salt://mysql/files/my.cnf
    - watch_in:
      - service: mysqld
    {% if os_family in ['Debian', 'Gentoo', 'RedHat'] %}
    - user: root
    - group: root
    - mode: 644
    {% endif %}
# official oracle mysql repo
# creates this file, that rewrites /etc/mysql/my.cnf setting
# so, make it empty
mysql_additional_config:
  file.managed:
    - name: /usr/my.cnf
    - source: salt://mysql/files/usr-my.cnf
    - create: False
    - watch_in:
      - service: mysqld
Status API Training Shop Blog About Pricing
� 2015 GitHub, Inc. Terms Privacy Security Contact Help