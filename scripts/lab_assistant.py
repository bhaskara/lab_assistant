#!/usr/bin/env python

import sys
import yaml
import math
import os
import optparse
from os import path
import re
import time
import subprocess
from sys import stderr
import shutil as sh

def alist_to_dict(l):
    d = {}
    for x, y in l:
        d[x] = y
    return d

def param_range(r):
    if isinstance(r, list):
        return r
    elif isinstance(r, dict):
        a = r.get('min', 0)
        b = r['max']
        c = r.get('step', 1)
        return [a+c*i for i in range(1+int((b-a)/c)) if a+c*i<=b]
    else:
        return [r]

def param_combinations(ranges, i=0):
    if i==len(ranges):
        return [[]]
    k = ranges[i][0]
    vals = ranges[i][1]
    return [c + [(k, v)] for c in param_combinations(ranges, i+1) for v in vals]

def make_invocation(executable, params):
    return [executable] + ["--{0}={1}".format(k, v) for k, v in params.iteritems()]

def param_settings(config):
    ranges = [(name, param_range(val)) for name, val in config['params'].iteritems()]
    return map(alist_to_dict, param_combinations(ranges))

def make_name(n):
    m = re.match('(.*)\.', n)
    if m:
        return m.group(1)
    else:
        return n

def get_time_stamp():
    return time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())

def get_variable_params(config):
    l = [name for name, val in config['params'].iteritems() if\
         isinstance(val, list) or isinstance(val, dict)]
    l.sort()
    return l

def run_name(s, params):
    return '_'.join(str(s[p]) for p in params)

def setup_dirs(d, config_str):
    par = path.dirname(d)
    os.makedirs(d)
    latest = os.path.join(par, 'latest')
    if path.exists(latest):
        os.remove(latest)
    os.symlink(d, os.path.join(par, 'latest'))
    with open(path.join(d, 'config.yaml'), 'w') as f:
        f.write(config_str)

def main():
    parser = optparse.OptionParser()
    parser.add_option('-l', '--log_dir', default=os.getenv('LAB_ASSISTANT_LOG_DIR', '.'))
    options, args = parser.parse_args()
    
    if len(args)<1:
        print "Usage: {0} CONFIG_FILE".format(sys.argv[0])
        return 1

    with open(args[0]) as f:
        config_str = f.read()
    config = yaml.load(config_str)

    name = config.get('name', make_name(args[0]))
    stamp = get_time_stamp()
    outdir = path.join(options.log_dir, name, stamp)
    stderr.write("Output dir is {0}\n".format(outdir))

    if os.path.exists(outdir):
        print "Directory {0} already exists".format(outdir)
        return 1

    setup_dirs(outdir, config_str)
    with open(path.join(outdir, 'run_info.yaml'), 'w') as f:
        settings = param_settings(config)
        variable_params = get_variable_params(config)
        executable = path.abspath(path.join(path.dirname(args[0]),
                                            config['executable']))
        f.write("executable: {0}\n".format(executable))

        for s in settings:
            d = os.path.join(outdir, run_name(s, variable_params))
            os.mkdir(d)
            with open(os.path.join(d, 'out.log'), 'w') as outfile:
                with open(os.path.join(d, 'err.log'), 'w') as errfile:
                    args = make_invocation(executable, s)
                    stderr.write("Running with args {0}... ".format(s))
                    subprocess.check_call(args, stdout=outfile, stderr=errfile)
                    stderr.write("done\n")

        f.write("completed: true\n")

        
                
    
if __name__ == '__main__':
    sys.exit(main())
