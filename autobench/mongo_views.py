#!/usr/bin/python

# ============================== IMPORTS ==============================
# ___________________________ Flask Imports ___________________________
from flask import render_template, flash, redirect, session, url_for, \
    request, g, abort, send_from_directory
from flask_login import login_user, logout_user, current_user, \
    login_required
from sqlalchemy import desc

# ____________________________ App Imports ____________________________
from autobench import lm
from autobench import mongo_alchemy as ma
from autobench.mongo_forms import *
from functions.jenkinsMethods import *
from functions.mongo_actions import *
from mongo_models import Users, Servers

# _________________________ Standard Imports __________________________
from bson import DBRef, ObjectId
from jenkins import JenkinsException
from json import JSONEncoder

# _________________________ AAEBench Imports __________________________
from aaebench import customlogger


# ============================== METHODS ==============================
# ___________________________ LOGIN METHODS ___________________________
@lm.user_loader
def load_user(id_):

    return mongo_models.Users.query.filter_by(mongo_id=ObjectId(id_)).first()


def unauthorized():
    return redirect('/')


@myapp.before_request
def _before_request():
    try:
        g.mongo_user = current_user
    except:
        return render_template('500.html'), 500


# =============================== VIEWS ===============================
@myapp.route('/login', methods=['GET', 'POST'])
def _login():
    if g.mongo_user is not None and g.mongo_user.is_authenticated:
        return redirect('/')

    form = LoginForm()
    # validate login credentials
    if form.validate_on_submit():
        # get user from db
        user = mongo_models.Users.query \
                .filter_by(user_name=str(form.email.data)).first() \
               or \
               mongo_models.Users.query\
                   .filter_by(email=str(form.email.data)).first()

        # if valid user
        if user:
            # check password
            if user.check_password(str(form.password.data)):
                user.is_authenticated = True
                user.save()
                login_user(user, remember=True)
                flash('Hello, {}.'.format(user.first_name))

                return redirect('/')
            else:
                flash('Wrong password. Try again.')
        else:
            flash('Invalid username or e-mail. Try again.')
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash("Error in the {} field - {}".format(
                        getattr(form, field).label.text, error))
    return render_template('login.html',
                           title='Login',
                           date=get_date_last_modified(),
                           form=form)


@myapp.route('/logout')
def _logout():
    logout_user()
    flash('You have been logged out.')
    return redirect('/login')

# _______________________________ ROOT ________________________________
@myapp.route('/')
@login_required
def _root():
    user = g.mongo_user
    return render_template('index.html',
                           title='Home',
                           date=get_date_last_modified(),
                           user=user)


# _______________________________ INFO ________________________________
# methods used to get info
@myapp.route('/my_info')
@login_required
def _my_info():
    user = g.mongo_user
    return render_template('my_info.html',
                           title='My Info',
                           date=get_date_last_modified(),
                           user=user)


@myapp.route('/my_info/edit', methods=['GET', 'POST'])
@login_required
def _edit_my_info():
    user = g.mongo_user
    form = EditMyInfoForm()
    if form.validate_on_submit():
        if user.check_password(str(form.password.data)):
            message = update_my_info(form, user)
            flash(message)
            logger.debug(message)
            return redirect(url_for('_my_info'))
        else:
            flash('Invalid password. Try again.')

    # fill out form with current values, except for passwords
    for attr in form.data.keys():
        if attr in dir(user):
            field = getattr(form, attr)
            field.data = getattr(user, attr)

    return render_template('my_info_edit.html',
                           title='Edit About Me',
                           date=get_date_last_modified(),
                           user=user, form=form)


@myapp.route('/server_info', methods=['POST'])
@login_required
def _server_info():
    server_id = request.get_json().get('id')
    print 'fetching server id {}'.format(server_id)
    server = mongo_models.Servers.query.filter_by(id=server_id).first()
    print server.group
    return render_template('server_info.html',
                           server=server)


# _____________________________ INVENTORY _____________________________
@myapp.route('/inventory')
@login_required
def _inventory():
    user = g.mongo_user
    inventory = get_inventory(user)
    servers = inventory.get('servers')
    switches = inventory.get('switches')

    return render_template('inventory.html', title='Inventory',
                           user=user, servers=servers, switches=switches,
                           date=get_date_last_modified())


@myapp.route('/servers')
@login_required
def _servers():
    user = g.mongo_user
    inventory = get_inventory(user)
    servers = inventory.get('servers')

    return render_template('servers.html', title='Servers',
                           user=user, servers=servers,
                           date=get_date_last_modified())


@myapp.route('/switches')
@login_required
def _switches():
    user = g.mongo_user
    inventory = get_inventory(user)
    switches = inventory.get('switches')

    return render_template('switches.html', title='Switches',
                           user=user, switches=switches,
                           date=get_date_last_modified())


