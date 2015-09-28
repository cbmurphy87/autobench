#!/usr/bin/python

from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from sqlalchemy.orm.exc import NoResultFound
from app import app, lm, db
from app.forms import CreateForm, LoginForm, BuildStepForm, AddInventoryForm
from models import Users, Servers, StorageDevices, ServerStorage, ServerCommunication
from datetime import datetime
import os
import fnmatch
from scripts.jenkinsMethods import *
from scripts.db_actions import add_inventory


# ============================ HELPER METHODS =============================


def get_date_last_modified():
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
def before_request():
    g.user = current_user


# ============================= LOGIN VIEWS ================================


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    # validate login credentials
    if form.validate_on_submit():
        try:
            # get user from db
            user = Users.query.filter_by(email=str(form.email.data)).first()
        except NoResultFound:
            user = None
            flash('Invalid e-mail. Try again.')
        # if valid user
        if user:
            # check password
            if str(form.password.data) == 'Not24Get':
                user.is_authenticated = True
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                flash('Logged in successfully.')
                return redirect(url_for('index'))
            else:
                flash('Wrong password. Try again.')
    return render_template('login.html',
                           title='Login',
                           date=get_date_last_modified(),
                           form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect('/login')


# ============================= REGULAR VIEWS ===============================


@app.route('/')
@login_required
def root():
    user = g.user
    session.permanent = True
    return render_template('index.html',
                           title='Home',
                           date=get_date_last_modified(),
                           user=user)


# _______________________ INDEX ________________________
@app.route('/index')
@login_required
def index():
    user = g.user
    session.permanent = True
    return render_template('index.html',
                           title='Home',
                           date=get_date_last_modified(),
                           user=user)


# _______________________ INVENTORY ________________________
@app.route('/inventory')
@login_required
def inventory_route():
    user = g.user
    servers = Servers.query.all()
    return render_template('inventory.html', title='Inventory',
                           date=get_date_last_modified(),
                           user=user, servers=servers)


@app.route('/inventory/add', methods=['GET', 'POST'])
def add_inventory_route():
    user = g.user
    add_form = AddInventoryForm()
    if add_form.validate_on_submit():
        print 'Form is valid'
        failed = add_inventory(add_form)
        if not failed:
            print 'Successful'
            flash('Successfully added hardware.')
            return redirect('/inventory')
        else:
            print 'Failed'
            flash('Could not add hardware. Try again.')
    return render_template('add_inventory.html', title='Add Inventory',
                           date=get_date_last_modified(), user=user,
                           add_inventory_form=add_form)


# _______________________ TESTS ________________________
@app.route('/tests')
@login_required
def tests_route():
    user = g.user
    return render_template('tests.html', title='Tests',
                           date=get_date_last_modified(),
                           user=user)


# _______________________ JOBS ________________________
@app.route('/testpost/<job_name>', methods=['POST', 'GET'])
@login_required
def testpost_route(job_name):
    print 'Building job {}!'.format(job_name)
    status = build_job(job_name)
    flash(status)
    return redirect('/jobs')


@app.route('/create_job', methods=['GET', 'POST'])
@login_required
def create_job_route():
    user = g.user
    create_form = CreateForm()
    build_form = BuildStepForm()
    if create_form.validate_on_submit():
        make_job(create_form)
        flash('Created job {}'.format(create_form.job_name.data))
        return redirect('/jobs')
    elif request.method == 'POST':
        flash("Invalid entries.")
    return render_template('create_job.html', title='Create Job',
                           date=get_date_last_modified(),
                           create_form=create_form,
                           build_form=build_form,
                           user=user)


@app.route('/jobs', methods=['GET', 'POST'])
@login_required
def jobs_route():
    user = g.user
    return render_template('jobs.html', title='Jobs',
                           date=get_date_last_modified(),
                           jobs=get_all_info(),
                           result=lambda x: get_last_result(x),
                           user=user)


@app.route('/jobs/<jobname>')
@login_required
def job_info_route(jobname):
    user = g.user
    job_info = get_jenkins_job_info(jobname)
    if job_info:
        return render_template('job_info.html',
                               title='Job Info',
                               date=get_date_last_modified(),
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
