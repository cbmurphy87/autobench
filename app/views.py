#!/usr/bin/python

# ___________________________ Flask Imports ________________________
from flask import render_template, flash, redirect, session, url_for, request, \
    g, abort, send_from_directory
from flask.ext.login import login_user, logout_user, current_user, \
    login_required
from sqlalchemy import sql, or_

# ___________________________ App Imports ________________________
from app import myapp, lm
from app.forms import CreateJobForm, LoginForm, BuildStepForm, \
    AddInventoryForm, DeployForm, EditInfoForm
from models import Users, Servers

# ___________________________ Standard Imports ________________________
from datetime import datetime
import fnmatch
from jenkins import JenkinsException
from json import JSONEncoder
from multiprocessing import Process
import os
from subprocess import Popen, PIPE

# ___________________________ AAEBench Imports ________________________
from aaebench.testautomation.syscontrol.file_transfer import SFTPManager
from aaebench.testautomation.syscontrol.racadm import RacadmManager
from aaebench.parents.managers import GenericManager

# ___________________________ Flask Imports ________________________
from scripts.jenkinsMethods import *
from scripts.db_actions import *


# ========================== METHODS ============================

# _______________________ HELPER METHODS ________________________
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


# ___________________ Asynchronous METHODS ______________________
# method for creating a separate process
def _deploy_server(form):

    message = 'Deploying {} {} to {} with ks {}.'.format(form.os.data.flavor,
                                                         form.os.data.version,
                                                         form.target.data.id,
                                                         form.os.data.append)
    print message

    pxe_file = render_template('pxeboot',
                               kernel=form.os.data.kernel,
                               initrd=form.os.data.initrd,
                               append=form.os.data.append)

    # gather data
    server = form.target.data
    interfaces = server.interfaces
    interface = interfaces.filter_by(name='NIC.1').first()
    eth0 = interface.mac.lower().replace(':', '-')
    drac_ip = interfaces.filter_by(name='DRAC').first().ip
    print 'iDRAC ip address is: {}'.format(drac_ip)

    # send unique config file to pxe server
    sftp = SFTPManager('pxe.aae.lcl')
    client = sftp.create_sftp_client()
    filename = '/tftpboot/pxelinux.cfg/01-{}'.format(eth0)

    with client.open(filename, 'w') as f:
        f.write(pxe_file)

    salt_master_manager = GenericManager(hostname='salt-gru.aae.lcl',
                                         username='salt',
                                         password='Not24Get',
                                         local=False,
                                         ending='$')
    command = ['salt-key', '-d', server.id, '-y']
    salt_master_manager.connection.exec_command(command)
    salt_master_manager.close()

    # reboot server to PXE
    racadm = RacadmManager(drac_ip)
    racadm.boot_once('PXE')

    # make server unavailable
    try:
        user = g.user
        server = models.Servers.query.filter_by(id=server.id).first()
        server.available = False
        server.held_by = user.id
        db.session.commit()
        print 'Server {} now unavailable.'.format(server)
    except Exception as e:
        print 'Error making server unavailable: {}'.format(e)
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


# ________________________ LOGIN METHODS ________________________
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


# =========================== LOGIN VIEWS =============================
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
            print 'Error fetching user: {}'.format(e)
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


# =========================== REGULAR VIEWS ===========================
@myapp.route('/')
@login_required
def _root():
    user = g.user
    return render_template('index.html',
                           title='Home',
                           date=_get_date_last_modified(),
                           user=user)


@myapp.route('/script')
@login_required
def _script():
    print 'HI!'
    print 'args:'
    for k, v in request.args.items():
        print '  ->{}: {}'.format(k, v)
    return 'Hello'


@myapp.route('/my_info')
@login_required
def _my_info():
    user = g.user
    return render_template('my_info.html',
                           title='About Me',
                           date=_get_date_last_modified(),
                           user=user)


@myapp.route('/my_info/edit', methods=['GET', 'POST'])
@login_required
def _edit_my_info():
    user = g.user
    form = EditInfoForm()
    if form.validate_on_submit():
        if user.check_password(str(form.password.data)):
            message = update_user_info(form, user)
            flash(message)
            print message
            return redirect(url_for('_my_info'))
        else:
            flash('Invalid password. Try again.')
    print form.errors

    for attr in user.__dict__.keys():
        if attr in form.data.keys():
            field = getattr(form, attr)
            field.data = getattr(user, attr)

    return render_template('edit_my_info.html',
                           title='Edit About Me',
                           date=_get_date_last_modified(),
                           user=user, form=form)


# _______________________ INFO _________________________
# methods used to get inventory info
@myapp.route('/server_info', methods=['POST'])
@login_required
def _server_info():
    server_id = request.get_json().get('id')
    return render_template('server_info.html',
                           server=models.Servers.query
                           .filter_by(id=server_id).first())