@myapp.route('/servers/add', methods=['GET', 'POST'])
@login_required
def _servers_add():
    user = g.mongo_user
    group_ids = [group.mongo_id for group in user.groups]
    AddServerForm = make_add_server_form(group_ids)
    form = AddServerForm()
    if form.validate_on_submit():
        print 'adding server'
        flash('Adding server. Wait 30 seconds, then refresh.')
        p = Process(target=add_server, args=(form, user))
        p.start()
        return redirect('/servers')
    elif request.method == 'POST':
        print form.errors

    return render_template('servers_add.html', title='Add Inventory',
                           date=get_date_last_modified(), user=user,
                           form=form)


@myapp.route('/servers/add/manual', methods=['GET', 'POST'])
@login_required
def _servers_add_manual():
    user = g.mongo_user
    group_ids = [group.mongo_id for group in user.groups]
    AddServerManualForm = make_add_server_manual_form(group_ids)
    form = AddServerManualForm()
    if form.validate_on_submit():
        return redirect('/servers')

    return render_template('servers_add_manual.html',
                           title='Add Server',
                           date=get_date_last_modified(), user=user,
                           form=form)


@myapp.route('/servers/<id_>')
@login_required
def _servers_id(id_):
    user = g.mongo_user
    server = mongo_models.Servers.query.filter_by(id=id_).first()
    return render_template('servers_id.html', title=id_, server=server,
                           date=get_date_last_modified(), user=user)


@myapp.route('/servers/<id_>/add_oob', methods=['GET', 'POST'])
@login_required
def _servers_id_add_oob(id_):
    user = g.mongo_user
    form = AddInterfaceForm()
    if form.validate_on_submit():
        add_interface(form, id_, user)
        return redirect('/servers/{}'.format(id_))
    return render_template('servers_id_add_oob.html',
                           title='Add Out of Band Interface', form=form,
                           date=get_date_last_modified(), user=user)


@myapp.route('/servers/<server_id>/edit', methods=['GET', 'POST'])
@login_required
def _servers_id_edit(server_id):
    user = g.mongo_user
    server = mongo_models.Servers.query.filter_by(id=server_id).first()
    ChangeForm = make_edit_server_form(user, server)
    form = ChangeForm()

    if form.validate_on_submit():
        message = edit_server_info(form, server_id)
        flash(message)
        logger.debug(message)
        return redirect('/servers/{}'.format(server_id))
    elif request.method == 'POST':
        flash('Invalid info. Try again.')

    # set all form values except management info
    for attr in form.data.keys():
        field = getattr(form, attr)
        if attr in ('project', 'group'):
            # continue, since these fields are set during form creation
            continue
        if hasattr(server, attr):
            field.data = getattr(server, attr)
        elif hasattr(server, 'management') and \
            hasattr(server.management, attr):
                field.data = getattr(server.management, attr)
        else:
            logger.debug('Server has no attr {}.'.format(attr))
    return render_template('servers_id_edit.html', title=server_id,
                           server=server, date=get_date_last_modified(),
                           user=user, form=form)


@myapp.route('/switches/add', methods=['GET', 'POST'])
@login_required
def _switches_add():
    user = g.mongo_user
    group_ids = [group.mongo_id for group in user.groups]
    AddSwitchForm = make_add_switch_form(group_ids)
    form = AddSwitchForm()
    if form.validate_on_submit():
        message = add_switch(form)
        flash(message)
        return redirect('/switches')

    return render_template('switches_add.html',
                           title='Add Switch',
                           date=get_date_last_modified(), user=user,
                           form=form)


@myapp.route('/switches/models/add', methods=['GET', 'POST'])
@login_required
def _switches_models_add():
    user = g.mongo_user
    form = AddSwitchModelForm()
    if form.validate_on_submit():
        message = add_switch_model(form)
        flash(message)
        return redirect('/switches')

    return render_template('switches_models_add.html',
                           title='Add Switch Model',
                           date=get_date_last_modified(), user=user,
                           form=form)


@myapp.route('/switches/add_manual', methods=['GET', 'POST'])
@login_required
def _switches_add_manual():
    user = g.mongo_user
    group_ids = [group.id for group in user.groups]
    AddSwitchManualForm = make_add_switch_manual_form(group_ids)
    form = AddSwitchManualForm()
    if form.validate_on_submit():
        return redirect('/switches')

    return render_template('switches_add.html',
                           title='Add Switch',
                           date=get_date_last_modified(), user=user,
                           form=form)


@myapp.route('/switches/<id_>')
@login_required
def _switches_id(id_):
    user = g.mongo_user
    switch = mongo_models.Switches.query.filter_by(id=id_).first()
    return render_template('switches_id.html', title=id_,
                           switch=switch, user=user,
                           date=get_date_last_modified())


