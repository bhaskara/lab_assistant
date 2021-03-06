import optparse
import yaml
import math
import os
from os import path
import re
import time
import subprocess as sp
from sys import stderr
import shutil as sh


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

def make_invocation(executable, params, outdir, file_params):
    p1 = ["--{0}={1}".format(k, v) for k, v in params.iteritems()]
    p2 = ["--{0}={1}".format(k, path.join(outdir, v)) for
          k, v in file_params.iteritems()]
    return [executable] + p1 + p2

def is_file_param(v):
    return isinstance(v, dict) and 'relative_path' in v

def get_file_params(config):
    l = [(k, v['relative_path']) for k, v in config['params'].iteritems() if
         is_file_param(v)]
    return dict(l)

def param_settings(config):
    ranges = [(n, param_range(v)) for n, v in config['params'].iteritems() if
              not is_file_param(v)]
    return map(dict, param_combinations(ranges))

def make_name(n):
    m = re.match('(.*)\.', n)
    if m:
        return m.group(1)
    else:
        return n

def get_time_stamp():
    return time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())

def get_variable_params(config):
    var = []
    fixed = []
    for name, val in config['params'].iteritems():
        if isinstance(val, list) or isinstance(val, dict):
            if not is_file_param(val):
                var.append(name)
        else:
            fixed.append(name)
    return var, fixed

def run_name(s, params):
    prefix = '_'.join(str(s[p]) for p in params)
    return prefix+"_out"

def create_or_update_link(p, name, target):
    "Ensure that PATH/NAME points to TARGET.  Remove any existing link or file PATH/NAME."
    f = path.join(p, name)
    if path.exists(f):
        os.remove(f)
    os.symlink(target, f)

def setup_dirs(d, config_str, root):
    par = path.dirname(d)
    os.makedirs(d)
    create_or_update_link(par, 'latest', d)
    create_or_update_link(root, 'latest', d)
    with open(path.join(d, 'config.yaml'), 'w') as f:
        f.write(config_str)

def subdict(d, keys):
    return dict((k, v) for k, v in d.iteritems() if k in keys)
        
def process_vcs(config, path):
    vcs_config = config.get('vcs', None)
    if not vcs_config:
        return ''
    assert vcs_config['type'] == 'git'
    p = sp.Popen(['git', 'diff', '--stat'], stdout=sp.PIPE, cwd=path)
    out, err = p.communicate()
    assert not out.strip(), "Uncommitted changes in git repository: {0}".\
           format(out)
    p = sp.Popen(['git', 'rev-parse', 'HEAD'], stdout=sp.PIPE,
                 cwd=path)
    out, err = p.communicate()
    assert p.returncode==0
    return "vcs:\n  type: git\n  commit: {0}\n".format(out.strip())
    

def main():
    parser = optparse.OptionParser()
    parser.add_option('-l', '--log_dir', default=os.getenv('LAB_ASSISTANT_LOG_DIR', '.'))
    options, args = parser.parse_args()

    assert len(args)==1
    config_file = args[0]
    assert config_file!='exp_info.yaml', "Forbidden name for config file"
    with open(config_file) as f:
        config_str = f.read()
    config = yaml.load(config_str)

    name = config.get('name', make_name(config_file))
    stamp = get_time_stamp()
    outdir = path.join(options.log_dir, name, stamp)
    stderr.write("Output dir is {0}\n".format(outdir))

    if path.exists(outdir):
        print "Directory {0} already exists".format(outdir)
        return 1

    config_dir = path.abspath(path.dirname(config_file))
    vcs_info = process_vcs(config, config_dir)
    settings = param_settings(config)
    variable_params, fixed_params = get_variable_params(config)
    executable = path.join(config_dir, config['executable'])
    file_params = get_file_params(config)
    setup_dirs(outdir, config_str, options.log_dir)
    with open(path.join(outdir, 'exp_info.yaml'), 'w') as f:
        f.write(vcs_info)
        f.write("executable: {0}\n".format(executable))
        fixed_args = subdict(config['params'], fixed_params)
        stderr.write("fixed params: {0}\n".format(fixed_args))

        config_num = 0
        for s in settings:
            d = path.join(outdir, run_name(s, variable_params))
            os.mkdir(d)
            for k, v in file_params.iteritems():
                parent = path.dirname(path.join(d, v))
                if not path.exists(parent):
                    os.makedirs(parent)
            outfile_path = path.join(d, 'out.log')
            errfile_path = path.join(d, 'err.log')
            with open(outfile_path, 'w') as outfile:
                with open(errfile_path, 'w') as errfile:
                    args = make_invocation(executable, s, d, file_params)
                    stderr.write("\nConfiguration {0}\n".format(config_num))
                    for k in variable_params:
                        stderr.write("  {0}: {1}\n".format(k, s[k]))
                    config_num += 1
                    print outfile_path
                    print errfile_path
                    p = sp.Popen(args, stdout=outfile, stderr=errfile)
                    elapsed_time = 0
                    while True:
                        if p.poll() is not None:
                            break
                        
                        stderr.write("\r  Elapsed time is {0} seconds.  "
                                     "{1} bytes written on stdout and {2} bytes on stderr".\
                                     format(elapsed_time, path.getsize(outfile_path),
                                            path.getsize(errfile_path)))
                        inc = 1
                        time.sleep(inc)
                        elapsed_time += inc
                    if p.returncode==0:
                        stderr.write("\ndone\n")
                    else:
                        stderr.write("\nexited with return code {0}\n".\
                                     format(p.returncode))
        f.write("completed: true\n")
                
    
