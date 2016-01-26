#!/usr/bin/python

# ============================== IMPORTS ==============================
# ___________________________ Flask Imports ___________________________
from flask import render_template, flash, redirect, session, url_for, request, \
    g, abort, send_from_directory
from flask.ext.login import login_user, logout_user, current_user, \
    login_required
from sqlalchemy import sql
from wtforms.ext.sqlalchemy.fields import QuerySelectField

# ____________________________ App Imports ____________________________
from autobench import myapp, lm
from autobench.forms import *
from models import Users, Servers

# _________________________ Standard Imports __________________________
from datetime import datetime
import fnmatch
from jenkins import JenkinsException
from json import JSONEncoder
from multiprocessing import Process
import os
from subprocess import Popen, PIPE

# _________________________ AAEBench Imports __________________________
from aaebench import customlogger
from aaebench.testautomation.syscontrol.file_transfer import SFTPManager
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from aaebench.testautomation.syscontrol.smcipmi import SMCIPMIManager
from aaebench.parents.managers import GenericManager

# ___________________________ Flask Imports ___________________________
from scripts.jenkinsMethods import *
from scripts.db_actions import *


# ============================== METHODS ==============================

# ___________________________ HELPER METHODS __________________________
def _get_date_last_modified():
    try:
        matches = []
        for root, dirnames, filenames in os.walk(os.getcwd()):
            for filename in fnmatch.filter(filenames, '*.html'):
                matches.append(os.path.join(root, filename))
        date = datetime.fromtimestamp(
            os.path.getctime(max(matches, key=os.path.getctime))).strftime(
            '%b %d %Y')
    except:
        date = '?'
    finally:
        return date


# _______________________ Asynchronous METHODS ________________________
# method for creating a separate process
def _deploy_server(form):

    message = 'Deploying {} {} to {} with ks {}.'.format(form.os.data.flavor,
                                                         form.os.data.version,
                                                         form.target.data.id,
                                                         form.os.data.append)
    logger.info(message)

    pxe_file = render_template('pxeboot',
                               kernel=form.os.data.kernel,
                               initrd=form.os.data.initrd,
                               append=form.os.data.append)

    # gather data
    server = form.target.data
    server_type = server.make
    interfaces = server.interfaces
    eth0_interface = interfaces.filter_by(name='NIC.1').first()
    eth0 = eth0_interface.mac.lower().replace(':', '-')
    logger.debug('eth0 mac: {}'.format(eth0))
    ipmi_int = interfaces.filter_by(name='DRAC').first() or \
               interfaces.filter_by(name='ipmi').first()
    if not ipmi_int:
        raise Exception('Could not find ipmi interface!')
    ipmi_ip = ipmi_int.ip

    logger.debug('IPMI ip address is: {}'.format(ipmi_ip))

    # send unique config file to pxe server
    sftp = SFTPManager('pxe.aae.lcl')
    client = sftp.create_sftp_client()
    filename = '/tftpboot/pxelinux.cfg/01-{}'.format(eth0)
    # write file
    with client.open(filename, 'w') as f:
        f.write(pxe_file)
    # delete salt key
    logger.debug(server.id)
    salt_master_manager = GenericManager(hostname='salt-gru.aae.lcl',
                                         username='salt',
                                         password='Not24Get',
                                         local=False,
                                         ending='$')
    command = ['salt-key', '-d', str(server.id), '-y']
    salt_master_manager.connection.exec_command(' '.join(command))

    # reboot server to PXE
    if server_type.lower() == 'dell':
        logger.debug('Detected server is a Dell. Using RACADM.')
        ipmi = RacadmManager(ipmi_ip)
    else:
        logger.debug('Detected server is not a Dell. Using IPMI.')
        ipmi = SMCIPMIManager(ipmi_ip)

    ipmi.boot_once('PXE', reboot=True)

    # make server unavailable
    try:
        user = g.user
        server = models.Servers.query.filter_by(id=server.id).first()
        server.available = False
        server.held_by = user.id
        db.session.commit()
        logger.info('Server {} now unavailable.'.format(server))
    except Exception as e:
        logger.error('Error making server unavailable: {}'.format(e))
        db.session.rollback()


