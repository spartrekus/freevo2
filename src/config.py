# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# config.py - Handle the configuration files
# -----------------------------------------------------------------------------
# $Id$
#
# Try to find the freevo_config.py config file in the following places:
# 1) ./freevo_config.py               Defaults from the freevo dist
# 2) ~/.freevo/freevo_config.py       The user's private config
# 3) /etc/freevo/freevo_config.py     Systemwide config
# 
# Customize freevo_config.py from the freevo dist and copy it to one
# of the other places where it will not get overwritten by new
# checkouts/installs of freevo.
# 
# The format of freevo_config.py might change, in that case you'll
# have to update your customized version.
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2004 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Edition: Krister Lagerstrom <krister-freevo@kmlager.com>
#
# Please see the file freevo/Docs/CREDITS for a complete list of authors.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MER-
# CHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# -----------------------------------------------------------------------------

# python imports
import sys
import os
import re
import pwd
import setup_freevo
import __builtin__
import logging

# freevo imports
import sysconfig
import version
import system
import input

# get logging object
log = logging.getLogger('config')


VERSION = version.__version__

# For Internationalization purpose
import gettext
try:
    gettext.install('freevo', os.environ['FREEVO_LOCALE'], 1)
except: # unavailable, define '_' for all modules
    import __builtin__
    __builtin__.__dict__['_']= lambda m: m


# temp solution until this is fixed to True and False
# in all freevo modules
__builtin__.__dict__['TRUE']  = 1
__builtin__.__dict__['FALSE'] = 0


# String helper function. Always use this function to detect if the
# object is a string or not. It checks against str and unicode
def __isstring__(s):
    return isinstance(s, str) or isinstance(s, unicode)
        
__builtin__.__dict__['isstring'] = __isstring__


def print_config_changes(conf_version, file_version, changelist):
    """
    print changes made between version on the screen
    """
    ver_old = float(file_version)
    ver_new = float(conf_version)
    if ver_old == ver_new:
        return
    print
    print 'You are using version %s, changes since then:' % file_version
    changed = [(cv, cd) for (cv, cd) in changelist if cv > ver_old]
    if not changed:
        print 'The changelist has not been updated, please notify the developers!'
    else:
        for change_ver, change_desc in changed:
            print 'Version %s:' % change_ver
            for line in change_desc.split('\n'):
                print '    ', line.strip()
            print
    print
            

#
# get information about what is started here:
# helper = some script from src/helpers or is webserver or recordserver
#
HELPER          = 0
IS_RECORDSERVER = 0
IS_WEBSERVER    = 0

app = os.path.splitext(os.path.basename(sys.argv[0]))[0]
__builtin__.__dict__['__freevo_app__'] = app

if sys.argv[0].find('main.py') == -1:
    HELPER=1
if sys.argv[0].find('recordserver.py') != -1:
    IS_RECORDSERVER = 1
elif sys.argv[0].find('webserver.py') != -1:
    IS_WEBSERVER = 1

# remove this later
DEBUG = 0


LOGDIR = sysconfig.CONF.logdir
FREEVO_CACHEDIR = sysconfig.CONF.cachedir

def _mem_debug_function_(type, name='', level=1):
    if MEMORY_DEBUG < level:
        return
    print '<mem> %s: %s' % (type, name)


__builtin__.__dict__['_mem_debug_']= _mem_debug_function_

#
# Default settings
# These will be overwritten by the contents of 'freevo.conf'
#
CONF = sysconfig.CONF
if not hasattr(CONF, 'geometry'):
    CONF.geometry = '800x600'
w, h = CONF.geometry.split('x')
CONF.width, CONF.height = int(w), int(h)

if not hasattr(CONF, 'display'):
    CONF.display = 'x11'
if not hasattr(CONF, 'tv'):
    CONF.tv = 'ntsc'
if not hasattr(CONF, 'chanlist'):
    CONF.chanlist = 'us-cable'
if not hasattr(CONF, 'version'):
    CONF.version = 0


#
# TV card settup
#

class TVSettings(dict):
    def __setitem__(self, key, val):
        # FIXME: key has to end with number or we crash here
        number = key[-1]
        dict.__setitem__(self, key, val(number))
    
TV_SETTINGS = TVSettings()

TV_DEFAULT_SETTINGS = None


#
# Config file handling
#
cfgfilepath = [ '.', os.path.expanduser('~/.freevo'), '/etc/freevo',
                '/usr/local/etc/freevo' ]


#
# Read the environment set by the start script
#
SHARE_DIR   = os.path.abspath(os.environ['FREEVO_SHARE'])
CONTRIB_DIR = os.path.abspath(os.environ['FREEVO_CONTRIB'])

SKIN_DIR  = os.path.join(SHARE_DIR, 'skins')
ICON_DIR  = os.path.join(SHARE_DIR, 'icons')
IMAGE_DIR = os.path.join(SHARE_DIR, 'images')
FONT_DIR  = os.path.join(SHARE_DIR, 'fonts')

RUNAPP = os.environ['RUNAPP']