@myapp.route('/switches/<switch_id>/edit', methods=['GET', 'POST'])
@login_required
def _switch_id_edit(switch_id):
    user = g.mongo_user
    switch = mongo_models.Switches.query.filter_by(id=switch_id).first()
    ChangeForm = make_edit_switch_form(user, switch)
    form = ChangeForm()

    if form.validate_on_submit():
        message = edit_switch_info(form, switch_id)
        flash(message)
        logger.debug(message)
        return redirect('/switches/{}'.format(switch_id))
    elif request.method == 'POST':
        flash('Invalid info. Try again.')

    # set all form values except management info
    for attr in form.data.keys():
        field = getattr(form, attr)
        if attr in ('project', 'group'):
            # continue, since these fields are set during form creation
            continue
        if hasattr(switch, attr):
            field.data = getattr(switch, attr)
        elif hasattr(switch, 'management') and \
                hasattr(switch.management, attr):
            field.data = getattr(switch.management, attr)
        else:
            logger.debug('Switch has no attr {}.'.format(attr))
    return render_template('switches_id_edit.html', title=switch_id,
                           switch=switch, date=get_date_last_modified(),
                           user=user, form=form)


@myapp.route('/servers/update', methods=['GET', 'POST'])
@login_required
def _servers_update():
    user = g.mongo_user
    server_id = request.get_json().get('id')
    update_server(server_id, user)
    flash('Updating server. Wait 30 seconds, then refresh.')

    return redirect('/servers')


@myapp.route('/servers/status', methods=['GET', 'POST'])
@login_required
def _servers_status():
    _id = request.get_json().get('id')
    _next = request.get_json().get('next')
    user = g.mongo_user
    server = Servers.query.filter_by(id=_id).first()
    if _next:
        return redirect(_next)
    return render_template('servers_status.html', server=server,
                           user=user)


@myapp.route('/servers/delete', methods=['GET', 'POST'])
@login_required
def _delete_id():
    id_ = request.get_json().get('id')
    user = g.mongo_user
    logger.info('User {} is deleting server {}'.format(user, id_))

    message = delete_server(id_, user)
    flash(message)

    return redirect('/servers')


# ______________________________ DEPLOY _______________________________
@myapp.route('/deploy', methods=['GET', 'POST'])
@login_required
def _deploy():
    user = g.mongo_user
    form = DeployForm()
    user_server_ids = [s.id for p in user.projects_owned for s in p.servers]
    print 'my servers: {}'.format(user_server_ids)

    query = mongo_models.Servers.query \
        .filter(mongo_models.Servers.id.in_(*user_server_ids)) \
        .ascending(mongo_models.Servers.id).all

    form.target.query_factory = query
    if form.validate_on_submit():
        # check that user owns server
        if not form.target.data.held_by == user.id:
            flash('You do not own this server!')
            return render_template('deploy.html', title='Tests',
                                   date=get_date_last_modified(),
                                   user=user, form=form)
        # start subprocess to deploy system
        p = Process(target=deploy_server, args=(form, user))
        p.start()

        message = 'Deploying {} {} to {}.' \
            .format(form.os.data.flavor,
                    form.os.data.version,
                    form.target.data.id)

        flash(message)

        return redirect(url_for('_inventory'))
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash("Error in the {} field - {}".format(
                        getattr(form, field).label.text, error))
    return render_template('deploy.html', title='Tests',
                           date=get_date_last_modified(),
                           user=user, form=form)


# _______________________________ JOBS ________________________________
@myapp.route('/jobs')
@login_required
def _jobs():

    user = g.mongo_user
    jobs = get_all_jobs(user)
    return render_template('jobs.html', title='Jobs', user=user,
                           jobs=jobs)


@myapp.route('/create_job')
@login_required
def _create_job():
    user = g.mongo_user
    return render_template('create_job.html', title='Create Job', user=user)


@myapp.route('/job/<_id>')
@login_required
def _job_id(_id):
    user = g.mongo_user
    job = get_job(_id)
    if not job:
        return redirect(url_for('_jobs'))
    return render_template('job_id.html', title='Jobs', user=user,
                           job=job)


@myapp.route('/jobs/delete')
@login_required
def _jobs_delete():
    user = g.mongo_user
    if not user.admin:
        return 'You must be admin to delete jobs!'
    try:
        return delete_all_jobs(user)
    except Exception as e:
        return e.message


# _____________________________ PROJECTS ______________________________
@myapp.route('/projects')
@login_required
def _projects():
    user = g.mongo_user

    projects = get_all_projects(user)
    print projects
    return render_template('projects.html', title='Projects', user=user,
                           projects=projects)


@myapp.route('/projects/add', methods=['GET', 'POST'])
@login_required
def _projects_add():
    user = g.mongo_user
    AddProjectForm = make_add_project_form(user)
    form = AddProjectForm()
    form.start_date.data = datetime.today()
    form.target_end_date.data = datetime.today()
    if form.validate_on_submit():
        flash(add_project(form, user))
        return redirect('/projects')

    return render_template('projects_add.html', title='Add Project',
                           user=user, form=form)


