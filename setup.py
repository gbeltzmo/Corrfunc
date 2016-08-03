#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import print_function

import os
import os.path as path
from os.path import join as pjoin
import sys
from sys import version_info
import re
import subprocess
    
# partial import
import Corrfunc
from Corrfunc import read_text_file, write_text_file

# Make sure we are running on posix (Linux, Unix, MAC OSX)
if os.name != 'posix':
    sys.exit("Sorry, Windows is not supported")


def strip_line(line, sep=os.linesep):
    """
    Removes occurrence of character (sep) from a line of text
    """
    
    try:
        return line.strip(sep)
    except TypeError:
        return line.decode('utf-8').strip(sep)


def run_command(command, **kwargs):
    proc = subprocess.Popen(command, shell=True,
                            **kwargs)
    stdout, stderr = proc.communicate(None)
    status = proc.wait()
    if status:
        msg = "command = {0} failed with stdout = {1} stderr = {2} "\
              "status {3:d}\n".format(command, stdout, stderr, status)
        raise Exception(msg)
    return stdout, stderr


def get_dict_from_buffer(buf, keys=['DISTNAME', 'MAJOR',
                                    'MINOR', 'PATCHLEVEL',
                                    'PYTHON',
                                    'MIN_PYTHON_MAJOR',
                                    'MIN_PYTHON_MINOR',
                                    'MIN_NUMPY_MAJOR',
                                    'MIN_NUMPY_MINOR']):
    """
    Parses a string buffer for key-val pairs for the supplied keys.

    Slightly modified from:
    "http://stackoverflow.com/questions/5323703/regex-how-to-"\
    "match-sequence-of-key-value-pairs-at-end-of-string

    """
    
    import re
    keys = [k.strip() for k in keys]
    regex = re.compile(r'''
    \n                 # all key-value pairs are on separate lines
    \s*                # there might be some leading spaces
    (                  # start group to return
    (?:{0}\s*)         # placeholder for tags to detect '\S+' == all
    \s*:*=\s*          # optional spaces, optional colon, = , optional spaces
    .*                 # the value
    )                  # end group to return
    '''.format('|'.join(keys)), re.VERBOSE)
    
    matches = regex.findall(buf)
    pairs = {k: [] for k in keys}
    for match in matches:
        key, val = match.split('=', 1)
        # remove colon and leading/trailing whitespace
        key = (strip_line(key, ':')).strip()
        # remove newline and leading/trailing whitespace
        val = (strip_line(val)).strip()
        if key not in keys:
            msg = "regex produced incorrect match. regex pattern = {0}"\
                  "claims key = [{1}] while original set of search keys = {2}"\
                  .format(regex.pattern, key, '|'.join(keys))
            raise RuntimeError(msg)
        pairs.setdefault(key, []).append(val)
            
    return pairs

    
base_url = "https://github.com/manodeep/Corrfunc"
common_mk_file = pjoin(path.dirname(path.abspath(__file__)),
                       "common.mk")
common = read_text_file(common_mk_file)
common_dict = get_dict_from_buffer(common)
name = common_dict['DISTNAME'][0]
major = common_dict['MAJOR'][0]
minor = common_dict['MINOR'][0]
patch = common_dict['PATCHLEVEL'][0]
if name is None or major is None or minor is None or patch is None:
    msg = "ERROR: Did not find at least one of the keys "\
          "(DISTNAME, MAJOR, MINOR, PATCHLEVEL) in 'common.mk'.\n"\
          "Checks can not run - aborting installation. "\
          "name = {1} major = {2} minor = {3} patch = {4}\n\n"\
          "You can fix this by re-issuing git clone {0}".\
          format(base_url, name, major, minor, patch)
    raise AssertionError(msg)

version = "{0}.{1}.{2}".format(major, minor, patch)

# Check that version matches
if Corrfunc.__version__ != version:
    msg = "ERROR: Version mis-match. Python version found = {0} \
    while C version claims {1}".format(Corrfunc.__version__, version)
    sys.exit(msg)

# Since arbitrary python can be used even within the Makefile
# make sure that the current python executable is the same as the
# one specified in common.mk. Easiest way is to replace
make_python = common_dict['PYTHON'][0]
if make_python is None:
    msg = "PYTHON is not defined in 'common.mk'. Please "\
          "edit 'common.mk' and define PYTHON (typically "\
          "just python) "
    sys.exit(msg)

