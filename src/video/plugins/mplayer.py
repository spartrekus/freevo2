# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------
# mplayer.py - the Freevo MPlayer module for video
# -----------------------------------------------------------------------
# $Id$
#
# Notes: 
#
# Todo:  Copy some stuff in an application for mplayer video and tv      
#
# -----------------------------------------------------------------------
# $Log$
# Revision 1.103  2005/05/25 19:23:56  dischi
# fix crash
#
# Revision 1.102  2005/05/10 18:44:49  dischi
# fix crash for bad detections
#
# Revision 1.101  2005/05/05 17:34:01  dischi
# adjust to new gui submodule imports
#
# Revision 1.100  2005/05/05 10:26:55  dischi
# use vfs mount functions
#
# Revision 1.99  2005/04/10 17:58:12  dischi
# switch to new mediainfo module
#
# Revision 1.98  2005/01/02 13:08:01  dischi
# make it possible to set video filter for mplayer
#
# Revision 1.97  2005/01/01 18:48:53  dischi
# remove debug
#
# Revision 1.96  2005/01/01 17:07:32  dischi
# fix crash
#
# Revision 1.95  2005/01/01 15:06:19  dischi
# add MPLAYER_RESAMPLE_AUDIO
#
# Revision 1.94  2004/12/31 11:57:44  dischi
# renamed SKIN_* and OSD_* variables to GUI_*
#
# Revision 1.93  2004/12/19 10:36:31  dischi
# update bmovl fifo handling
#
# Revision 1.92  2004/12/18 13:36:08  dischi
# adjustments to new bmovl display
#
# Revision 1.91  2004/11/20 18:23:05  dischi
# use python logger module for debug
#
# Revision 1.90  2004/10/30 18:47:47  dischi
# move progressbar to gui/area
#
# Revision 1.89  2004/10/06 19:01:32  dischi
# use new childapp interface
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

# python imports
import os, re
import popen2

# external imports
import notifier
import mmpython
from mevas.bmovl2 import MPlayerOverlay
from mevas.displays import bmovlcanvas

# freevo imports
import config     # Configuration handler. reads config file.
import util       # Various utilities
import childapp
import plugin
import gui
import gui.displays
import gui.areas

from application import Application
from event import *

import logging
log = logging.getLogger('video')

class PluginInterface(plugin.Plugin):
    """
    Mplayer plugin for the video player.

    With this plugin Freevo can play all video files defined in
    VIDEO_MPLAYER_SUFFIX. This is the default video player for Freevo.
    """
    def __init__(self):
        # XXX Removed the version detection code. Mplayer 0.90 is too old,
        # XXX even the mplayer people don't support it anymore. 
        # XXX Removing the check also removes some strange startup problems

        # create plugin structure
        plugin.Plugin.__init__(self)

        # register mplayer as the object to play video
        plugin.register(MPlayer(), plugin.VIDEO_PLAYER, True)