@myapp.route('/projects/delete', methods=['GET', 'POST'])
@login_required
def _projects_delete():
    user = g.mongo_user
    project_id = request.get_json().get('project_id')
    project = mongo_models.Projects.query.filter_by(mongo_id=project_id).first()
    if not (user == project.owner or user.admin):
        return 'You do not own this project!'
    return delete_project(project.mongo_id, user)


@myapp.route('/projects/<id_>')
@login_required
def _projects_id(id_):
    user = g.mongo_user
    project = get_project_by_id(id_)
    return render_template('project_id.html', title='Projects',
                           user=user, project=project)


@myapp.route('/projects/<id_>/edit', methods=['GET', 'POST'])
@login_required
def _projects_id_edit(id_):
    user = g.mongo_user
    project = get_project_by_id(id_)

    if not ((project.owner == user) or user.admin):
        flash('You do not own this project!')
        return redirect('/projects/{}'.format(id_))

    EditProjectForm = make_edit_project_form(project)
    form = EditProjectForm()

    if form.validate_on_submit():
        message = edit_project(project.mongo_id, user, form)
        logger.debug(message)
        flash(message)
        return redirect('/projects/{}'.format(id_))

    # set all form values
    for attr in project.__dict__['_values'].keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = project.__dict__['_values'].get(attr).value

    return render_template('project_id_edit.html', title='Edit Project',
                           user=user, project=project, form=form)


@myapp.route('/projects/<id_>/add_member', methods=['GET', 'POST'])
@login_required
def _projects_id_add_member(id_):
    user = g.mongo_user
    project = get_project_by_id(id_)
    AddProjectMemberForm = make_add_project_member_form(project)
    form = AddProjectMemberForm()
    if not ((project.owner == user) or user.admin):
        flash('You are not the owner of this project!')
        return redirect('/projects/{}'.format(id_))
    if form.validate_on_submit():
        message = add_project_member(form=form, user=user, project=project)
        flash(message)
        return redirect('/projects/{}'.format(id_))
    return render_template('project_id_add_member.html', title='Projects',
                           user=user, project=project, form=form)


@myapp.route('/projects/<id_>/remove_member', methods=['GET', 'POST'])
@login_required
def _projects_id_remove_member(id_):
    member_id = request.get_json().get('member_id')
    member = mongo_models.Users.query.filter_by(mongo_id=member_id).first()
    user = g.mongo_user
    project = get_project_by_id(id_)
    if not ((project.owner == user) or user.admin):
        return 'You are not the owner of this project!'
    message = remove_project_member(user=user, project=project, member=member)
    return message


@myapp.route('/projects/<id_>/add_server', methods=['GET', 'POST'])
@login_required
def _projects_id_add_server(id_):
    user = g.mongo_user
    project = get_project_by_id(id_)
    AddProjectServerForm = make_add_project_server_form(project)
    form = AddProjectServerForm()
    if not ((project.owner == user) or user.admin):
        flash('You are not the owner of this project!')
        return redirect('/projects/{}'.format(id_))
    if form.validate_on_submit():
        message = add_project_server(form=form, user=user, project=project)
        flash(message)
        return redirect('/projects/{}'.format(id_))
    return render_template('project_id_add_server.html', title='Projects',
                           user=user, project=project, form=form)


@myapp.route('/projects/<id_>/remove_server', methods=['GET', 'POST'])
@login_required
def _projects_id_remove_server(id_):
    server_id = request.get_json().get('server_id')
    server = mongo_models.Servers.query.filter_by(id=server_id).first()
    user = g.mongo_user
    project = get_project_by_id(id_)
    if not ((project.owner == user) or user.admin):
        return 'You are not the owner of this project!'
    message = remove_project_server(user=user, project=project,
                                    server_id=server.id)
    return message


@myapp.route('/projects/<id_>/add_status', methods=['GET', 'POST'])
@login_required
def _projects_id_add_status(id_):
    browser = request.user_agent
    user = g.mongo_user
    project = get_project_by_id(id_)
    form = AddProjectStatusForm()
    form.datetime.data = datetime.today()
    if not ((project.owner == user) or
            (user in project.members) or user.admin):
        flash('You are not the owner of this project!')
        return redirect('/projects/{}'.format(id_))
    if form.validate_on_submit():
        message = add_project_status(form=form, user=user,
                                     project_id=project.mongo_id)
        flash(message)
        return redirect('/projects/{}'.format(id_))
    return render_template('project_id_add_status.html',
                           title='Add Status', user=user, project=project,
                           form=form, browser=browser)


@myapp.route('/projects/<id_>/remove_status', methods=['GET', 'POST'])
@login_required
def _projects_id_remove_status(id_):
    status_id = request.get_json().get('status_id')
    user = g.mongo_user
    project = get_project_by_id(id_)
    if not ((project.owner == user) or user.admin):
        return 'You are not the owner of this project!'
    message = remove_project_status(user=user, project_id=project.mongo_id,
                                    status_id=status_id)
    logger.debug(message)
    return message


