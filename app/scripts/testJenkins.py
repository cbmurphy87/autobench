#!/usr/bin/python

import sys
import jenkins

def make_butler():
  jenkins_url = 'http://jenkins.aae.lcl:8080'
  butler = jenkins.Jenkins(jenkins_url) #, 'root', 'Not24Get')
  return butler

def make_job(build):
  butler = make_butler()
  with open('/root/aaetest/app/configs/testsaltconfig.xml', 'r') as f:
    d = {'target':target}
    config_file = f.read()
    config_file = config_file.format(**d)
  try:
    butler.create_job(name, config_file)
  except:
    print "Job already created: skipping creation."
  finally:
    if build:
      print "Running job {}.".format(name)
      print name, type(name)
      butler.build_job(str(name))

def main():
  make_job(sys.argv[1])

if __name__ == '__main__':
  main()