# method to run new debug
def _run_debug():
    test_path = os.path.join(os.getcwd(), 'unit_tests.py')
    p = Popen(test_path, stdout=PIPE, stderr=PIPE)
    response, err = p.communicate()
    with open(os.path.join(os.getcwd(), 'last_debug.out'), 'w+') as f:
        f.write(response)
        if err:
            f.write('\n\nErrors:\n')
            f.write(err)


# ___________________________ LOGIN METHODS ___________________________
@lm.user_loader
def load_user(id):
    return Users.query.get(id)


def unauthorized():
    return redirect(url_for('_login'))


@myapp.before_request
def _before_request():
    try:
        g.user = current_user
    except:
        return render_template('500.html'), 500


# =============================== VIEWS ===============================
@myapp.route('/login', methods=['GET', 'POST'])
def _login():
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('_root'))

    form = LoginForm()
    # validate login credentials
    if form.validate_on_submit():
        try:
            # get user from db
            user = Users.query.filter_by(email=str(form.email.data)).first()
        except Exception as e:
            logger.error('Error fetching user: {}'.format(e))
        # if valid user
        if user:
            # check password
            if user.check_password(str(form.password.data)):
                user.is_authenticated = True
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                flash('Hello, {}.'.format(user.first_name))

                return redirect(url_for('_root'))
            else:
                flash('Wrong password. Try again.')
        else:
            flash('Invalid e-mail. Try again.')
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash("Error in the {} field - {}".format(
                    getattr(form, field).label.text, error))
    return render_template('login.html',
                           title='Login',
                           date=_get_date_last_modified(),
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
    user = g.user
    return render_template('index.html',
                           title='Home',
                           date=_get_date_last_modified(),
                           user=user)


# _______________________________ INFO ________________________________
# methods used to get info
@myapp.route('/my_info')
@login_required
def _my_info():
    user = g.user
    return render_template('my_info.html',
                           title='My Info',
                           date=_get_date_last_modified(),
                           user=user)


@myapp.route('/my_info/edit', methods=['GET', 'POST'])
@login_required
def _edit_my_info():
    user = g.user
    form = EditMyInfoForm()
    if form.validate_on_submit():
        if user.check_password(str(form.password.data)):
            message = update_my_info(form, user)
            flash(message)
            logger.debug(message)
            return redirect(url_for('_my_info'))
        else:
            flash('Invalid password. Try again.')

    for attr in user.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(user, attr)

    return render_template('edit_my_info.html',
                           title='Edit About Me',
                           date=_get_date_last_modified(),
                           user=user, form=form)


@myapp.route('/server_info', methods=['POST'])
@login_required
def _server_info():
    server_id = request.get_json().get('id')
    return render_template('server_info.html',
                           server=models.Servers.query
                           .filter_by(id=server_id).first())


# _____________________________ INVENTORY _____________________________
@myapp.route('/inventory')
@login_required
def _inventory():

    user = g.user
    servers = get_inventory(user)

    return render_template('inventory.html', title='Inventory',
                           date=_get_date_last_modified(),
                           user=user, servers=servers)


@myapp.route('/inventory/add', methods=['GET', 'POST'])
@login_required
def _add_inventory():
    user = g.user
    group_ids = [group.id for group in user.groups]
    AddInventoryForm = make_add_inventory_form(group_ids)
    form = AddInventoryForm()
    if form.validate_on_submit():
        flash('Adding server. Wait 30 seconds, then refresh.')
        p = Process(target=add_inventory, args=(form, user))
        p.start()
        return redirect('/inventory')

    return render_template('inventory_add.html', title='Add Inventory',
                           date=_get_date_last_modified(), user=user,
                           form=form)


@myapp.route('/inventory/<_id>')
@login_required
def _inventory_id(_id):
    user = g.user
    server = Servers.query.get(_id)
    user_holding = server.holder
    return render_template('inventory_id.html', title=_id, server=server,
                           date=_get_date_last_modified(), user=user,
                           user_holding=user_holding)


@myapp.route('/inventory/<_id>/add_oob', methods=['GET', 'POST'])
@login_required
def _inventory_id_add_oob(_id):
    user = g.user
    form = AddInterfaceForm()
    if form.validate_on_submit():
        add_interface(form, _id, user)
        return redirect('/inventory/{}'.format(_id))
    return render_template('inventory_add_oob.html',
                           title='Add Out of Band Interface', form=form,
                           date=_get_date_last_modified(), user=user)


@myapp.route('/inventory/<_id>/edit', methods=['GET', 'POST'])
@login_required
def _inventory_edit_id(_id):
    user = g.user
    server = Servers.query.get(_id)
    ChangeForm = makeEditForm(holder=server.held_by)
    form = ChangeForm()
    form.held_by = QuerySelectField('Owner', get_label='id',
                                    query_factory=models.Users.query.
                                    order_by('email').all,
                                    default=server.holder)
    if form.validate_on_submit():
        message = edit_server_info(form, _id)
        flash(message)
        logger.debug(message)
        return redirect('/inventory/{}'.format(_id))
    elif request.method == 'POST':
        flash('Invalid info. Try again.')

    for attr in server.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(server, attr)
    return render_template('inventory_edit_id.html', title=_id, server=server,
                           date=_get_date_last_modified(), user=user, form=form)


@myapp.route('/inventory/update', methods=['GET', 'POST'])
@login_required
def _update_inventory():
    user = g.user
    _id = request.get_json().get('id')
    try:
        server = Servers.query.filter_by(id=_id).first()
        flash('Updating server. Wait 30 seconds, then refresh.')
        logger.info('Updating server {}.'.format(server.id))
        make = server.make or 'unknown'
        if make.lower() == 'dell':
            target = update_dell_server
        elif 'super' in make.lower():
            target = update_smc_server
        else:
            message = 'Could not get server make'
            logger.error(message)
            raise Exception(message)
        p = Process(target=target, args=(server, user))
        p.start()
    except Exception as e:
        logger.error('Could not update server {}.: {}'.format(server.id, e))
    return redirect('inventory')


@myapp.route('/inventory/status', methods=['GET', 'POST'])
@login_required
def _inventory_status():
    _id = request.get_json().get('id')
    _next = request.get_json().get('next')
    user = g.user
    server = Servers.query.filter_by(id=_id).first()
    user_holding = server.holder
    if _next:
        return redirect(_next)
    return render_template('inventory_status.html', server=server,
                           user=user, user_holding=user_holding)


@myapp.route('/inventory/checkout', methods=['GET', 'POST'])
@login_required
def _checkout_id():
    _id = request.get_json().get('id')
    _next = request.get_json().get('next')
    user = g.user
    logger.info('User {} checking out {}'.format(user, _id))
    server = Servers.query.filter_by(id=_id).first()
    if server.available and not server.holder:
        try:
            server.available = False
            server.held_by = user.id
            db.session.add(server)
            db.session.commit()
        except Exception as e:
            'Exception in checkout: {}'.format(e)
            db.session.rollback()
    if _next:
        return redirect(_next)
    # check status of server
    server = Servers.query.filter_by(id=_id).first()
    try:
        if server.held_by == user.id:
            i_am_holder = True
            title = 'Release this server'
            color = 'green'
        else:
            i_am_holder = False
            holder_name = str(server.holder)
            title = 'This server is held by {}'.format(holder_name)
            color = 'red'
        if server.dirty:
            logger.info('Server is dirty.')
            color = 'yellow'
        server_json = JSONEncoder().encode({'available': server.available,
                                            'i_am_holder': i_am_holder,
                                            'title': title,
                                            'color': color})
        return server_json
    except Exception as e:
        logger.error("Couldn't encode server: {}".format(e))
    return JSONEncoder().encode({'available': False,
                                 'i_am_holder': False,
                                 'held_by': 'unknown',
                                 'title': 'Server state is unknown',
                                 'color': 'red'})


@myapp.route('/inventory/delete', methods=['GET', 'POST'])
@login_required
def _delete_id():
    _id = request.get_json().get('id')
    user = g.user
    logger.info('User {} is deleting server {}'.format(user, _id))
    server = Servers.query.filter_by(id=_id).first()
    drives = server.drives
    try:
        for drive in drives:
            db.session.delete(drive)
        db.session.commit()
        db.session.delete(server)
        db.session.commit()
        logger.info('Server successfully deleted.')
    except Exception as e:
        logger.error('Error deleting server {}: {}'.format(_id, e))
        db.session.rollback()

    i_am_holder = (server.held_by == user.id)
    if i_am_holder:
        title = 'Release this server'
        color = 'green'
    else:
        title = 'This server is held by {}'.format(str(server.holder))
        color = 'red'
    server_json = JSONEncoder().encode({'available': server.available,
                                        'i_am_holder': i_am_holder,
                                        'title': title,
                                        'color': color})
    return server_json


@myapp.route('/inventory/release', methods=['GET', 'POST'])
@login_required
def _release():
    _id = request.get_json().get('id')
    _next = request.get_json().get('next')
    user = g.user
    logger.info('User {} releasing {}'.format(user, _id))
    server = Servers.query.filter_by(id=_id).first()
    user_holding = server.holder
    try:
        holding_user_id = user_holding.id
        if user.id == holding_user_id:
            server.available = True
            server.held_by = sql.null()
            try:
                db.session.add(server)
                db.session.commit()
            except:
                db.session.rollback()
            title = 'Check out this server'
            color = 'blue'
        else:
            title = 'Server in unknown state'
            server.available = False
            color = 'red'
        if server.dirty:
            logger.info('Server is dirty.')
            color = 'yellow'
        i_am_holder = False

        server_json = JSONEncoder().encode({'available': server.available,
                                            'i_am_holder': i_am_holder,
                                            'title': title,
                                            'color': color})
        return server_json
    except:
        logger.error('Could not get user holding server.')
    if _next:
        return redirect(_next)
    logger.error('Error releasing server. Server may be in unknown state.')
    return JSONEncoder().encode({'available': server.available,
                                 'i_am_holder': False,
                                 'title': 'Error getting status'})


# ______________________________ DEPLOY _______________________________
@myapp.route('/deploy', methods=['GET', 'POST'])
@login_required
def _deploy():
    user = g.user
    form = DeployForm()
    form.target.query_factory = models.Servers.query \
        .filter_by(held_by=user.id).order_by('id').all
    servers = models.Servers.query
    if form.validate_on_submit():
        # check that user owns server
        if not form.target.data.held_by == user.id:
            flash('You do not own this server!')
            return render_template('deploy.html', title='Tests',
                                   date=_get_date_last_modified(),
                                   user=user, form=form, servers=servers)
        # start subprocess to deploy system
        p = Process(target=_deploy_server, args=(form,))
        p.start()

        message = 'Deploying {} {} to {}.'\
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
                           date=_get_date_last_modified(),
                           user=user, form=form, servers=servers)


