#if 0 /*
# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------
# main.py - This is the Freevo main application code
# -----------------------------------------------------------------------
# $Id$
#
# Notes:
# Todo:        
#
# -----------------------------------------------------------------------
# $Log$
# Revision 1.113  2004/02/11 11:09:40  dischi
# cachetime checking not working right now
#
# Revision 1.112  2004/02/05 20:39:11  dischi
# check mmpython cache version
#
# Revision 1.111  2004/02/01 17:11:51  dischi
# make it possible to load cachefiles on startup
#
# Revision 1.110  2004/01/25 14:54:31  dischi
# save parent after skin change
#
# Revision 1.109  2004/01/24 18:53:54  dischi
# add mmpython md5 disc id support
#
# Revision 1.108  2004/01/19 20:29:11  dischi
# cleanup, reduce cache size
#
# Revision 1.107  2004/01/18 16:49:39  dischi
# check cache on startup
#
# Revision 1.106  2004/01/17 20:30:18  dischi
# use new metainfo
#
# Revision 1.105  2004/01/10 14:56:45  dischi
# better shutdown handling
#
# Revision 1.104  2004/01/10 13:19:52  dischi
# use new skin.set_base_fxd function
#
# Revision 1.103  2004/01/07 18:15:41  dischi
# add mmpython warning
#
# -----------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, et al. 
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
# ----------------------------------------------------------------------- */
#endif

# Must do this here to make sure no os.system() calls generated by module init
# code gets LD_PRELOADed
import os
os.environ['LD_PRELOAD'] = ''

import sys, time
import traceback
import signal


# i18n support

# First load the xml module. It's not needed here but it will mess
# up with the domain we set (set it from freevo 4Suite). By loading it
# first, Freevo will override the 4Suite setting to freevo

try:
    from xml.utils import qp_xml
    from xml.dom import minidom
    
    # now load other modules to check if all requirements are installed
    import mmpython
    import Image
    import pygame
    import twisted
    
except ImportError, i:
    print 'Can\'t find all Python dependencies:'
    print i
    print
    print 'Not all requirements of Freevo are installed on your system.'
    print 'Please check the INSTALL file for more informations.'
    print
    print 'A quick solution is to install the Freevo runtime. This contains'
    print 'all Python dependencies to run Freevo. Get the current runtime at'
    print 'http://sourceforge.net/project/showfiles.php?group_id=46652&release_id=194955'
    print 'After downloading, run \'./freevo install path-to-runtime.tgz\'.'
    print
    print 'The runtime doesn\'t contain external applications like mplayer, xine'
    print 'or tvtime. You need to download and install them, too (all except'
    print 'mplayer are optional).'
    print
    sys.exit(0)

    
import config

import util    # Various utilities
import osd     # The OSD class, used to communicate with the OSD daemon
import menu    # The menu widget class
import skin    # The skin class
import rc      # The RemoteControl class.

from item import Item
from event import *
from plugins.shutdown import shutdown


# Create the remote control object
rc_object = rc.get_singleton()

# Create the OSD object
osd = osd.get_singleton()

# Create the skin object
skin = skin.get_singleton()


class SkinSelectItem(Item):
    """
    Item for the skin selector
    """
    def __init__(self, parent, name, image, skin):
        Item.__init__(self, parent)
        self.name  = name
        self.image = image
        self.skin  = skin
        
    def actions(self):
        return [ ( self.select, '' ) ]

    def select(self, arg=None, menuw=None):
        """
        Load the new skin and rebuild the main menu
        """
        import plugin
        skin.set_base_fxd(self.skin)
        pos = menuw.menustack[0].choices.index(menuw.menustack[0].selected)

        parent = menuw.menustack[0].choices[0].parent
        menuw.menustack[0].choices = []
        for p in plugin.get('mainmenu'):
            menuw.menustack[0].choices += p.items(parent)

        menuw.menustack[0].selected = menuw.menustack[0].choices[pos]
        menuw.back_one_menu()

        

class MainMenu(Item):
    """
    this class handles the main menu
    """
    def getcmd(self):
        """
        Setup the main menu and handle events (remote control, etc)
        """
        import plugin
        menuw = menu.MenuWidget()
        items = []
        for p in plugin.get('mainmenu'):
            items += p.items(self)

        mainmenu = menu.Menu(_('Freevo Main Menu'), items, item_types='main', umount_all = 1)
        menuw.pushmenu(mainmenu)
        osd.add_app(menuw)


    def eventhandler(self, event = None, menuw=None, arg=None):
        """
        Automatically perform actions depending on the event, e.g. play DVD
        """
        # pressing DISPLAY on the main menu will open a skin selector
        # (only for the new skin code)
        if event == MENU_CHANGE_STYLE:
            items = []
            for name, image, skinfile in skin.get_skins():
                items += [ SkinSelectItem(self, name, image, skinfile) ]

            menuw.pushmenu(menu.Menu('SKIN SELECTOR', items))
            return True

        # give the event to the next eventhandler in the list
        return Item.eventhandler(self, event, menuw)
        
    