# ___________________________ JENKINS JOBS ____________________________
@myapp.route('/build_jenkins_job/<job_name>', methods=['POST', 'GET'])
@login_required
def _build_jenkins_job(job_name):
    logger.info('Building job {}!'.format(job_name))
    status = build_jenkins_job(job_name)
    flash(status)
    return redirect('/jenkins_jobs')


@myapp.route('/create_jenkins_job', methods=['GET', 'POST'])
@login_required
def _create_jenkins_job():
    user = g.mongo_user
    form = CreateJobForm()

    # set servers in form
    user_project_ids = [x.id for x in
                        mongo_models.Projects.query.filter_by(owner_id=user.id).all()]

    query = mongo_models.Servers.query\
        .filter(mongo_models.Servers.project_id.in_(user_project_ids)) \
        .order_by('id').all
    form.target.query_factory = query

    if form.validate_on_submit():
        make_jenkins_job(form)
        flash('Created job {}'.format(form.job_name.data))
        return redirect('/jenkins_jobs')
    elif request.method == 'POST':
        flash("Invalid entries.")
    return render_template('create_jenkins_job.html', title='Create Job',
                           date=get_date_last_modified(),
                           form=form,
                           user=user)


@myapp.route('/jenkins_jobs', methods=['GET', 'POST'])
@login_required
def _jenkins_jobs():
    user = g.mongo_user
    try:
        jobs = get_all_jenkins_info()
    except JenkinsException:
        return render_template('500.html'), 500
    return render_template('jenkins_jobs.html', title='Jenkins Jobs',
                           date=get_date_last_modified(),
                           jobs=get_all_jenkins_info(),
                           result=lambda x: get_last_jenkins_result(x),
                           user=user)


@myapp.route('/jenkins_jobs/<jobname>')
@login_required
def _jenkins_job_info(jobname):
    user = g.mongo_user
    job_info = get_jenkins_job_info(jobname)
    if job_info:
        return render_template('jenkins_job_info.html',
                               title='Job Info',
                               date=get_date_last_modified(),
                               job_info=job_info,
                               user=user)
    return redirect('/jenkins_jobs')


# __________________________ AUTOMATION JOBS __________________________
@myapp.route('/create_job/choices', methods=['GET', 'POST'])
@login_required
def _get_job_choices():
    last_step = request.get_json().get('last_step')
    # each entry should have a 'class' and an 'action', where 'class'
    # is the top-most string, and 'action' is the bottom most.
    step_map = {'OS': [{'CentOS': {'5': ['5.1', '5.2'],
                                   '6': '6.5',
                                   '7': ['7.0', '7.1']},
                              'Windows': {'2012': 'R2'},
                              'OpenSUSE': 'tumbleweed'}],
                'CentOS': [{'MySQL': ['5.5', '5.6']},
                           {'PostgreSQL': 'Latest'},
                           {'fio': 'Latest'},
                           {'IOMeter': 'Latest'}],
                'Windows': ['MSSQL', 'Oracle'],
                'OpenSUSE': ['MySQL', 'Hadoop'],
                'MySQL': ['sysbench', 'hammerdb'],
                'PostgreSQL': ['hammerdb', 'fio'],
                'MSSQL': ['hammerdb', 'fio'],
                'Oracle': ['hammerdb', 'fio'],
                'hammerdb': ["TPC-C", "TPC-E"],
                'sysbench': {'read': ['100%', '90%', '70%']},
                'fio': [{'read': ['100%', '90%', '70%', '50%']},
                        {'write': ['100%', '90%', '70%', '50%']}]}

    return render_template('job_choices.html', last_step=last_step,
                           step_map=step_map)


# _______________________________ ADMIN _______________________________
@myapp.route('/admin', methods=['GET', 'POST'])
@login_required
def _admin():
    user = g.mongo_user
    if not user.admin:
        logger.warning("User {} trying to access page '/admin' without "
                       "admin privilege.".format(user))
        abort(401)
    users = mongo_models.Users.query.ascending(mongo_models.Users.email).all()
    groups = mongo_models.Groups.query\
        .ascending(mongo_models.Groups.mongo_id).all()
    projects = mongo_models.Projects.query\
        .descending(mongo_models.Projects.mongo_id).all()
    rooms = mongo_models.Rooms.query.all()

    return render_template('admin/admin.html', title='Admin', user=user,
                           groups=groups, users=users, projects=projects,
                           rooms=rooms, date=get_date_last_modified())


@myapp.route('/admin/user/add', methods=['GET', 'POST'])
@login_required
def _admin_user_add():
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        abort(401)
    form = AddUserForm()
    if form.validate_on_submit():
        flash(add_user(form, user))
        return redirect('/admin')

    return render_template('admin/admin_user_add.html', title='Admin', user=user,
                           form=form, date=get_date_last_modified())