# _______________________________ JOBS ________________________________
@myapp.route('/jobs')
@login_required
def _jobs():
    user = g.user
    jobs = get_all_jobs()
    return render_template('jobs.html', title='Jobs', user=user, jobs=jobs)


@myapp.route('/job/<_id>')
@login_required
def _job_id(_id):
    user = g.user
    job = get_job(_id)
    if not job:
        return redirect(url_for('_jobs'))
    return render_template('job_id.html', title='Jobs', user=user, job=job)


@myapp.route('/jobs/delete')
@login_required
def _jobs_delete():
    user = g.user
    if not user.admin:
        return 'You must be admin to delete jobs!'
    try:
        delete_all_jobs()
        return 'Successfully deleted all jobs.'
    except Exception as e:
        return e.message


# _____________________________ PROJECTS ______________________________
@myapp.route('/projects')
@login_required
def _projects():
    user = g.user
    projects = get_all_projects()
    return render_template('projects.html', title='Projects', user=user,
                           projects=projects)


@myapp.route('/projects/add', methods=['GET', 'POST'])
@login_required
def _projects_add():
    user = g.user
    AddProjectForm = make_add_project_form(user)
    form = AddProjectForm()
    if form.validate_on_submit():
        error = add_project(form, user)
        if not error:
            message = 'Project successfully added!'
            logger.debug(message)
            flash(message)
            return redirect('/projects')
        else:
            message = 'Could not create project: {}'.format(error)
            logger.error(message)
            flash(message)
    if form.errors:
        logger.error(form.errors)
    return render_template('projects_add.html', title='Add Project', user=user,
                           form=form)


