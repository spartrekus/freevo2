# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# generic.py - plugin for recording one program with a specific command
# -----------------------------------------------------------------------------
# $Id$
#
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2004 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dmeyer@tzi.de>
# Maintainer:    Dirk Meyer <dmeyer@tzi.de>
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
import time
import os
import string
import logging

# notifier
import notifier

# freevo imports
import config
from util.popen import Process

# record imports
from record.recorder import Plugin
from record.types import *

# get logging object
log = logging.getLogger('record')

class Childapp(Process):
    """
    ChildApp wrapper for use inside a recorder plugin
    """
    def __init__(self, app, control):
        """
        Init the childapp
        """
        Process.__init__(self, app)
        self.control = control


    def finished(self):
        """
        Callback when the child died
        """
        self.control.stopped()
        self.control = None



class PluginInterface(Plugin):
    """
    Generic plugin. This plugin is sometimes too generic, so other plugins
    like dvb inherit from it. This plugin can only handle recording one
    item at a time using one specific application to do so.
    """
    def __init__(self):
        # set a nice name for debug
        if not hasattr(self, 'name'):
            self.reason = 'record.generic can\'t be used directly'
            return
        Plugin.__init__(self)
        log.info('plugin: activating %s record' % self.name)
        # childapp running the external program
        self.app  = None
        # recording item
        self.item = None
        # timer for stop the child when it's all done
        self.stop_timer = None
        # the recordings scheduled by the plugin
        self.recordings = []
        # timer for next recording
        self.rec_timer = None
        # suffix for filename
        self.suffix = '.suffix'


    def get_cmd(self, rec):
        """
        Build the command to record. A class which inherits from the plugin
        should override this function.
        """
        raise Exception('generic: get_cmd() missing')


    def get_channel_list(self):
        raise Exception('generic: get_channel_list() missing')
    

    def schedule(self, recordings, server=None):
        """
        Function called from the server. This function updates the
        recordings scheduled by the plugin.
        """
        if self.item and not self.item in recordings:
            log.info('%s.schedule: recording item no longer in list' % \
                     self.name)
            self.stop()
        self.recordings = recordings
        if server:
            self.server = server

        if self.rec_timer:
            notifier.removeTimer(self.rec_timer)
            self.rec_timer = None

        if not self.recordings:
            log.info('%s.schedule: nothing scheduled' % self.name)
            return
        
        # sort by start time
        recordings.sort(lambda l, o: cmp(l.start,o.start))
        if recordings[0].status == RECORDING:
            # the first one is running right now, so the timer
            # should be set to the next one
            if len(self.recordings) == 1:
                log.info('%s.schedule: already scheduled' % self.name)
                return
            log.info('%s.schedule: currently recording' % self.name)
            rec0 = recordings[0]
            rec1 = recordings[1]
            # get end time of current recording incl. padding
            end = rec0.stop + rec0.stop_padding
            if end < rec1.start - rec1.start_padding:
                # both recordings don't overlap at the start time
                start = rec1.start - rec1.start_padding
            else:
                # recordings overlap in the padding
                # start new recording with mimimum padding possible
                start = min(end, rec1.start)
        else:
            rec   = recordings[0]
            start = rec.start - rec.start_padding
            
        secs = max(0, int(start - time.time()))
        log.info('%s.schedule: next in %s sec' % (self.name, secs))
        
        self.rec_timer = notifier.addTimer(secs * 1000, self.record)



    def record(self):
        """
        Record the next item in the recordings list. If the first is
        currently recording, stop the recording and record the next.
        """
        # remove the timer, just to be sure
        notifier.removeTimer(self.rec_timer)
        self.rec_timer = None

        if self.item:
            log.info('%s.record: there is something running, stopping it' % \
                     self.name)
            self.stop()
            # return here, this function gets called by notifier using the
            # new rec_timer at once because stop() called schedule again.
            return False

        rec = self.recordings[0]
        rec.status = 'recording'
            
        # create a filename if it is missing
        if not rec.url:
            filename_array = { 'progname': String(rec.name),
                               'title'   : String(rec.subtitle) }

            filemask = config.TV_RECORDFILE_MASK % filename_array
            filename = ''
            for letter in time.strftime(filemask, time.localtime(rec.start)):
                if letter in string.ascii_letters + string.digits:
                    filename += letter
                elif filename and filename[-1] != '_':
                    filename += '_'
            filename = filename.rstrip(' -_:') + self.suffix
            rec.url = 'file:' + os.path.join(config.TV_RECORD_DIR, filename)
        else:
            # check filename
            if rec.url.startswith('file:'):
                rec.url = os.path.join(config.TV_RECORD_DIR, rec.url[5:])
                if rec.url.endswith('.suffix'):
                    rec.url = os.path.splitext(rec.url)[0] + self.suffix
                rec.url = 'file:' + rec.url
        if rec.url.startswith('file:'):
            # check if target dir exists
            d = os.path.dirname(rec.url[5:])
            if not os.path.isdir(d):
                os.makedirs(d)
        # get the cmd for the childapp
        cmd = self.get_cmd(rec)
        self.item = rec
        self.app = Childapp(cmd, self)
        rec.recorder = self

        # Set auto stop for stop time + padding + 10 secs
        if self.stop_timer:
            notifier.removeTimer(self.stop_timer)
        timer = max(0, int(rec.stop + rec.stop_padding + 10 - time.time()))
        log.info('%s.record: add stop timer for %s sec' % (self.name, timer))
        self.stop_timer = notifier.addTimer(timer * 1000, self.stop)

        # Create fxd file now, even if we don't know if it is working. It
        # will be deleted later when there is a problem
        self.create_fxd(rec)

        # schedule next recording
        self.schedule(self.recordings)

        if self.server:
            # FIXME: find a better way to notify the server
            self.server.send_update()

        return False
    

    def stop(self):
        """
        Stop the current running recording
        """
        if not self.item:
            # nothing to stop here
            return False
        log.info('%s.stop: stop recording: %s' % \
                 (self.name, String(self.item.name)))
        # remove the stop timer, we don't need it anymore
        notifier.removeTimer(self.stop_timer)
        self.stop_timer = None
        # stop the application
        self.app.stop()
        return False


    def stopped(self):
        """
        Callback when the recording has stopped
        """
        if self.stop_timer:
            notifier.removeTimer(self.stop_timer)
        if self.item.url.startswith('file:'):
            filename = self.item.url[5:]
            if os.path.isfile(filename):
                self.item.status = SAVED
                self.create_thumbnail(self.item)
            else:
                self.item.status = FAILED
                self.delete_fxd(self.item)
        else:
            self.item.status = 'done'
        log.info('%s.stopped: recording finished, new status' % self.name)
        log.info(str(self.item))
        if self.server:
            # FIXME: find a better way to notify the server
            self.server.send_update()
        self.server.save()
        self.item.recorder = None
        self.item = None
        self.app = None
        # reset our timer by calling schedule again with the shorter list
        self.schedule(self.recordings[1:])