@myapp.route('/admin/users/delete', methods=['GET', 'POST'])
@login_required
def _delete_user():
    user_name = request.get_json().get('user_name')
    user = g.mongo_user
    if not user.admin:
        print 'You are not admin!'
        abort(401)
    message = delete_user(user_name, user)
    logger.debug(message)

    return JSONEncoder().encode({'message': message})


@myapp.route('/admin/users/<id_>', methods=['GET', 'POST'])
@login_required
def _user_info(id_):
    user = g.mongo_user
    if not user.admin:
        print 'User is not admin'
        abort(401)
    other_user = mongo_models.Users.query.filter_by(mongo_id=id_).first()
    if not (user.admin and user):
        return render_template('404.html', user=user), 404

    return render_template('admin/admin_users_id.html', title='User Info',
                           user=user,
                           date=get_date_last_modified(),
                           other_user=other_user)


@myapp.route('/admin/users/<user_name>/edit', methods=['GET', 'POST'])
@login_required
def _edit_user_info(user_name):
    user = g.mongo_user
    if not user.admin:
        abort(401)
    other_user = mongo_models.Users.query.filter_by(user_name=user_name).first()
    form = EditUserInfoForm()
    if not other_user:
        abort(401)

    if form.validate_on_submit():
        message = update_user_info(form, other_user.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/users/{}'.format(other_user.user_name))

    for attr in other_user.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(other_user, attr)

    return render_template('admin/admin_users_edit.html', title='Edit User Info',
                           user=user,
                           date=get_date_last_modified(), form=form)


@myapp.route('/groups/<id_>')
@login_required
def _groups_id(id_):
    user = g.mongo_user
    group = mongo_models.Groups.query.filter_by(mongo_id=id_).first()
    print group
    if not group:
        return render_template('404.html', user=user), 404

    return render_template('groups_id.html', title='Group Info',
                           user=user, group=group,
                           date=get_date_last_modified())


@myapp.route('/admin/groups/add', methods=['GET', 'POST'])
@login_required
def _admin_groups_add():
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        abort(401)
    form = AddGroupForm()
    if form.validate_on_submit():
        flash(add_group(form, user))
        return redirect('/admin')

    return render_template('admin/admin_groups_add.html', title='Admin',
                           user=user, form=form, date=get_date_last_modified())


@myapp.route('/admin/groups/delete', methods=['GET', 'POST'])
@login_required
def _delete_group():
    gid = request.get_json().get('gid')
    user = g.mongo_user
    if not user.admin:
        logger.warning('User {} trying to delete group {} without '
                       'admin privilege.'.format(user))
        abort(401)
    message = delete_group(gid, user)
    flash(message)
    logger.debug(message)

    return JSONEncoder().encode({'success': 1})


@myapp.route('/admin/groups/<id_>/edit', methods=['GET', 'POST'])
@login_required
def _groups_info_edit(id_):
    user = g.mongo_user
    form = EditGroupForm()
    group = mongo_models.Groups.query.filter_by(mongo_id=id_).first()
    print 'group: {}'.format(group)
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    if form.validate_on_submit():
        message = update_group_info(form, group.mongo_id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.mongo_id))

    for attr in dir(group):
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(group, attr)

    return render_template('admin/admin_groups_edit.html',
                           title='Edit Group Info',
                           user=user, group=group, form=form,
                           date=get_date_last_modified())


@myapp.route('/admin/groups/<group_id>/add_member', methods=['GET', 'POST'])
@login_required
def _groups_add_member(group_id):
    user = g.mongo_user
    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    AddGroupMemberForm = make_add_group_member_form(group_id)
    form = AddGroupMemberForm()

    if form.validate_on_submit():
        message = add_group_member(form, group.mongo_id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.mongo_id))

    return render_template('admin/admin_groups_add_member.html',
                           title='Add Group Member',
                           user=user, group=group, form=form,
                           date=get_date_last_modified())


@myapp.route('/admin/groups/<group_id>/remove_member', methods=['GET', 'POST'])
@login_required
def _groups_remove_member(group_id):
    user = g.mongo_user
    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404
    user_name = request.get_json().get('user_name')
    user_to_delete = mongo_models.Users.query.filter_by(user_name=user_name)\
        .first()

    message = remove_group_member(group_id, user_to_delete.mongo_id, user)

    return JSONEncoder().encode({'message': message})


@myapp.route('/admin/groups/<gid>/remove_server', methods=['GET', 'POST'])
@login_required
def _groups_remove_server(gid):
    user = g.mongo_user
    group = mongo_models.Groups.query.filter_by(mongo_id=gid).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404
    server_id = request.get_json().get('server_id')

    message = remove_group_server(group_id=gid, server_id=server_id, user=user)

    return JSONEncoder().encode({'message': message})