@myapp.route('/projects/delete', methods=['GET', 'POST'])
@login_required
def _projects_delete():
    user = g.user
    project_id = request.get_json().get('project_id')
    project = models.Projects.query.filter_by(id=project_id).first()
    if user != project.owner:
        return 'You do not own this project!'
    return delete_project(project, user)


@myapp.route('/projects/<id_>')
@login_required
def _projects_id(id_):
    user = g.user
    project = get_project_by_id(id_)
    return render_template('project_id.html', title='Projects', user=user,
                           project=project)


@myapp.route('/projects/<id_>/edit')
@login_required
def _projects_id_edit(id_):
    user = g.user
    project = get_project_by_id(id_)
    return render_template('project_id_edit.html', title='Edit Project',
                           user=user, project=project)


@myapp.route('/projects/<id_>/add_member', methods=['GET', 'POST'])
@login_required
def _projects_id_add_member(id_):
    user = g.user
    project = get_project_by_id(id_)
    AddProjectMemberForm = make_add_project_member_form(project)
    form = AddProjectMemberForm()
    if not user == project.owner:
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
    member = models.Users.query.filter_by(id=member_id).first()
    user = g.user
    project = get_project_by_id(id_)
    if not user == project.owner:
        return 'You are not the owner of this project!'
    message = remove_project_member(user=user, project=project, member=member)
    return message


