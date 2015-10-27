#!/usr/bin/python

import sys
import jenkins
from flask import render_template


def make_butler():
    jenkins_url = 'http://jenkins.aae.lcl:8080'
    butler = jenkins.Jenkins(jenkins_url)
    return butler


def get_jenkins_job_names():
    butler = make_butler()
    job_list = []
    for job in butler.get_jobs():
        this_job = butler.get_job_info(job.get('name'))
        job_list.append(this_job['name'])
    return job_list


def get_jenkins_jobs_and_last_build():
    butler = make_butler()
    jobs = butler.get_jobs()
    build_list = []
    if jobs:
        for job in jobs:
            job_info = butler.get_job_info(job.get('name'))
            if job_info.get('color').lower() == 'blue':
                status = 'Success'
            elif job_info.get('color').lower() == 'red':
                status = 'Failed'
            else:
                status = 'Not Built'
            build_list.append((job_info['name'], status))
        return build_list
    else:
        return 'N/A', 'Not built'


def get_jenkins_job_by_name(name):
    butler = make_butler()
    return butler.get_job_name(name)


def get_jenkins_job_info(name):
    butler = make_butler()
    try:
        info = butler.get_job_info(name)
    except jenkins.NotFoundException:
        return None
    return info


def get_all_info():
    jobs = get_jenkins_job_names()
    job_list = []
    for job in jobs:
        job_list.append(get_jenkins_job_info(job))
    return job_list


def get_last_result(job_name):
    butler = make_butler()
    if not butler.get_job_name(job_name) == job_name:
        return 'None'
    job = butler.get_job_info(job_name)
    try:
        job_number = job['lastCompletedBuild']['number']
    except:
        return 'Not built'
    return butler.get_job_info(job_name, job_number)['lastCompletedBuild'][
        'result']


def make_job(create_form):
    butler = make_butler()
    config_file = render_template('configs/config.xml',
                                  builders=[create_form])

    # do we need to encode?
    # config_file = config_file.encode('latin-1')

    # try to create job
    try:
        butler.create_job(create_form.job_name.data, config_file)
    except Exception as e:
        print 'Exception: {}'.format(e)
        if butler.job_exists(create_form.job_name.data):
            print "Job {} already created: skipping creation."\
                .format(create_form.job_name.data)
        else:
            print "Could not create job. Exiting."
            return

    # build job if it created
    if create_form.build.data:
        if not butler.job_exists(create_form.job_name.data):
            print 'Job not created!'
            return
        print "Running job {}.".format(create_form.job_name.data)
        print str(create_form.job_name.data)
        build_job(create_form.job_name.data)


def get_running_builds():
    butler = make_butler()
    try:
        return butler.get_running_builds()
    except:
        print 'The function "get_running_builds()" is broken'


def build_job(job_name):
    butler = make_butler()
    if butler.job_exists(job_name):
        butler.build_job(job_name)
        return "Built job {}".format(job_name)
    else:
        return "No job by the name {}".format(job_name)


def delete_job(job_name):

    butler = make_butler()
    try:
        butler.delete_job(job_name)
    except Exception as e:
        print 'Failed to delete job {}: {}'.format(job_name, e)


def main():
    delete_job("I'm Hungry.")


if __name__ == '__main__':
    main()