@myapp.route('/admin/groups/<group_id>/add_server', methods=['GET', 'POST'])
@login_required
def _groups_add_server(group_id):
    user = g.mongo_user
    group = mongo_models.Groups.query.filter_by(mongo_id=group_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    AddGroupServerForm = make_add_group_server_form()
    form = AddGroupServerForm()

    if form.validate_on_submit():
        message = add_group_server(form, group.mongo_id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.mongo_id))

    for attr in form.data.keys():
        if attr in dir(group):
            field = getattr(form, attr)
            field.data = getattr(group, attr)

    return render_template('admin/admin_groups_add_server.html',
                           title='Add Group Server',
                           user=user, group=group, form=form,
                           date=get_date_last_modified())


@myapp.route('/rooms')
@login_required
def _rooms():
    user = g.mongo_user
    rooms = mongo_models.Rooms.query.all()
    if not rooms:
        return render_template('500.html', user=user), 500

    return render_template('rooms.html', title='Rooms',
                           user=user, rooms=rooms,
                           date=get_date_last_modified())


@myapp.route('/rooms/<id_>')
@login_required
def _rooms_id(id_):
    user = g.mongo_user
    room = mongo_models.Rooms.query.filter_by(mongo_id=id_).first()
    racks = mongo_models.Racks.query.filter_by(location_ref=room.to_ref())\
        .ascending('number').all()
    print 'racks: {}'.format(racks)
    if not (user.admin and room):
        return render_template('404.html', user=user), 404

    return render_template('rooms_id.html', title='Room Info',
                           user=user, room=room, racks=racks,
                           date=get_date_last_modified())


@myapp.route('/admin/rooms/add', methods=['GET', 'POST'])
@login_required
def _admin_rooms_add():
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        abort(401)
    form = AddEditRoomForm()

    if form.validate_on_submit():
        flash(add_room(form, user))
        return redirect('/admin')

    return render_template('admin/admin_rooms_add.html', title='Admin',
                           user=user, form=form, date=get_date_last_modified())


@myapp.route('/admin/rooms/delete', methods=['GET', 'POST'])
@login_required
def _admin_rooms_delete():
    id_ = request.get_json().get('id')
    user = g.mongo_user
    if not user.admin:
        print 'You are not admin'
        abort(401)
    message = delete_room(id_, user)
    flash(message)
    logger.debug(message)

    return JSONEncoder().encode({'success': 1})