@myapp.route('/projects/<id_>/add_server', methods=['GET', 'POST'])
@login_required
def _projects_id_add_server(id_):
    user = g.user
    project = get_project_by_id(id_)
    if not user == project.owner:
        flash('You are not the owner of this project!')
        return redirect('/projects/{}'.format(id_))
    return render_template('project_id_add_server.html', title='Projects',
                           user=user, project=project)


@myapp.route('/projects/<id_>/add_status', methods=['GET', 'POST'])
@login_required
def _projects_id_add_status(id_):
    user = g.user
    project = get_project_by_id(id_)
    form = AddProjectStatusForm()
    if not user == project.owner:
        flash('You are not the owner of this project!')
        return redirect('/projects/{}'.format(id_))
    if form.validate_on_submit():
        message = add_project_status(form=form, user=user,
                                     project_id=project.id)
        flash(message)
        return redirect('/projects/{}'.format(id_))
    return render_template('project_id_add_status.html', title='Add Status',
                           user=user, project=project, form=form)


@myapp.route('/projects/<id_>/remove_status', methods=['GET', 'POST'])
@login_required
def _projects_id_remove_status(id_):
    status_id = request.get_json().get('status_id')
    status = models.Users.query.filter_by(id=status_id).first()
    user = g.user
    project = get_project_by_id(id_)
    if not user == project.owner:
        return 'You are not the owner of this project!'
    message = remove_project_status(user=user, project=project, status=status)
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
    user = g.user
    form = CreateJobForm()
    build_form = BuildStepForm()
    servers = models.Servers.query
    if form.validate_on_submit():
        make_jenkins_job(form)
        flash('Created job {}'.format(form.job_name.data))
        return redirect('/jenkins_jobs')
    elif request.method == 'POST':
        flash("Invalid entries.")
    return render_template('create_jenkins_job.html', title='Create Job',
                           date=_get_date_last_modified(),
                           form=form,
                           build_form=build_form,
                           user=user, servers=servers)


