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
# Note: this file needs a huge cleanup!!!
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


# String helper function. Always use this function to detect if the
# object is a string or not. It checks against str and unicode
def __isstring__(s):
    return isinstance(s, str) or isinstance(s, unicode)
        
__builtin__.__dict__['isstring'] = __isstring__

app = os.path.splitext(os.path.basename(sys.argv[0]))[0]
__builtin__.__dict__['__freevo_app__'] = app


# XXX ************************************************************

# XXX The following code will be removed before the next release
# XXX Please do NOT use this varaibles anymore and fix code were it
# XXX is used.

# use True/False
__builtin__.__dict__['TRUE']  = 1
__builtin__.__dict__['FALSE'] = 0

# use __freevo_app__
HELPER = 0
if sys.argv[0].find('main.py') == -1:
    HELPER=1

# use logger
DEBUG = 0

# use sysconfig code
LOGDIR = sysconfig.CONF.logdir
FREEVO_CACHEDIR = sysconfig.CONF.cachedir

# use special logger
def _mem_debug_function_(type, name='', level=1):
    if MEMORY_DEBUG < level:
        return
    print '<mem> %s: %s' % (type, name)

__builtin__.__dict__['_mem_debug_']= _mem_debug_function_

# XXX ************************************************************

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
# Read the environment set by the start script
#
SHARE_DIR   = os.path.abspath(os.environ['FREEVO_SHARE'])
CONTRIB_DIR = os.path.abspath(os.environ['FREEVO_CONTRIB'])

SKIN_DIR  = os.path.join(SHARE_DIR, 'skins')
ICON_DIR  = os.path.join(SHARE_DIR, 'icons')
IMAGE_DIR = os.path.join(SHARE_DIR, 'images')
FONT_DIR  = os.path.join(SHARE_DIR, 'fonts')


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
# load the config file
#
execfile(os.path.join(os.path.dirname(__file__), 'configfile.py'))

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
def detect(*what):
    for module in what:
        exec('import %s' % module)


# make sure USER and HOME are set
os.environ['USER'] = pwd.getpwuid(os.getuid())[0]
os.environ['HOME'] = pwd.getpwuid(os.getuid())[5]


REDESIGN_MAINLOOP = 'not working while mainloop redesign'
REDESIGN_BROKEN   = 'not working while gui redesign'
REDESIGN_FIXME    = 'not working since gui redesign, feel free to fix this'
REDESIGN_UNKNOWN  = 'plugin may be broken after gui redesign, please check'