#
# Check that freevo_config.py is not found in the config file dirs
#
for dirname in cfgfilepath[1:]:
    freevoconf = dirname + '/freevo_config.py'
    if os.path.isfile(freevoconf):
        log.critical(('freevo_config.py found in %s, please remove it ' +
                      'and use local_conf.py instead!') % freevoconf)
        sys.exit(1)
        
#
# search missing programs at runtime
#
for program, valname, needed in setup_freevo.EXTERNAL_PROGRAMS:
    if not hasattr(CONF, valname) or not getattr(CONF, valname):
        setup_freevo.check_program(CONF, program, valname, needed, verbose=0)
    if not hasattr(CONF, valname) or not getattr(CONF, valname):
        setattr(CONF, valname, '')

#
# fall back to x11 if display is mga or fb and DISPLAY ist set
# or switch to fbdev if we have no DISPLAY and x11 or dga is used
#
if not HELPER:
    if os.environ.has_key('DISPLAY') and os.environ['DISPLAY']:
        if CONF.display in ('mga', 'fbdev'):
            print
            print 'Warning: display is set to %s, but the environment ' % \
                  CONF.display + \
                  'has DISPLAY=%s.' % os.environ['DISPLAY']
            print 'this could mess up your X display, setting display to x11.'
            print 'If you really want to do this, start \'DISPLAY="" freevo\''
            print
            CONF.display='x11'
    else:
        if CONF.display == 'x11':
            print
            print 'Warning: display is set to %s, but the environment ' % \
                  CONF.display + \
                  'has no DISPLAY set. Setting display to fbdev.'
            print
            CONF.display='fbdev'

elif CONF.display == 'dxr3':
    # don't use dxr3 for helpers. They don't use the osd anyway, but
    # it may mess up the dxr3 output (don't ask why).
    CONF.display='fbdev'
    
#
# Load freevo_config.py:
#
if os.path.isfile(os.environ['FREEVO_CONFIG']):
    log.info('Loading cfg: %s' % os.environ['FREEVO_CONFIG'])
    execfile(os.environ['FREEVO_CONFIG'], globals(), locals())
    
else:
    log.critical("Error: %s: no such file" % os.environ['FREEVO_CONFIG'])
    sys.exit(1)


#
# Search for local_conf.py:
#
for dirname in cfgfilepath:
    overridefile = dirname + '/local_conf.py'
    if os.path.isfile(overridefile):
        log.info('Loading cfg overrides: %s' % overridefile)
        execfile(overridefile, globals(), locals())

        try:
            CONFIG_VERSION
        except NameError:
            print
            print 'Error: your local_config.py file has no version information'
            print 'Please check freevo_config.py for changes and set'
            print 'CONFIG_VERSION in %s to %s' % \
                  (overridefile, LOCAL_CONF_VERSION)
            print
            sys.exit(1)

        if int(str(CONFIG_VERSION).split('.')[0]) != \
           int(str(LOCAL_CONF_VERSION).split('.')[0]):
            print
            print 'Error: The version information in freevo_config.py doesn\'t'
            print 'match the version in your local_config.py.'
            print 'Please check freevo_config.py for changes and set'
            print 'CONFIG_VERSION in %s to %s' % \
                  (overridefile, LOCAL_CONF_VERSION)
            print_config_changes(LOCAL_CONF_VERSION, CONFIG_VERSION,
                                 LOCAL_CONF_CHANGES)
            sys.exit(1)

        if int(str(CONFIG_VERSION).split('.')[1]) != \
           int(str(LOCAL_CONF_VERSION).split('.')[1]):
            log.warning('freevo_config.py was changed.\n' +
                        'Please check your local_config.py')
            print_config_changes(LOCAL_CONF_VERSION, CONFIG_VERSION, 
                                 LOCAL_CONF_CHANGES)
        break

else:
    locations = ''
    for dirname in cfgfilepath:
        locations += '  %s\n' % dirname
    log.critical("""local_conf.py not found
Freevo is not completely configured to start

The configuration is based on three files. This may sound oversized, but this
way it's easier to configure. First Freevo loads a file called 'freevo.conf'.
This file will be generated by 'freevo setup'. Use 'freevo setup --help' to get
information about the parameter. Based on the informations in that file, Freevo
will guess some settings for your system. This takes place in a file called
'freevo_config.py'. Since this file may change from time to time, you should
not edit this file. After freevo_config.py is loaded, Freevo will look for a
file called 'local_conf.py'. You can overwrite the variables from
'freevo_config.py' in here. There is an example for 'local_conf.py' called
'local_conf.py.example' in the Freevo distribution.
    
If you need more help, use the internal webserver to get more informations
how to setup Freevo. To do this, you need to set
WWW_USERS = { 'username' : 'password' }
in your local_conf.py and then you can access the doc at
http://localhost:8080/help/
    
The location of freevo_config.py is %s
Freevo searches for freevo.conf and local_conf.py in the following locations:
%s

Since it's highly unlikly you want to start Freevo without further
configuration, Freevo will exit now.
"""  % (os.environ['FREEVO_CONFIG'], locations))
    sys.exit(0)