class Splashscreen(skin.Area):
    """
    A simple splash screen for osd startup
    """
    def __init__(self, text):
        skin.Area.__init__(self, 'content')

        self.pos          = 0
        self.bar_border   = skin.Rectange(bgcolor=0xff000000L, size=2)
        self.bar_position = skin.Rectange(bgcolor=0xa0000000L)
        self.text         = text

    def update_content(self):
        """
        there is no content in this area
        """
        layout    = self.layout
        area      = self.area_val
        content   = self.calc_geometry(layout.content, copy_object=True)

        self.write_text(self.text, content.font, content, height=-1, align_h='center')

        pos = 0
        x0, x1 = content.x, content.x + content.width
        y = content.y + content.font.font.height + content.spacing
        if self.pos:
            pos = round(float((x1 - x0 - 4)) / (float(100) / self.pos))
        self.drawroundbox(x0, y, x1-x0, 20, self.bar_border)
        self.drawroundbox(x0+2, y+2, pos, 16, self.bar_position)


    def progress(self, pos):
        """
        set the progress position and refresh the screen
        """
        self.pos = pos
        skin.draw('splashscreen', None)




def signal_handler(sig, frame):
    """
    the signal handler to shut down freevo
    """
    if sig in (signal.SIGTERM, signal.SIGINT):
        shutdown(exit=True)



def tracefunc(frame, event, arg, _indent=[0]):
    """
    function to trace everything inside freevo for debugging
    """
    if event == 'call':
        filename = frame.f_code.co_filename
        funcname = frame.f_code.co_name
        lineno = frame.f_code.co_firstlineno
        if 'self' in frame.f_locals:
            try:
                classinst = frame.f_locals['self']
                classname = repr(classinst).split()[0].split('(')[0][1:]
                funcname = '%s.%s' % (classname, funcname)
            except:
                pass
        here = '%s:%s:%s()' % (filename, lineno, funcname)
        _indent[0] += 1
        tracefd.write('%4s %s%s\n' % (_indent[0], ' ' * _indent[0], here))
        tracefd.flush()
    elif event == 'return':
        _indent[0] -= 1

    return tracefunc





#
# Freevo main function
#

# parse arguments
if len(sys.argv) >= 2:

    # force fullscreen mode
    # deactivate screen blanking and set osd to fullscreen
    if sys.argv[1] == '-force-fs':
        os.system('xset -dpms s off')
        config.START_FULLSCREEN_X = 1

    # activate a trace function
    if sys.argv[1] == '-trace':
        tracefd = open(os.path.join(config.LOGDIR, 'trace.txt'), 'w')
        sys.settrace(tracefunc)
        config.DEBUG = 2

    # create api doc for Freevo and move it to Docs/api
    if sys.argv[1] == '-doc':
        import pydoc
        import re
        for file in util.match_files_recursively('src/', ['py' ]):
            # doesn't work for everything :-(
            if file not in ( 'src/tv/record_server.py', ) and \
                   file.find('src/www') == -1 and \
                   file.find('src/helpers') == -1:
                file = re.sub('/', '.', file)
                try:
                    pydoc.writedoc(file[4:-3])
                except:
                    pass
        try:
            os.mkdir('Docs/api')
        except:
            pass
        for file in util.match_files('.', ['html', ]):
            print 'moving %s' % file
            os.rename(file, 'Docs/api/%s' % file)
        print
        print 'wrote api doc to \'Docs/api\''
        shutdown(exit=True)



# setup mmpython

if config.DEBUG > 2:
    mmpython.mediainfo.DEBUG = config.DEBUG
    mmpython.factory.DEBUG   = config.DEBUG
else:
    mmpython.mediainfo.DEBUG = 0
    mmpython.factory.DEBUG   = 0

mmpython.USE_NETWORK = config.USE_NETWORK
mmpython.disc.discinfo.CREATE_MD5_ID = config.MMPYTHON_CREATE_MD5_ID

# if not os.path.isfile(os.path.join(config.OVERLAY_DIR, 'cachetime')):
#     print '\nWARNING: no pre-cached data'
#     print 'Freevo will cache each directory when you first enter it. This can'
#     print 'be slow. Start "./freevo cache" to pre-cache all directories to speed'
#     print 'up usage of freevo'
#     print
# else:
#     f = open(os.path.join(config.OVERLAY_DIR, 'cachetime'))
#     if long(time.time()) - long(f.readline()) > 604800:
#         print '\nWARNING: cache files older than 7 days'
#         print 'Please rerun "./freevo cache" to speed up freevo'
#         print
#     f.close()
    

os.umask(config.UMASK)