# _______________________ INVENTORY ________________________
@myapp.route('/inventory')
@login_required
def _inventory():
    user = g.user
    servers = get_inventory()
    # count server fields

    return render_template('inventory.html', title='Inventory',
                           date=_get_date_last_modified(),
                           user=user, servers=servers)


@myapp.route('/inventory/add', methods=['GET', 'POST'])
@login_required
def _add_inventory():
    user = g.user
    form = AddInventoryForm()
    if form.validate_on_submit():
        flash('Adding server. Wait 30 seconds, then refresh.')
        p = Process(target=add_inventory, args=(form, user))
        p.start()
        return redirect('/inventory')

    return render_template('add_inventory.html', title='Add Inventory',
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


@myapp.route('/inventory/update', methods=['GET', 'POST'])
@login_required
def _update_inventory():
    _id = request.get_json().get('id')
    try:
        server = Servers.query.filter_by(id=_id).first()
        mac = server.interfaces.filter_by(type='oob').first().mac
        flash('Updating server. Wait 30 seconds, then refresh.')
        p = Process(target=update_inventory, args=(mac,))
        p.start()
    except Exception:
        print 'Could not update server {}.'.format(server.id)
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
    print 'User {} checking out {}'.format(user, _id)
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
        server_json = JSONEncoder().encode({'available': server.available,
                                            'i_am_holder': i_am_holder,
                                            'title': title,
                                            'color': color})
        return server_json
    except Exception as e:
        print "Couldn't encode server: {}".format(e)
    return JSONEncoder().encode({'available': False,
                                 'i_am_holder': False,
                                 'held_by': 'unknown',
                                 'title': 'Server state is unknown',
                                 'color': 'red'})


@myapp.route('/inventory/delete', methods=['GET', 'POST'])
@login_required
def _delete_id():
    _id = request.get_json().get('id')
    _next = request.get_json().get('next')
    user = g.user
    print 'User {} is deleting server {}'.format(user, _id)
    server = Servers.query.filter_by(id=_id).first()
    drives = server.drives
    print drives.all()
    try:
        for drive in drives:
            db.session.delete(drive)
        db.session.commit()
        db.session.delete(server)
        db.session.commit()
        print 'Server successfully delted.'
    except Exception as e:
        print 'Error deleting server {}: {}'.format(_id, e)
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
    print 'User {} releasing {}'.format(user, _id)
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
        i_am_holder = False

        server_json = JSONEncoder().encode({'available': server.available,
                                            'i_am_holder': i_am_holder,
                                            'title': title,
                                            'color': color})
        return server_json
    except:
        print 'Could not get user holding server.'
    if _next:
        return redirect(_next)
    print 'Error releasing server. Server may be in unknown state.'
    return JSONEncoder().encode({'available': server.available,
                                 'i_am_holder': False,
                                 'title': 'Error getting status'})


# _______________________ Deploy ________________________
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


# _______________________ JOBS ________________________
@myapp.route('/build_job/<job_name>', methods=['POST', 'GET'])
@login_required
def _build_job(job_name):
    print 'Building job {}!'.format(job_name)
    status = build_job(job_name)
    flash(status)
    return redirect('/jobs')


@myapp.route('/create_job', methods=['GET', 'POST'])
@login_required
def _create_job():
    user = g.user
    form = CreateJobForm()
    build_form = BuildStepForm()
    servers = models.Servers.query
    if form.validate_on_submit():
        make_job(form)
        flash('Created job {}'.format(form.job_name.data))
        return redirect('/jobs')
    elif request.method == 'POST':
        flash("Invalid entries.")
    return render_template('create_job.html', title='Create Job',
                           date=_get_date_last_modified(),
                           form=form,
                           build_form=build_form,
                           user=user, servers=servers)


@myapp.route('/jobs', methods=['GET', 'POST'])
@login_required
def _jobs():
    user = g.user
    try:
        jobs = get_all_info()
    except JenkinsException:
        return render_template('500.html'), 500
    return render_template('jobs.html', title='Jobs',
                           date=_get_date_last_modified(),
                           jobs=get_all_info(),
                           result=lambda x: get_last_result(x),
                           user=user)


@myapp.route('/jobs/<jobname>')
@login_required
def _job_info(jobname):
    user = g.user
    job_info = get_jenkins_job_info(jobname)
    if job_info:
        return render_template('job_info.html',
                               title='Job Info',
                               date=_get_date_last_modified(),
                               job_info=job_info,
                               user=user)
    return redirect('/jobs')


# ________________________ Debug __________________________
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


# _______________________ Handlers ________________________
@myapp.errorhandler(404)
def not_found_error(error):
    user = g.user
    return render_template('404.html', user=user), 404


@myapp.errorhandler(500)
def internal_error(error):
    user = g.user
    db.session.rollback()
    return render_template('500.html', user=user), 500