class MPlayer(Application):
    """
    the main class to control mplayer
    """
    def __init__(self):
        """
        init the mplayer object
        """
        Application.__init__(self, 'mplayer', 'video', True)
        self.name       = 'mplayer'
        self.seek       = 0
        self.app        = None
        self.plugins    = []
        self._timer_id  = None
        self.hide_osd_cb = False
        self.use_bmovl  = True

    def rate(self, item):
        """
        How good can this player play the file:
        2 = good
        1 = possible, but not good
        0 = unplayable
        """
        if item.url[:6] in ('dvd://', 'vcd://') and item.url.endswith('/'): 
            return 1
        if item.mode in ('dvd', 'vcd'):
            return 2
        if item.mimetype in config.VIDEO_MPLAYER_SUFFIX:
            return 2
        if item.network_play:
            return 1
        return 0
    
    
    def play(self, options, item):
        """
        play a videoitem with mplayer
        """
        self.options = options
        self.item    = item
        
        mode         = item.mode
        url          = item.url

        self.item_info    = None
        self.item_length  = -1
        self.item.elapsed = 0        

        if mode == 'file':
            url = item.url[6:]
            self.item_info = mmpython.parse(url)
            if hasattr(self.item_info, 'get_length'):
                self.item_length = self.item_info.get_endpos()
                self.dynamic_seek_control = True
                
        if url.startswith('dvd://') and url[-1] == '/':
            url += '1'
            
        if url == 'vcd://':
            c_len = 0
            for i in range(len(item.info.tracks)):
                if item.info.tracks[i].length > c_len:
                    c_len = item.info.tracks[i].length
                    url = item.url + str(i+1)
            
        try:
            log.info('MPlayer.play(): mode=%s, url=%s' % (mode, url))
        except UnicodeError:
            log.info('MPlayer.play(): [non-ASCII data]')

        if mode == 'file' and not os.path.isfile(url):
            # This event allows the videoitem which contains subitems to
            # try to play the next subitem
            return '%s\nnot found' % os.path.basename(url)
       

        # Build the MPlayer command
        command = [ config.MPLAYER_CMD ] + config.MPLAYER_ARGS_DEF.split(' ') + \
                  [ '-slave', '-ao'] + config.MPLAYER_AO_DEV.split(' ')

        additional_args = []

        if mode == 'dvd':
            if config.DVD_LANG_PREF:
                # There are some bad mastered DVDs out there. E.g. the specials
                # on the German Babylon 5 Season 2 disc claim they have more
                # than one audio track, even more then on en. But only the
                # second on works, mplayer needs to be started without -alang
                # to find the track
                if hasattr(item, 'mplayer_audio_broken') and \
                       item.mplayer_audio_broken:
                    log.warning('dvd audio broken, try without alang')
                else:
                    additional_args += [ '-alang', config.DVD_LANG_PREF ]

            if config.DVD_SUBTITLE_PREF:
                # Only use if defined since it will always turn on subtitles
                # if defined
                additional_args += [ '-slang', config.DVD_SUBTITLE_PREF ]

        if hasattr(item.media, 'devicename') and mode != 'file':
            additional_args += [ '-dvd-device', item.media.devicename ]
        elif mode == 'dvd':
            # dvd on harddisc
            additional_args += [ '-dvd-device', item.filename ]
            url = url[:6] + url[url.rfind('/')+1:]
            
        if item.media and hasattr(item.media,'devicename'):
            additional_args += [ '-cdrom-device', item.media.devicename ]

        if item.selected_subtitle == -1:
            additional_args += [ '-noautosub' ]

        elif item.selected_subtitle and mode == 'file':
            if os.path.isfile(os.path.splitext(item.filename)[0]+'.idx'):
                additional_args += [ '-vobsubid', str(item.selected_subtitle) ]
            else:
                additional_args += [ '-sid', str(item.selected_subtitle) ]
                
        elif item.selected_subtitle:
            additional_args += [ '-sid', str(item.selected_subtitle) ]
            
        if item.selected_audio != None:
            additional_args += [ '-aid', str(item.selected_audio) ]

        if item['deinterlace'] and config.MPLAYER_VF_INTERLACED:
            additional_args += [ '-vf-pre',  config.MPLAYER_VF_INTERLACED ]
        elif not item['deinterlace'] and config.MPLAYER_VF_PROGRESSIVE:
            additional_args += [ '-vf-pre',  config.MPLAYER_VF_PROGRESSIVE ]
                
        mode = item.mimetype
        if not config.MPLAYER_ARGS.has_key(mode):
            mode = 'default'

        # Mplayer command and standard arguments
        command += [ '-v', '-vo', config.MPLAYER_VO_DEV +
                     config.MPLAYER_VO_DEV_OPTS ]

        # mode specific args
        command += config.MPLAYER_ARGS[mode].split(' ')

        # make the options a list
        command += additional_args

        if hasattr(item, 'is_playlist') and item.is_playlist:
            command.append('-playlist')

        if config.MPLAYER_RESAMPLE_AUDIO and self.item_info and \
               hasattr(self.item_info, 'audio') and self.item_info.audio and \
               hasattr(self.item_info.audio[0], 'samplerate') and \
               self.item_info.audio[0].samplerate and \
               self.item_info.audio[0].samplerate < 40000:
            srate = max(41000, min(self.item_info.audio[0].samplerate * 2, 48000))
            log.info('resample audio from %s to %s',
                     self.item_info.audio[0].samplerate, srate)
            command += [ '-srate', str(srate) ]

        # add the file to play
        command.append(url)

        if options:
            command += options

        # Use software scaler? If not, we also deactivate
        # bmovl because resizing doesn't work
        self.use_bmovl = False
        if '-nosws' in command:
            command.remove('-nosws')

        elif not '-framedrop' in command:
            command += config.MPLAYER_SOFTWARE_SCALER.split(' ')
            self.use_bmovl = True

        # correct avi delay based on mmpython settings
        if config.MPLAYER_SET_AUDIO_DELAY and item.info.has_key('delay') and \
               item.info['delay'] > 0:
            command += [ '-mc', str(int(item.info['delay'])+1), '-delay',
                         '-' + str(item.info['delay']) ]

        while '' in command:
            command.remove('')

        # autocrop
        if config.MPLAYER_AUTOCROP and \
               str(' ').join(command).find('crop=') == -1:
            log.info('starting autocrop')
            (x1, y1, x2, y2) = (1000, 1000, 0, 0)
            crop_cmd = command[1:] + ['-ao', 'null', '-vo', 'null', '-ss',
                                      '60', '-frames', '20', '-vf',
                                      'cropdetect' ]
            child = popen2.Popen3(self.vf_chain(crop_cmd), 1, 100)
            crop = '^.*-vf crop=([0-9]*):([0-9]*):([0-9]*):([0-9]*).*'
            exp = re.compile(crop)
            while(1):
                data = child.fromchild.readline()
                if not data:
                    break
                m = exp.match(data)
                if m:
                    x1 = min(x1, int(m.group(3)))
                    y1 = min(y1, int(m.group(4)))
                    x2 = max(x2, int(m.group(1)) + int(m.group(3)))
                    y2 = max(y2, int(m.group(2)) + int(m.group(4)))
        
            if x1 < 1000 and x2 < 1000:
                command = command + [ '-vf' , 'crop=%s:%s:%s:%s' % \
                                      (x2-x1, y2-y1, x1, y1) ]
            
            child.wait()

        if item.subtitle_file:
            mp, f = util.resolve_media_mountdir(item.subtitle_file)
            if mp:
                mp.mount()
            command += ['-sub', f]

        if item.audio_file:
            mp, f = util.resolve_media_mountdir(item.audio_file)
            if mp:
                mp.mount()
            command += ['-audiofile', f]

        if self.use_bmovl:
            if config.MPLAYER_BMOVL2_POSSIBLE:
                self.overlay = MPlayerOverlay()
                command += [ '-vf', 'bmovl2=%s' % self.overlay.fifo_fname ]
            else:
                self.fifoname = bmovlcanvas.create_fifo()
                command += [ '-vf', 'bmovl=1:0:%s' % self.fifoname ]

        self.plugins = plugin.get('mplayer_video')

        for p in self.plugins:
            command = p.play(command, self)

        command=self.vf_chain(command)

        if plugin.getbyname('MIXER'):
            plugin.getbyname('MIXER').reset()

        self.show()
        self.app = MPlayerApp(command, self)
        self.osd_visible = False

        return None
    

    def stop(self):
        """
        Stop mplayer
        """
        Application.stop(self)
        for p in self.plugins:
            command = p.stop()
        if not self.app:
            return
        self.app.stop('quit\n')
        self.app = None


    def hide_osd(self):
        """
        Hide the seek osd. This is a rc callback after pressing seek
        """
        if not self.osd_visible and self.app and self.app.area_handler:
            self.app.area_handler.hide()
            gui.displays.get().update()
        self._timer_id = None
        return False
        
    def eventhandler(self, event, menuw=None):
        """
        eventhandler for mplayer control. If an event is not bound in this
        function it will be passed over to the items eventhandler
        """
        if not self.app:
            return self.item.eventhandler(event)

        for p in self.plugins:
            if p.eventhandler(event):
                return True

        if event == VIDEO_MANUAL_SEEK:
            from gui import PopupBox
            PopupBox('Seek disabled, press QUIT').show()
            
        if event == STOP:
            self.stop()
            return self.item.eventhandler(event)

        if event == 'AUDIO_ERROR_START_AGAIN':
            self.stop()
            self.play(self.options, self.item)
            return True
        
        if event in ( PLAY_END, USER_END ):
            self.stop()
            return self.item.eventhandler(event)

        if event == VIDEO_SEND_MPLAYER_CMD:
            self.app.write('%s\n' % event.arg)
            return True

        if event == TOGGLE_OSD:
            if not self.use_bmovl:
                # We don't use bmovl so we use the normal mplayer osd
                self.app.write('osd\n')
                return True

            if not self.app.area_handler:
                # Bmovl not ready yet
                return True
            
            self.osd_visible = not self.osd_visible
            if self.osd_visible:
                self.app.area_handler.display_style['video'] = 1
                self.app.area_handler.draw(self.item)
                self.app.area_handler.show()
            else:
                self.app.area_handler.hide()
                gui.displays.get().update()
                self.app.area_handler.display_style['video'] = 0
                self.app.area_handler.draw(self.item)
            return True

        if event == PAUSE or event == PLAY:
            self.app.write('pause\n')
            return True

        if event == SEEK:
            if event.arg > 0 and self.item_length != -1 and \
                   self.dynamic_seek_control:
                # check if the file is growing
                if self.item_info.get_endpos() == self.item_length:
                    # not growing, deactivate this
                    self.item_length = -1

                self.dynamic_seek_control = False

            if event.arg > 0 and self.item_length != -1:
                # safety time for bad mplayer seeking
                seek_safety_time = 20
                if self.item_info['type'] in ('MPEG-PES', 'MPEG-TS'):
                    seek_safety_time = 500

                # check if seek is allowed
                if self.item_length <= self.item.elapsed + event.arg + \
                       seek_safety_time:
                    # get new length
                    self.item_length = self.item_info.get_endpos()
                    
                # check again if seek is allowed
                if self.item_length <= self.item.elapsed + event.arg + \
                       seek_safety_time:
                    log.info('unable to seek %s secs at time %s, length %s' % \
                            (event.arg, self.item.elapsed, self.item_length))
                    return False
                
            if self.use_bmovl and not self.osd_visible:
                if self._timer_id != None:
                    notifier.removeTimer( self._timer_id )
                    self._timer_id = None
                elif self.app.area_handler:
                    self.app.area_handler.show()
                cb = notifier.Callback( self.hide_osd )
                self._timer_id = notifier.addTimer( 2000, cb )
                
            self.app.write('seek %s\n' % event.arg)
            return True

        # nothing found? Try the eventhandler of the object who called us
        return self.item.eventhandler(event)



    def vf_chain(self, command):
        """
        Change a mplayer command to support more than one -vf
        parameter. This function will grep all -vf parameter from
        the command and add it at the end as one vf argument
        """
        ret = []
        vf = ''
        next_is_vf = False
        for arg in command:
            if next_is_vf:
                vf += ',%s' % arg
                next_is_vf = False
            elif (arg == '-vop' or arg == '-vf'):
                next_is_vf=True
            else:
                ret.append(arg)
        if vf:
            return ret + [ '-vf-add', vf[1:] ]
        return ret