this_python = sys.executable
python_script = "'from __future__ import print_function; "\
                "import sys; print(sys.executable)'"
get_full_python, full_python_errors = run_command(
    make_python + " -c " + python_script,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if get_full_python is None:
    msg = "Could not determine which python is resolved in the Makefile "\
          "Parsed PYTHON=[${0}] in Makefile which could not be resolved "\
          "through the shell. Please report your python setup and file an "\
          "installation issue at {1}.".format(make_python, base_url)
    sys.exit(msg)


get_full_python = strip_line(get_full_python, os.linesep)
if get_full_python == this_python:
    print("Great. Current python is the same as the python in the Makefile")
else:
    msg = "Looks like python specified in Makefile = {0} is different "\
          "from the invoked python instance = {1}.\nReplacing PYTHON "\
          "in 'common.mk' and recompiling *all* files".format(
              get_full_python, this_python)
    print(msg)
    key = "PYTHON"
    python_regexp = re.compile(r'''
    \n\s*           # there might be some leading spaces
    (               # start group to return
    (?:{0}\s*)      # placeholder for tags to detect '\S+' == all
    \s*:*=\s*       # optional spaces, optional colon, = , optional spaces
    .*              # the value
    )               # end group to return
    '''.format(key), re.VERBOSE)
    replacement = '\n{0}:={1}'.format(key, this_python)
    common = python_regexp.sub(replacement, common, count=1)
    write_text_file(common_mk_file, common)


min_py_major = int(common_dict['MIN_PYTHON_MAJOR'][0])
min_py_minor = int(common_dict['MIN_PYTHON_MINOR'][0])
min_np_major = int(common_dict['MIN_NUMPY_MAJOR'][0])
min_np_minor = int(common_dict['MIN_NUMPY_MINOR'][0])

# Enforce minimum python version
if version_info[0] < min_py_major or \
   (version_info[0] == min_py_major and version_info[1] < min_py_minor):
    raise RuntimeError('Sorry. Found python {0}.{1} but minimum required \
    python version is {2}.{3}'.format(version_info[0],
                                      version_info[1],
                                      min_py_major, min_py_minor))
# numpy 1.7 supports python 2.4-2.5; python 3.1-3.3.
try:
    from setuptools import setup, Extension
    from setuptools.command.build_ext import build_ext
except ImportError:
    from distutils.core import setup, Extension
    from distutils.command.build_ext import build_ext

if sys.argv[-1] == "publish":
    os.system("python setup.py sdist upload")
    sys.exit()


class BuildExtSubclass(build_ext):
    def build_extensions(self):
        # Everything has already been configured - so just call make
        for ext in self.extensions:
            sources = ext.sources

            # Blatantly copied from the Android distutils setup.py
            # But then modified to make it python3 compatible!
            if sources is None:
                msg = "in 'ext_modules' option (extension {0}),"\
                      "sources must be present and must be "\
                      "a list of source filename".format(ext.name)
                raise Exception(msg)

            if len(sources) == 1:
                ext_dir = path.dirname(sources[0])
            else:
                # not debugged - likely to be wrong
                ext_dir = path.commonprefix(sources)

            command = "cd {0} && make ".format(ext_dir)
            run_command(command)
            
            import shutil
            import errno
            try:
                os.makedirs(path.dirname(self.get_ext_fullpath(ext.name)))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise

            # full_name = '{0}.so.{1}'.format(pjoin(ext_dir, ext.name),
            #                                 version)
            full_build_name = '{0}.{1}'.format(
                self.get_ext_fullpath(ext.name), version)

            full_name = '{0}.so'.format(pjoin(ext_dir, ext.name))
            full_build_name = '{0}'.format(self.get_ext_fullpath(ext.name))
            pkg_sourcedir = '{0}'.format(pjoin(ext_dir, '../../Corrfunc'))
            pkg_in_srcdir = '{0}/{1}.so'.format(pkg_sourcedir, ext.name)

            shutil.copyfile(full_name, full_build_name)

            # just copy the newly created library in the Corrfunc module directory.
            # Installed Corrfunc version will automatically get the extensions
            #os.remove(pkg_in_srcdir)
            #os.symlink('{0}'.format(pjoin('../', full_name)),
            #           pkg_in_srcdir)
            shutil.copyfile(full_name, pkg_in_srcdir)


def generate_extensions(python_dirs):
    extensions = []
    for pdir in python_dirs:
        mk = read_text_file(pjoin(path.dirname(path.abspath(__file__)),
                                  pdir, "Makefile"))
        makefile_dict = get_dict_from_buffer(mk, ['PROJECT', 'SOURCES'])
        project = makefile_dict['PROJECT'][0].strip()
        src_files = makefile_dict['SOURCES']
        if project is None or src_files is None:
            msg = "In directory = {0}, can not locate either the project "\
                  "name or the list of source files."\
                  "Got project = {1} and sources = {2}."\
                  .format(pdir, project, src_files)
            raise AssertionError(msg)

        sources = [pjoin(pdir, f) for f in src_files]
        # print("Found project = {0} in dir = {1} with sources = {2}\n".
        #       format(project, pdir, sources))
        ext = Extension("{0}".format(project),
                        sources=sources)
        extensions.append(ext)
    return extensions


# Only python >= 3.5 supports the recursive glob, hence
# defining the function that works on all reasonable pythons
# http://stackoverflow.com/questions/2186525/use-a-glob-to-
# find-files-recursively-in-python
def recursive_glob(rootdir='.', patterns=['*']):
    import fnmatch
    return [pjoin(looproot, filename)
            for looproot, _, filenames in os.walk(rootdir)
            for filename in filenames for p in patterns
            if fnmatch.fnmatch(filename, p)]


# Taken from numpy setup.py
def setup_packages():

    # protect the user in case they run python setup.py not from root directory
    src_path = path.dirname(path.abspath(sys.argv[0]))
    old_path = os.getcwd()
    os.chdir(src_path)
    sys.path.insert(0, src_path)

    # create a list of the python extensions
    python_dirs = ["xi_theory/python_bindings",
                   "xi_mocks/python_bindings"]
    extensions = generate_extensions(python_dirs)

    # only run this if not creating source dist
    if "sdist" not in sys.argv:
        command = "make install"
        run_command(command)

    # find all the data-files required.
    # Now the lib + associated header files have been generated
    # and put in lib/ and include/
    # This step must run after ``make install``
    dirs_patterns = {'xi_theory/tests/data': ['*.ff', '*.txt',
                                              '*.txt.gz', '*.dat'],
                     'xi_mocks/tests/data': ['*.ff', '*.txt',
                                             '*.txt.gz', '*.dat'],
                     'xi_theory/tests': ['Mr19*', 'bins*', 'cmass*'],
                     'xi_mocks/tests': ['Mr19*', 'bins*', 'angular_bins*'],
                     'include': ['count*.h'],
                     'lib': ['libcount*.a']
                     }
    data_files = []
    for d in dirs_patterns:
        patterns = dirs_patterns[d]
        f = recursive_glob(d, patterns)
        data_files.extend(f)

    # change them to be relative to package dir rather than root
    data_files = ["../{0}".format(d) for d in data_files]
    long_description = read_text_file('README.rst')

    # All book-keeping is done.
    # base_url = "https://github.com/manodeep/Corrfunc"
    classifiers = ['Development Status :: 4 - Beta',
                   'Intended Audience :: Developers',
                   'Intended Audience :: Science/Research',
                   'License :: OSI Approved :: MIT License',
                   'Natural Language :: English',
                   'Operating System :: POSIX',
                   'Programming Language :: C',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.6',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.5']
    metadata = dict(
        name=name,
        version=version,
        author='Manodeep Sinha',
        author_email='manodeep@gmail.com',
        maintainer='Manodeep Sinha',
        maintainer_email='manodeep@gmail.com',
        url=base_url,
        download_url='{0}/archive/{1}-{2}.tar.gz'.format(
            base_url, name, version),
        description='Blazing fast correlation functions on the CPU',
        long_description=long_description,
        classifiers=classifiers,
        license='MIT',
        # Solaris might work, Windows will almost certainly not work
        platforms=["Linux", "Mac OSX", "Unix"],
        keywords=['correlation functions', 'simulations',
                  'surveys', 'galaxies'],
        packages=[name],
        ext_package=name,
        ext_modules=extensions,
        package_data={'': data_files},
        include_package_data=True,
        install_requires=['setuptools',
                          'numpy>={0}.{1}'.format(min_np_major, min_np_minor),
                          'future'],
        zip_safe=False,
        cmdclass={'build_ext': BuildExtSubclass})

    # Now the actual setup
    try:
        setup(**metadata)
    finally:
        del sys.path[0]
        os.chdir(old_path)

    return

if __name__ == '__main__':
    setup_packages()