@myapp.route('/jenkins_jobs', methods=['GET', 'POST'])
@login_required
def _jenkins_jobs():
    user = g.user
    try:
        jobs = get_all_jenkins_info()
    except JenkinsException:
        return render_template('500.html'), 500
    return render_template('jenkins_jobs.html', title='Jenkins Jobs',
                           date=_get_date_last_modified(),
                           jobs=get_all_jenkins_info(),
                           result=lambda x: get_last_jenkins_result(x),
                           user=user)


@myapp.route('/jenkins_jobs/<jobname>')
@login_required
def _jenkins_job_info(jobname):
    user = g.user
    job_info = get_jenkins_job_info(jobname)
    if job_info:
        return render_template('jenkins_job_info.html',
                               title='Job Info',
                               date=_get_date_last_modified(),
                               job_info=job_info,
                               user=user)
    return redirect('/jenkins_jobs')


# _______________________________ ADMIN _______________________________
@myapp.route('/admin', methods=['GET', 'POST'])
@login_required
def _admin():
    user = g.user
    if not user.admin:
        print 'not admin'
        abort(401)
    users = models.Users.query.order_by('email').all()
    groups = models.Groups.query.order_by('id').all()

    return render_template('admin.html', title='Admin', user=user,
                           groups=groups, users=users,
                           date=_get_date_last_modified())


@myapp.route('/admin/group/add', methods=['GET', 'POST'])
@login_required
def _admin_group_add():
    user = g.user
    if not user.admin:
        print 'not admin'
        abort(401)
    form = AddGroupForm()
    if form.validate_on_submit():
        flash(add_group(form, user))
        return redirect('/admin')

    return render_template('admin_group_add.html', title='Admin', user=user,
                           form=form, date=_get_date_last_modified())


@myapp.route('/admin/groups/delete', methods=['GET', 'POST'])
@login_required
def _delete_group():
    gid = request.get_json().get('gid')
    user = g.user
    if not user.admin:
        print 'not admin'
        abort(401)
    message = delete_group(gid, user)
    flash(message)
    logger.debug(message)

    return JSONEncoder().encode({'success': 1})


@myapp.route('/admin/user/add', methods=['GET', 'POST'])
@login_required
def _admin_user_add():
    user = g.user
    if not user.admin:
        print 'not admin'
        abort(401)
    form = AddUserForm()
    if form.validate_on_submit():
        flash(add_user(form, user))
        return redirect('/admin')

    return render_template('admin_user_add.html', title='Admin', user=user,
                           form=form, date=_get_date_last_modified())


@myapp.route('/admin/users/delete', methods=['GET', 'POST'])
@login_required
def _delete_user():
    user_name = request.get_json().get('user_name')
    user = g.user
    if not user.admin:
        print 'not admin'
        abort(401)
    logger.debug(delete_user(user_name, user))

    return JSONEncoder().encode({'success': 1})


@myapp.route('/admin/users/<user_name>', methods=['GET', 'POST'])
@login_required
def _user_info(user_name):
    user = g.user
    if not user.admin:
        print 'not admin'
        abort(401)
    other_user = models.Users.query.filter_by(user_name=user_name).first()
    if not (user.admin and user):
        return render_template('404.html', user=user), 404

    return render_template('admin_users_info.html', title='User Info', user=user,
                           date=_get_date_last_modified(),
                           other_user=other_user)


@myapp.route('/admin/users/<user_name>/edit', methods=['GET', 'POST'])
@login_required
def _edit_user_info(user_name):
    user = g.user
    if not user.admin:
        abort(401)
    other_user = models.Users.query.filter_by(user_name=user_name).first()
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

    return render_template('admin_users_edit.html', title='Edit User Info', user=user,
                           date=_get_date_last_modified(), form=form)