# ======================================================================

# ======================================================================

class MPlayerApp( childapp.Instance ):
    """
    class controlling the in and output from the mplayer process
    """

    def __init__(self, app, mplayer):
        self.RE_TIME   = re.compile("^A: *([0-9]+)").match
        self.RE_START  = re.compile("^Starting playback\.\.\.").match
        self.RE_EXIT   = re.compile("^Exiting\.\.\. \((.*)\)$").match
        self.item      = mplayer.item
        self.mplayer   = mplayer
        self.exit_type = None
                       
        # DVD items also store mplayer_audio_broken to check if you can
        # start them with -alang or not
        if hasattr(self.item, 'mplayer_audio_broken') or \
               self.item.mode != 'dvd':
            self.check_audio = 0
        else:
            self.check_audio = 1

        # check for mplayer plugins
        self.stdout_plugins  = []
        self.elapsed_plugins = []
        for p in plugin.get('mplayer_video'):
            if hasattr(p, 'stdout'):
                self.stdout_plugins.append(p)
            if hasattr(p, 'elapsed'):
                self.elapsed_plugins.append(p)

        self.width  = 0
        self.height = 0
        self.screen = None
        self.area_handler = None
        
        # init the child (== start the threads)
        childapp.Instance.__init__( self, app, prio=config.MPLAYER_NICE )

                
    def stop_event(self):
        """
        return the stop event send through the eventhandler
        """
        if self.exit_type == "End of file":
            return PLAY_END
        elif self.exit_type == "Quit":
            return USER_END
        else:
            return PLAY_END


    def start_bmovl(self):
        """
        start bmovl or bmovl2 output
        """
        if config.MPLAYER_BMOVL2_POSSIBLE:
            log.info('starting Bmovl2')
            self.mplayer.overlay.set_can_write(True)
            while not self.mplayer.overlay.can_write():
                pass
            log.info('activating overlay')
            self.screen = gui.displays.set('Bmovl2', (self.width, self.height))
            self.screen.set_overlay(self.mplayer.overlay)
        else:
            log.info('activating bmovl')
            self.screen = gui.displays.set('Bmovl', (self.width, self.height),
                                           self.mplayer.fifoname)
        self.area_handler = gui.areas.Handler('video', ['screen', 'view',
                                                        'info', 'progress'])
        self.area_handler.hide(False)
        self.area_handler.draw(self.item)
        self.write('osd 0\n')
        

    def stdout_cb(self, line):
        """
        parse the stdout of the mplayer process
        """
        # FIXME
        # show connection status for network play
        # if self.item.network_play:
        #     if line.find('Opening audio decoder') == 0:
        #         self.osd.clearscreen(self.osd.COL_BLACK)
        #         self.osd.update()
        #     elif (line.startswith('Resolving ') or \
        #           line.startswith('Connecting to server') or \
        #           line.startswith('Cache fill:')) and \
        #           line.find('Resolving reference to') == -1:
        # 
        #         if line.startswith('Connecting to server'):
        #             line = 'Connecting to server'
        #         self.osd.clearscreen(self.osd.COL_BLACK)
        #         self.osd.drawstringframed(line, config.GUI_OVERSCAN_X+10,
        #              config.GUI_OVERSCAN_Y+10,
        #              self.osd.width - 2 * (config.GUI_OVERSCAN_X+10),
        #              -1, self.osdfont, self.osd.COL_WHITE)
        #         self.osd.update()

        # current elapsed time
        if line.find("A:") == 0:
            if self.width and self.height and not self.screen:
                self.start_bmovl()
            m = self.RE_TIME(line)
            if hasattr(m,'group') and self.item.elapsed != int(m.group(1))+1:
                self.item.elapsed = int(m.group(1))+1
                for p in self.elapsed_plugins:
                    p.elapsed(self.item.elapsed)
                if self.area_handler:
                    self.area_handler.draw(self.item)

        # exit status
        elif line.find("Exiting...") == 0:
            m = self.RE_EXIT(line)
            if m:
                self.exit_type = m.group(1)


        # this is the first start of the movie, parse infos
        elif not self.item.elapsed:
            for p in self.stdout_plugins:
                p.stdout(line)
                
            try:
                if line.find('SwScaler:') ==0 and line.find(' -> ') > 0 and \
                       line[line.find(' -> '):].find('x') > 0:
                    width, height = line[line.find(' -> ')+4:].split('x')
                    if self.height < int(height):
                        self.width  = int(width)
                        self.height = int(height)

                if line.find('Expand: ') == 0:
                    width, height = line[7:line.find(',')].split('x')
                    if self.height < int(height):
                        self.width  = int(width)
                        self.height = int(height)
            except Exception, e:
                log.error(e)

            if self.check_audio:
                if line.find('MPEG: No audio stream found -> no sound') == 0:
                    # OK, audio is broken, restart without -alang
                    self.check_audio = 2
                    self.item.mplayer_audio_broken = True
                    self.mplayer.post_event(Event('AUDIO_ERROR_START_AGAIN'))
                
                if self.RE_START(line):
                    if self.check_audio == 1:
                        # audio seems to be ok
                        self.item.mplayer_audio_broken = False
                    self.check_audio = 0



    def stderr_cb(self, line):
        """
        parse the stderr of the mplayer process
        """
        for p in self.stdout_plugins:
            p.stdout(line)


    def stop(self, cmd=''):
        if self.screen:
            gui.displays.remove(self.screen)
            del self.area_handler
            self.area_handler = None
            self.screen = None
            self.width  = 0
            self.height = 0
        childapp.Instance.stop( self, cmd )
        