@myapp.route('/admin/rooms/<id_>/edit', methods=['GET', 'POST'])
@login_required
def _admin_rooms_id_edit(id_):
    user = g.mongo_user
    form = AddEditRoomForm()
    room = mongo_models.Rooms.query.filter_by(id=id_).first()
    racks = mongo_models.Racks.query.filter_by(room_id=room.id)
    if not (user.admin and room):
        return render_template('404.html', user=user), 404

    if form.validate_on_submit():
        message = edit_room_id(form, room.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/rooms/{}'.format(room.id))

    for attr in room.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(room, attr)

    return render_template('admin/admin_rooms_edit.html',
                           title='Edit Room Info',
                           user=user, room=room, form=form,
                           racks=racks,
                           date=get_date_last_modified())


@myapp.route('/racks/<id_>')
@login_required
def _admin_racks_id(id_):
    user = g.mongo_user
    rack = mongo_models.Racks.query.filter_by(mongo_id=id_).first()
    rack_units = [u.mongo_id for u in rack.units]
    # ##################################################
    #                  !!! FIX THIS !!!                #
    ####################################################
    servers = mongo_models.Servers.query.filter(mongo_models.Servers.id
                                                .in_(*rack_units)).all()

    if not (user.admin and rack):
        return render_template('404.html', user=user), 404

    return render_template('admin/racks_id.html', title='Rack Info',
                           user=user, rack=rack, servers=servers,
                           date=get_date_last_modified())


@myapp.route('/admin/racks/get', methods=['GET', 'POST'])
@login_required
def _admin_racks_get():
    room_id = request.get_json().get('room_id')
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        flash('You are not admin!')
        abort(401)

    racks = mongo_models.Racks.query.filter_by(room_id=room_id).all()
    return render_template('admin/rack_form.html', options=racks,
                           disabled=False, id='rack_input', name='rack')


@myapp.route('/admin/racks/models/get', methods=['GET', 'POST'])
@login_required
def _admin_racks_models_get():
    manufacturer = request.get_json().get('manufacturer')
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        flash('You are not admin!')
        abort(401)

    models = mongo_models.Manufacturers.query\
        .filter_by(manufactuer_ref=manufacturer.to_ref()).all()
    return render_template('admin/rack_model_form.html', options=models,
                           disabled=False, id='model', name='model')


@myapp.route('/admin/racks/add', methods=['GET', 'POST'])
@login_required
def _admin_racks_add():
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        abort(401)
    AddEditRackForm = make_add_edit_rack_form()
    form = AddEditRackForm()
    if form.validate_on_submit():
        flash(add_rack(form, user))
        return redirect('/admin')

    return render_template('admin/admin_racks_add.html', title='Admin',
                           user=user, form=form,
                           date=get_date_last_modified())


@myapp.route('/admin/racks/models/add', methods=['GET', 'POST'])
@login_required
def _admin_racks_models_add():
    user = g.mongo_user
    if not user.admin:
        logger.warning('User {} trying to add model without admin privilege.'
                       .format(user))
        abort(401)
    form = AddEditRackModelForm()
    if form.validate_on_submit():
        flash(add_rack_model(form, user))
        return redirect('/admin')

    return render_template('admin/admin_racks_models_add.html', title='Admin',
                           user=user, form=form,
                           date=get_date_last_modified())


@myapp.route('/admin/racks/<id_>/edit', methods=['GET', 'POST'])
@login_required
def _admin_racks_id_edit(id_):
    user = g.mongo_user
    rack = mongo_models.Racks.query.filter_by(mongo_id=id_).first()
    AddEditRackForm = make_add_edit_rack_form(rack.location)
    form = AddEditRackForm()
    if not (user.admin and rack):
        return render_template('404.html', user=user), 404

    if form.validate_on_submit():
        message = edit_rack_id(form, rack.mongo_id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/racks/{}'.format(rack.mongo_id))
    else:
        logger.error('Error with form: {}'.format(form.errors))

    for attr in form.data.keys():
        if attr in dir(rack):
            field = getattr(form, attr)
            field.data = getattr(rack, attr)

    return render_template('admin/admin_racks_id_edit.html',
                           title='Edit Rack Info',
                           user=user, form=form, rack=rack,
                           date=get_date_last_modified())


@myapp.route('/admin/racks/delete', methods=['GET', 'POST'])
@login_required
def _admin_racks_delete():
    id_ = request.get_json().get('id')
    user = g.mongo_user
    if not user.admin:
        print 'You are not admin'
        abort(401)
    message = delete_rack(id_, user)
    flash(message)
    logger.debug(message)

    return JSONEncoder().encode({'success': 1})


@myapp.route('/admin/rack_units/get', methods=['GET', 'POST'])
@login_required
def _admin_rack_units_get():
    rack_id = request.get_json().get('rack_id')
    user = g.mongo_user
    if not user.admin:
        print 'not admin'
        flash('You are not admin!')
        abort(401)

    rack_units = mongo_models.RackUnits.query.filter_by(rack_id=rack_id).all()

    return render_template('admin/rack_unit_form.html', options=rack_units,
                           disabled=False, id='u_input', name='u')


# ______________________________ DEBUG ________________________________
@myapp.route('/debug', methods=['GET'])
@login_required
def _debug():
    p = Process(target=_run_debug, args=[])
    p.start()
    return redirect(url_for('_last_debug'))


@myapp.route('/last_debug', methods=['GET'])
@login_required
def _last_debug():
    user = g.mongo_user
    return render_template('last_debug.html', title='Debug', user=user,
                           date=get_date_last_modified())


@myapp.route('/last_debug_raw/<path>', methods=['GET'])
@login_required
def _last_debug_path(path):
    return send_from_directory('/root/autobench/tmp/coverage',
                               path)


@myapp.route('/last_debug_raw/', methods=['GET'])
@login_required
def _last_debug_raw():
    return send_from_directory('/root/autobench/tmp/coverage', 'index.html')


@myapp.route('/last_debug_out', methods=['GET'])
@login_required
def _last_debug_out():
    user = g.mongo_user
    with open('last_debug.out', 'r') as f:
        text = f.read()
    if text:
        return render_template('last_debug_out.html', title='Debug', user=user,
                               date=get_date_last_modified(), text=text)
    flash('Could not get last debug output.')
    return redirect(url_for('_last_debug'))


# ______________________________ HANDLERS _____________________________
@myapp.errorhandler(401)
def unauthorized_error(error):
    user = g.mongo_user
    return render_template('401.html', user=user), 401


@myapp.errorhandler(404)
def not_found_error(error):
    user = g.mongo_user
    return render_template('404.html', user=user), 404


@myapp.errorhandler(500)
def internal_error(error):
    user = g.mongo_user
    db.session.rollback()
    return render_template('500.html', user=user), 500


# _____________________________ TEST VIEWS ____________________________
@myapp.route('/admin/test_mongo', methods=['GET', 'POST'])
def _test_mongo():
    # add object to location document
    user = g.mongo_user

    # create form and set choices
    form = MongoForm()
    choices = [(str(x.mongo_id), str(x.id))
               for x in mongo_models.Servers.query.all()]
    form.device_ref.choices = choices

    if form.validate_on_submit():
        mongo_upsert_device_location(form)
        return redirect('admin/test_mongo')

    return render_template('admin/admin_test.html',
                           user=user, form=form,
                           date=get_date_last_modified())


if __name__ == '__main__':
    logger = customlogger.create_logger('views')
    main()
else:
    logger = customlogger.get_logger(__name__)