# start
try:
    # signal handler
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # load the fxditem to make sure it's the first in the
    # mimetypes list
    import fxditem

    # load all plugins
    import plugin

    # prepare the skin
    skin.prepare()

    # Fire up splashscreen and load the plugins
    splash = Splashscreen(_('Starting Freevo, please wait ...'))
    skin.register('splashscreen', ('screen', splash))
    plugin.init(splash.progress)
    skin.delete('splashscreen')

    # Fire up splashscreen and load the cache
    if config.MEDIAINFO_USE_MEMORY == 2:
        import util.mediainfo
        cachefiles = []
        for type in ('video', 'audio', 'image', 'games'):
            if plugin.is_active(type):
                n = 'config.%s_ITEMS' % type.upper()
                x = eval(n)
                for item in x:
                    if os.path.isdir(item[1]):
                        cachefiles += [ item[1] ] + util.get_subdirs_recursively(item[1])


        cachefiles = util.unique(cachefiles)

        splash = Splashscreen(_('Reading cache, please wait ...'))
        skin.register('splashscreen', ('screen', splash))
        for f in cachefiles:
            splash.progress(int((float((cachefiles.index(f)+1)) / len(cachefiles)) * 100))
            util.mediainfo.load_cache(f)
        skin.delete('splashscreen')

    # prepare again, now that all plugins are loaded
    skin.prepare()

    # start menu
    MainMenu().getcmd()

    poll_plugins = plugin.get('daemon_poll')
    eventhandler_plugins  = []
    eventlistener_plugins = []

    for p in plugin.get('daemon_eventhandler'):
        if hasattr(p, 'event_listener') and p.event_listener:
            eventlistener_plugins.append(p)
        else:
            eventhandler_plugins.append(p)
    
    # Kick off the main menu loop
    _debug_('Main loop starting...',2)

    from childapp import running_children

    while 1:
        # Get next command
        while 1:

            event, event_repeat_count = rc_object.poll()
            # OK, now we have a repeat_count... to whom could we give it?
            if event:
                if event == OS_EVENT_POPEN2:
                    _debug_('popen2 %s' % event.arg[1])
                    event.arg[0].child = util.popen3.Popen3(event.arg[1])
                else:
                    _debug_('handling event %s' % str(event), 2)
                    break

            for p in poll_plugins:
                if not (rc_object.app and p.poll_menu_only):
                    p.poll_counter += 1
                    if p.poll_counter == p.poll_interval:
                        p.poll_counter = 0
                        p.poll()

            for child in running_children:
                child.poll()

            time.sleep(0.01)


        for p in eventlistener_plugins:
            p.eventhandler(event=event)

        if event == FUNCTION_CALL:
            event.arg()

        elif event.handler:
            event.handler(event=event)
            
        # Send events to either the current app or the menu handler
        elif rc_object.app:
            if not rc_object.app(event):
                for p in eventhandler_plugins:
                    if p.eventhandler(event=event):
                        break
                else:
                    _debug_('no eventhandler for event %s' % event, 2)

        else:
            app = osd.focused_app()
            if app:
                try:
                    if config.TIME_DEBUG:
                        t1 = time.clock()
                    app.eventhandler(event)
                    if config.TIME_DEBUG:
                        print time.clock() - t1
                except SystemExit:
                    raise SystemExit
                except:
                    if config.FREEVO_EVENTHANDLER_SANDBOX:
                        traceback.print_exc()
                        from gui import AlertBox
                        pop = AlertBox(text=_('Event \'%s\' crashed\n\nPlease take a ' \
                                              'look at the logfile and report the bug to ' \
                                              'the Freevo mailing list. The state of '\
                                              'Freevo may be corrupt now and this error '\
                                              'could cause more errors until you restart '\
                                              'Freevo.\n\nLogfile: %s\n\n') % \
                                       (event, sys.stdout.logfile),
                                       width=osd.width-2*config.OSD_OVERSCAN_X-50)
                        pop.show()
                    else:
                        raise 
            else:
                _debug_('no target for events given')



except KeyboardInterrupt:
    print 'Shutdown by keyboard interrupt'
    # Shutdown the application
    shutdown()

except SystemExit:
    pass

except:
    print 'Crash!'
    try:
        tb = sys.exc_info()[2]
        fname, lineno, funcname, text = traceback.extract_tb(tb)[-1]

        if config.FREEVO_EVENTHANDLER_SANDBOX:
            secs = 5
        else:
            secs = 1
        for i in range(secs, 0, -1):
            osd.clearscreen(color=osd.COL_BLACK)
            osd.drawstring(_('Freevo crashed!'), 70, 70, fgcolor=osd.COL_ORANGE)
            osd.drawstring(_('Filename: %s') % fname, 70, 130, fgcolor=osd.COL_ORANGE)
            osd.drawstring(_('Lineno: %s') % lineno, 70, 160, fgcolor=osd.COL_ORANGE)
            osd.drawstring(_('Function: %s') % funcname, 70, 190, fgcolor=osd.COL_ORANGE)
            osd.drawstring(_('Text: %s') % text, 70, 220, fgcolor=osd.COL_ORANGE)
            osd.drawstring(str(sys.exc_info()[1]), 70, 280, fgcolor=osd.COL_ORANGE)
            osd.drawstring(_('Please see the logfiles for more info'), 70, 350,
                           fgcolor=osd.COL_ORANGE)
            osd.drawstring(_('Exit in %s seconds') % i, 70, 410, fgcolor=osd.COL_ORANGE)
            osd.update()
            time.sleep(1)

    except:
        pass
    traceback.print_exc()

    # Shutdown the application, but not the system even if that is
    # enabled
    shutdown()