@myapp.route('/admin/groups/<_id>', methods=['GET', 'POST'])
@login_required
def _groups_info(_id):
    user = g.user
    group = models.Groups.query.filter_by(id=_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    return render_template('admin_groups_info.html', title='Group Info',
                           user=user, group=group,
                           date=_get_date_last_modified())


@myapp.route('/admin/groups/<_id>/edit', methods=['GET', 'POST'])
@login_required
def _groups_info_edit(_id):
    user = g.user
    form = EditGroupForm()
    group = models.Groups.query.filter_by(id=_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    if form.validate_on_submit():
        message = update_group_info(form, group.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.id))

    for attr in group.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(group, attr)

    return render_template('admin_groups_edit.html', title='Edit Group Info',
                           user=user, group=group, form=form,
                           date=_get_date_last_modified())


@myapp.route('/admin/groups/<_id>/add_member', methods=['GET', 'POST'])
@login_required
def _groups_add_member(_id):
    user = g.user
    group = models.Groups.query.filter_by(id=_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    AddGroupMemberForm = make_add_group_member_form(_id)
    form = AddGroupMemberForm()

    if form.validate_on_submit():
        message = add_group_member(form, group.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.id))

    return render_template('admin_groups_add_member.html',
                           title='Add Group Member',
                           user=user, group=group, form=form,
                           date=_get_date_last_modified())


@myapp.route('/admin/groups/<gid>/remove_member', methods=['GET', 'POST'])
@login_required
def _groups_remove_member(gid):
    user = g.user
    group = models.Groups.query.filter_by(id=gid).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    RemoveGroupMemberForm = make_remove_group_member_form(gid)
    form = RemoveGroupMemberForm()

    if form.validate_on_submit():
        message = remove_group_member(group.id, form.member.data.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.id))

    return render_template('admin_groups_remove_member.html',
                           title='Remove Group Member',
                           user=user, group=group, form=form,
                           date=_get_date_last_modified())


@myapp.route('/admin/groups/<gid>/remove_server', methods=['GET', 'POST'])
@login_required
def _groups_remove_server(gid):
    user = g.user
    group = models.Groups.query.filter_by(id=gid).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    RemoveGroupServerForm = make_remove_group_server_form(gid)
    form = RemoveGroupServerForm()

    if form.validate_on_submit():
        message = remove_group_server(group.id, form.server.data.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.id))

    return render_template('admin_groups_remove_server.html',
                           title='Remove Group Server',
                           user=user, group=group, form=form,
                           date=_get_date_last_modified())


@myapp.route('/admin/groups/<_id>/add_server', methods=['GET', 'POST'])
@login_required
def _groups_add_server(_id):
    user = g.user
    group = models.Groups.query.filter_by(id=_id).first()
    if not (user.admin and group):
        return render_template('404.html', user=user), 404

    AddGroupServerForm = make_add_group_server_form(_id)
    form = AddGroupServerForm()

    if form.validate_on_submit():
        message = add_group_server(form, group.id, user)
        flash(message)
        logger.debug(message)
        return redirect('/admin/groups/{}'.format(group.id))

    for attr in group.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(group, attr)

    return render_template('admin_groups_add_server.html',
                           title='Add Group Server',
                           user=user, group=group, form=form,
                           date=_get_date_last_modified())


@myapp.route('/debug', methods=['GET'])
@login_required
def _debug():
    p = Process(target=_run_debug, args=[])
    p.start()
    return redirect(url_for('_last_debug'))


@myapp.route('/last_debug', methods=['GET'])
@login_required
def _last_debug():
    user = g.user
    return render_template('last_debug.html', title='Debug', user=user,
                           date=_get_date_last_modified())


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
    user = g.user
    with open('last_debug.out', 'r') as f:
        text = f.read()
    if text:
        return render_template('last_debug_out.html', title='Debug', user=user,
                               date=_get_date_last_modified(), text=text)
    flash('Could not get last debug output.')
    return redirect(url_for('_last_debug'))


# ______________________________ HANDLERS _____________________________
@myapp.errorhandler(401)
def unauthorized_error(error):
    user = g.user
    return render_template('401.html', user=user), 401


@myapp.errorhandler(404)
def not_found_error(error):
    user = g.user
    return render_template('404.html', user=user), 404


@myapp.errorhandler(500)
def internal_error(error):
    user = g.user
    db.session.rollback()
    return render_template('500.html', user=user), 500

if __name__ == '__main__':
    logger = customlogger.create_logger('views')
    main()
else:
    logger = customlogger.get_logger(__name__)
