#!/usr/bin/python

from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from sqlalchemy.orm.exc import NoResultFound
from app import app, lm, db
from app.forms import CreateJobForm, LoginForm, BuildStepForm, AddInventoryForm, DeployForm
from models import Users, Servers, StorageDevices, ServerStorage, ServerCommunication
from datetime import datetime
import os
import fnmatch
from scripts.jenkinsMethods import *
from scripts.db_actions import *
from multiprocessing import Process
from jenkins import JenkinsException
from aaebench.testautomation.syscontrol.file_transfer import SFTPManager
from aaebench.testautomation.syscontrol.racadm import RacadmManager


# ============================ HELPER METHODS =============================


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


# ============================ LOGIN METHODS ==============================


@lm.user_loader
def load_user(id):
    return Users.query.get(id)


def unauthorized():
    return redirect('/login')


@app.before_request
def _before_request():
    try:

        g.user = current_user
    except:
        return render_template('500.html'), 500


# ============================= LOGIN VIEWS ================================


@app.route('/login', methods=['GET', 'POST'])
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
            if str(form.password.data) == 'Not24Get':
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
    return render_template('login.html',
                           title='Login',
                           date=_get_date_last_modified(),
                           form=form)


@app.route('/logout')
def _logout():
    logout_user()
    flash('You have been logged out.')
    return redirect('/login')


# ============================= REGULAR VIEWS ===============================


@app.route('/')
@login_required
def _root():
    user = g.user
    return render_template('index.html',
                           title='Home',
                           date=_get_date_last_modified(),
                           user=user)


@app.route('/script')
def _script():
    print 'HI!'
    print 'args:'
    for k, v in request.args.items():
        print '  ->{}: {}'.format(k, v)
    return 'Hello'


# _______________________ INFO _________________________
# methods used to get inventory info
@app.route('/server_info', methods=['POST'])
def _server_info():
    server_id = request.get_json().get('id')
    return render_template('server_info.html',
                           server=models.Servers.query
                           .filter_by(id=server_id).first())


# _______________________ INVENTORY ________________________
@app.route('/inventory')
@login_required
def _inventory():
    user = g.user
    servers = get_inventory()
    return render_template('inventory.html', title='Inventory',
                           date=_get_date_last_modified(),
                           user=user, servers=servers)


@app.route('/inventory/add', methods=['GET', 'POST'])
@login_required
def _add_inventory():
    user = g.user
    add_form = AddInventoryForm()
    if add_form.validate_on_submit():
        flash('Adding server. Wait 30 seconds, then refresh.')
        p = Process(target=add_inventory, args=(add_form,))
        p.start()
        return redirect('/inventory')

    return render_template('add_inventory.html', title='Add Inventory',
                           date=_get_date_last_modified(), user=user,
                           add_inventory_form=add_form)


@app.route('/inventory/<_id>')
@login_required
def _inventory_id(_id):
    user = g.user
    server = Servers.query.get(_id)
    return render_template('inventory_id.html', title=_id, server=server,
                           date=_get_date_last_modified(), user=user)


@app.route('/inventory/update/<mac>', methods=['GET', 'POST'])
@login_required
def _update_inventory(mac):
    flash('Updating server. Wait 30 seconds, then refresh.')
    p = Process(target=update_inventory, args=(mac,))
    p.start()
    return redirect('inventory')


# _______________________ Deploy ________________________
# helper method for creating a separate process
def _deploy_server(form):

    print 'Deploying {} {} to {}!'.format(form.os.data.flavor,
                                       form.os.data.version,
                                       form.target.data.id)

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
    with client.open('/tftpboot/pxelinux.cfg/01-{}'.format(eth0), 'w') \
            as f:
        f.write(pxe_file)

    # reboot server to PXE
    racadm = RacadmManager(drac_ip)
    racadm.boot_once('PXE')

    # make server unavailable
    try:
        server = models.Servers.query.filter_by(id=server.id).first()
        server.available = False
        db.session.commit()
        print 'Server {} now unavailable.'.format(server)
    except Exception as e:
        print 'Error making server unavailable: {}'.format(e)
        db.session.rollback()


@app.route('/deploy', methods=['GET', 'POST'])
@login_required
def _deploy():
    user = g.user
    form = DeployForm()
    servers = models.Servers.query
    if form.validate_on_submit():

        # start subprocess to deploy system
        p = Process(target=_deploy_server, args=(form,))
        p.start()

        return redirect(url_for('_jobs'))
    return render_template('deploy.html', title='Tests',
                           date=_get_date_last_modified(),
                           user=user, form=form, servers=servers)


# _______________________ JOBS ________________________
@app.route('/build_job/<job_name>', methods=['POST', 'GET'])
@login_required
def _build_job(job_name):
    print 'Building job {}!'.format(job_name)
    status = build_job(job_name)
    flash(status)
    return redirect('/jobs')


@app.route('/create_job', methods=['GET', 'POST'])
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


@app.route('/jobs', methods=['GET', 'POST'])
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


@app.route('/jobs/<jobname>')
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


# _______________________ ERRORS ________________________
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