# set the umask
os.umask(UMASK)

#
# force fullscreen when freevo is it's own windowmanager
#
if len(sys.argv) >= 2 and sys.argv[1] == '--force-fs':
    START_FULLSCREEN_X = 1


#
# set default font
#
OSD_DEFAULT_FONTNAME = os.path.join(FONT_DIR, OSD_DEFAULT_FONTNAME)

#
# set list of video files to []
# (fill be filled from the plugins) 
#
VIDEO_SUFFIX = []

for p in plugin.getall():
    if p.startswith('video'):
        try:
            for s in eval('VIDEO_%s_SUFFIX' % p[6:].upper()):
                if not s in VIDEO_SUFFIX:
                    VIDEO_SUFFIX.append(s)
        except:
            pass

            
#
# set data dirs
# if not set, set it to root and home dir
# if set, make all path names absolute
#
for type in ('video', 'audio', 'image', 'games'):
    n = '%s_ITEMS' % type.upper()
    x = eval(n)
    if x == None:
        x = []
        if os.environ.has_key('HOME') and os.environ['HOME']:
            x.append(('Home', os.environ['HOME']))
        x.append(('Root', '/'))
        exec('%s = x' % n)
        if not HELPER and plugin.is_active('mediamenu', type):
            log.warning('%s not set, set it to Home directory' % n)
        if type == 'video':
            VIDEO_ONLY_SCAN_DATADIR = True

    elif type == 'games':
        abs = []
        for d in x:
            pos = d[1].find(':')
            if pos == -1:
                abs.append((d[0], os.path.abspath(d[1]), d[2]))
            else:
                if pos > d[1].find('/'):                        
                    abs.append((d[0], os.path.abspath(d[1]), d[2]))
                else:
                    abs.append((d[0], d[1][0:pos+1] + \
                                os.path.abspath(d[1][pos+1:]), d[2]))
        exec ('%s = abs' % n)
    else:
        # The algorithm doesn't work for GAMES_ITEMS, so we leave it out
        abs = []
        for d in x:
            if isstring(d):
                pos = d.find(':')
                if pos == -1:
                    abs.append(os.path.abspath(d))
                else:
                    if pos > d.find('/'):                        
                        abs.append(os.path.abspath(d))
                    else:
                        abs.append(d[0:pos+1] + os.path.abspath(d[pos+1:]))
            else:
                pos = d[1].find(':')
                if pos == -1:
                    abs.append((d[0], os.path.abspath(d[1])))
                else:
                    if pos > d[1].find('/'):                        
                        abs.append((d[0], os.path.abspath(d[1])))
                    else:
                        abs.append((d[0], d[1][0:pos+1] + \
                                    os.path.abspath(d[1][pos+1:])))
        exec ('%s = abs' % n)
            

        
if not TV_RECORD_DIR:
    TV_RECORD_DIR = VIDEO_ITEMS[0][1]
    msg = ('TV_RECORD_DIR not set\n' +
           '  Please set TV_RECORD_DIR to the directory, where recordings\n' +
           '  should be stored or remove the tv plugin. Autoset variable\n' +
           '  to %s.') % TV_RECORD_DIR
    if not HELPER and plugin.is_active('tv'):
        log.warning(msg)
        
if not VIDEO_SHOW_DATA_DIR and not HELPER:
    log.warning('VIDEO_SHOW_DATA_DIR not found')
    

#
# List of objects representing removable media, e.g. CD-ROMs,
# DVDs, etc.
#
REMOVABLE_MEDIA = sysconfig.REMOVABLE_MEDIA


#
# compile the regexp
#
VIDEO_SHOW_REGEXP_MATCH = re.compile("^.*" + VIDEO_SHOW_REGEXP).match
VIDEO_SHOW_REGEXP_SPLIT = re.compile("[\.\- ]*" + \
                                     VIDEO_SHOW_REGEXP + "[\.\- ]*").split


try:
    LOCALE
    log.critical('LOCALE is deprecated. Set encoding in freevo.conf.')
    sys.exit(0)
except NameError, e:
    pass
    
encoding = LOCALE = sysconfig.CONF.encoding

try:
    OVERLAY_DIR
    log.critical('OVERLAY_DIR is deprecated. Set vfs_dir in freevo.conf' +\
                 '  to change the location of the virtual file system')
    sys.exit(0)
except NameError, e:
    pass

OVERLAY_DIR = sysconfig.VFS_DIR

# auto detect function
detect = system.detect

# make sure USER and HOME are set
os.environ['USER'] = pwd.getpwuid(os.getuid())[0]
os.environ['HOME'] = pwd.getpwuid(os.getuid())[5]


REDESIGN_MAINLOOP = 'not working while mainloop redesign'
REDESIGN_BROKEN   = 'not working while gui redesign'
REDESIGN_FIXME    = 'not working since gui redesign, feel free to fix this'
REDESIGN_UNKNOWN  = 'plugin may be broken after gui redesign, please check'

