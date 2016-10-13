#!/usr/bin/python

import sys
import jenkins

def make_butler():
  jenkins_url = 'http://jenkins.aae.lcl:8080'
  butler = jenkins.Jenkins(jenkins_url)
  return butler

def get_jenkins_job_names():
  butler = make_butler()
  jobs = butler.get_jobs()
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
    return ('N/A', 'Not built')

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
  return butler.get_job_info(job_name, job_number)['lastCompletedBuild']['result']

def main():
  print get_last_result('testsalt2')

def rec(obj, spaces=0):
  if spaces == 0:
    print '-' * 70
  if type(obj) is dict:
    sys.stdout.write('\033[92m{}{{\n\033[0m'.format('  ' * spaces))
    for k, v in obj.items():
      sys.stdout.write('\033[91m{}{}: \033[0m'.format('  ' * spaces, k))
      if type(v) is not dict and not hasattr(v, '__iter__'):
        sys.stdout.write('\033[93m{}\n\033[0m'.format(v.encode('utf-8') if type(v) in (unicode, str) else v))
      else:
        sys.stdout.write('\n')
        rec(v, spaces + 1)
    sys.stdout.write('\033[92m{}}}\n\033[0m'.format('  ' * spaces))
  elif hasattr(obj, '__iter__'):
    sys.stdout.write('\033[95m{}[\033[0m'.format('  ' * spaces))
    if len(obj) >= 1:
      sys.stdout.write('\n')
      for o in obj:
        rec(o, spaces + 1)
    sys.stdout.write('\033[95m{}]\n\033[0m'.format('  ' * spaces if len(obj) else ''))
  else:
    sys.stdout.write('\033[93m{}{}\n\033[0m'.format('  ' * spaces, obj.encode('utf-8') if type(obj) in (unicode, str) else obj))

if __name__ == '__main__':
  main()
