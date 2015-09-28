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
