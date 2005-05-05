# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# rom_drives.py - the Freevo identifymedia/automount plugin
# -----------------------------------------------------------------------------
# $Id$
#
# Note: this file uses threads. All calls are wrapped around the fthread util
# to make it look like a normal function call. The reason for this is that
# ioctls and simple reads on rom drives may take a long time and we need to
# keep the notifier alive. Setting the fd to non blovk also doesn't help here.
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
import os
import re
import copy
import struct
import array
import logging

import notifier

# freevo imports
import sysconfig
import config
import eventhandler
import plugin
import util
import util.ioctl
import util.fthread
import mediadb

from event import *
from directory import DirItem
from gui import PopupBox
from item import Item

# FIXME: use Mimetype for this
from audio.audiodiskitem import AudioDiskItem
from video.videoitem import VideoItem


# the logging object
log = logging.getLogger()

# detect the rom drives
config.detect('rom_drives')

try:
    from CDROM import *
    # test if CDROM_DRIVE_STATUS is there
    # (for some strange reason, this is missing sometimes)
    CDROM_DRIVE_STATUS
except:
    if os.uname()[0] == 'FreeBSD':
        # FreeBSD ioctls - there is no CDROM.py...
        CDIOCEJECT = 0x20006318
        CDIOCCLOSE = 0x2000631c
        CDIOREADTOCENTRYS = 0xc0086305L
        CD_LBA_FORMAT = 1
        CD_MSF_FORMAT = 2
        CDS_NO_DISC = 1
        CDS_DISC_OK = 4
    else:
        # strange ioctls missing
        CDROMEJECT = 0x5309
        CDROMCLOSETRAY = 0x5319
        CDROM_DRIVE_STATUS = 0x5326
        CDROM_SELECT_SPEED = 0x5322
        CDS_NO_DISC = 1
        CDS_DISC_OK = 4


LABEL_REGEXP = re.compile("^(.*[^ ]) *$").match


# Watcher
watcher = None

# list of rom drives
rom_drives = []

def ioctl(*args, **kwargs):
    """
    Ioctl wrapper using fthread because ioctls on rom drives block
    for unknown time.
    """
    return util.fthread.call(util.ioctl.ioctl, *args, **kwargs)



class autostart(plugin.DaemonPlugin):
    """
    Plugin to autostart if a new medium is inserted while Freevo shows
    the main menu
    """
    def eventhandler(self, event = None):
        """
        eventhandler to handle the IDENTIFY_MEDIA plugin event and the
        EJECT event
        """
        if not eventhandler.is_menu():
            return False
        menuw = eventhandler.get()
        # if we are at the main menu and there is an IDENTIFY_MEDIA event,
        # try to autorun the media
        if plugin.isevent(event) == 'IDENTIFY_MEDIA' and menuw and \
               len(menuw.menustack) == 1 and not event.arg[1]:
            media = event.arg[0]
            if media.item:
                media.item.parent = menuw.menustack[0].selected
            if media.item and media.item.actions():
                if media.type == 'audio':
                    # disc marked as audio, play everything
                    if media.item.type == 'dir':
                        media.item.play_recursive(menuw=menuw)
                    elif media.item.type == 'audiocd':
                        media.item.play(menuw=menuw)
                    else:
                        media.item.actions()[0][0](menuw=menuw)
                elif media.videoitem:
                    # disc has one video file, play it
                    media.videoitem.actions()[0][0](menuw=menuw)
                else:
                    # ok, do whatever this item has to offer
                    media.item.actions()[0][0](menuw=menuw)
            else:
                menuw.refresh()
            return True

        # Handle the EJECT key for the main menu
        elif event == EJECT and menuw and len(menuw.menustack) == 1:
            # Are there any drives defined?
            if rom_drives:
                # The default is the first drive in the list
                media = rom_drives[0]
                media.move_tray(dir='toggle')
                return True


class rom_items(plugin.MainMenuPlugin):
    """
    Plugin to add the rom drives to a main menu. This can be the global main
    menu or most likely the video/audio/image/games main menu
    """
    def items(self, parent):
        """
        return the list of rom drives
        """
        items = []
        for media in rom_drives:
            if media.item:
                if parent.display_type == 'video' and media.videoitem:
                    m = media.videoitem
                    # FIXME: how to play video is maybe subdirs?

                else:
                    if media.item.type == 'dir':
                        media.item.display_type = parent.display_type
                        media.item.skin_display_type = parent.display_type
                    m = media.item

            else:
                m = Item(parent)
                m.name = _('Drive %s (no disc)') % media.drivename
                m.type = media.type
                m.media = media
                media.item = m

            m.parent = parent
            m.eventhandler_plugins.append(self.items_eventhandler)
            items.append(m)

        return items


    def items_eventhandler(self, event, item, menuw):
        """
        handle EJECT for the rom drives
        """
        if event == EJECT and item.media and menuw and \
           menuw.menustack[1] == menuw.menustack[-1]:
            item.media.move_tray(dir='toggle')
            return True
        return False


class RemovableMedia(vfs.Mountpoint):
    """
    Object about one drive
    """
    def __init__(self, mountdir='', devicename='', drivename=''):
        # This is read-only stuff for the drive itself
        vfs.Mountpoint.__init__(self, mountdir, devicename, 'empty_cdrom')
        self.drivename = drivename
        rom_drives.append(self)
        
        # Dynamic stuff
        self.tray_open = 0
        self.drive_status = None  # return code from ioctl for DRIVE_STATUS

        self.label     = ''
        self.info      = None
        self.item      = None
        self.videoitem = None
        self.locked    = False


    def is_tray_open(self):
        """
        return tray status
        """
        return self.tray_open


    def move_tray(self, dir='toggle', notify=1):
        """
        Move the tray. dir can be toggle/open/close
        """
        if dir == 'toggle':
            if self.is_tray_open():
                dir = 'close'
            else:
                dir = 'open'

        if dir == 'open':
            log.debug('Ejecting disc in drive %s' % self.drivename)

            if notify:
                pop = PopupBox(text=_('Ejecting disc in drive %s') % \
                               self.drivename)
                pop.show()

            try:
                fd = os.open(self.devicename, os.O_RDWR | os.O_NONBLOCK)

                if os.uname()[0] == 'FreeBSD':
                    ioctl(fd, CDIOCEJECT, 0)
                else:
                    ioctl(fd, CDROMEJECT)
                os.close(fd)
            except Exception, e:
                try:
                    log.exception('eject cdrom')
                except IOError:
                    # believe it or not, this sometimes causes an IOError if
                    # you've got a music track playing in the background
                    # (detached)
                    pass
                # maybe we need to close the fd if ioctl fails, maybe
                # open fails and there is no fd
                try:
                    os.close(fd)
                except:
                    pass

            self.tray_open = 1
            if notify:
                pop.destroy()


        elif dir == 'close':
            log.debug('Inserting %s' % self.drivename)

            if notify:
                pop = PopupBox(text=_('Reading disc in drive %s') % \
                               self.drivename)
                pop.show()

            # close the tray, identifymedia does the rest,
            # including refresh screen
            try:
                fd = os.open(self.devicename, os.O_RDONLY | os.O_NONBLOCK)
                if os.uname()[0] == 'FreeBSD':
                    s = ioctl(fd, CDIOCCLOSE, 0)
                else:
                    s = ioctl(fd, CDROMCLOSETRAY)
                os.close(fd)
            except Exception, e:
                log.exception('close tray')
                # maybe we need to close the fd if ioctl fails, maybe
                # open fails and there is no fd
                try:
                    os.close(fd)
                except:
                    pass

            self.tray_open = 0
            if watcher:
                watcher.check_all()
            if notify:
                pop.destroy()


    def check_status(self):
        """
        Return True if the status has changed (new disc / removed disc).
        """
        # Check drive status (tray pos, disc ready)
        try:
            CDSL_CURRENT = ( (int ) ( ~ 0 >> 1 ) )
            fd = os.open(self.devicename, os.O_RDONLY | os.O_NONBLOCK)
            if os.uname()[0] == 'FreeBSD':
                try:
                    data = array.array('c', '\000'*4096)
                    (address, length) = data.buffer_info()
                    buf = struct.pack('BBHP', CD_MSF_FORMAT, 0,
                                      length, address)
                    # use unthreader ioctl here, it is fast
                    s = util.ioctl.ioctl(fd, CDIOREADTOCENTRYS, buf)
                    s = CDS_DISC_OK
                except:
                    s = CDS_NO_DISC
            else:
                # use unthreader ioctl here, it is fast
                s = util.ioctl.ioctl(fd, CDROM_DRIVE_STATUS, CDSL_CURRENT)
        except:
            # maybe we need to close the fd if ioctl fails, maybe
            # open fails and there is no fd
            try:
                os.close(fd)
            except:
                pass
            self.drive_status = None
            return False

        # Same as last time? If so we're done
        if s == self.drive_status:
            os.close(fd)
            return False

        self.drive_status = s

        self.set_id('')
        self.label     = ''
        self.type      = 'empty_cdrom'
        self.item      = None
        self.videoitem = None

        # Is there a disc present?
        if s != CDS_DISC_OK:
            os.close(fd)
            return False

        # if there is a disc, the tray can't be open
        self.tray_open = False
        return True


    def scan(self):
        """
        Scan the disc (running in a thread)
        """
        self.info = mediadb.get(self)
        if config.ROM_SPEED and not self.info['mime'] == 'video/dvd':
            # try to set the speed
            fd = os.open(self.devicename, os.O_RDONLY | os.O_NONBLOCK)
            try:
                ioctl(fd, CDROM_SELECT_SPEED, config.ROM_SPEED)
            except:
                pass
            os.close(fd)
        return self
    



class Watcher:
    """
    Object to watch the rom drives for changes
    """
    def __init__(self):
        self.rebuild_file = sysconfig.cachefile('freevo-rebuild-database')
        self.locked = False

        # Add the drives to the config.removable_media list. There doesn't have
        # to be any drives defined.
        if config.ROM_DRIVES != None:
            for i in range(len(config.ROM_DRIVES)):
                (dir, device, name) = config.ROM_DRIVES[i]
                media = RemovableMedia(mountdir=dir, devicename=device,
                                       drivename=name)
                # close the tray without popup message
                media.move_tray(dir='close', notify=0)

        # Remove the ROM_DRIVES member to make sure it is not used by
        # legacy code!
        del config.ROM_DRIVES

        # register callback
        notifier.addTimer(2000, self.poll)


    def unlock_and_send_update(self, media):
        log.debug('MEDIA: Status=%s' % media.drive_status)
        log.debug('Posting IDENTIFY_MEDIA event')
        if hasattr(media, 'already_scanned'):
            arg = (media, False)
        else:
            media.already_scanned = True
            arg = (media, True)
        eventhandler.post(plugin.event('IDENTIFY_MEDIA', arg=arg))
        media.locked = False
        

    def identify(self, media):
        """
        magic!
        Try to find out as much as possible about the disc in the
        rom drive: title, image, play options, ...
        """
        disc_info = media.info
        if not disc_info.disc_ok:
            # bad disc, e.g. blank disc.
            return

        if disc_info['mime'] == 'audio/cd':
            disc_id = disc_info['id']
            media.item = AudioDiskItem(disc_id, parent=None,
                                       devicename=media.devicename,
                                       display_type='audio')
            media.type = media.item.type
            media.item.media = media
            if disc_info['title']:
                media.item.name = disc_info['title']
            media.item.info = disc_info
            self.unlock_and_send_update(media)

        image = title = movie_info = more_info = fxd_file = None

        media.set_id(disc_info['id'])
        media.label = disc_info['label']
        media.type  = 'cdrom'

        label = disc_info['label']

        # is the id in the database?
        for mimetype in plugin.mimetype():
            if not mimetype.database():
                continue
            movie_info = mimetype.database().get_media(media)
            if movie_info:
                title = movie_info.name
                image = movie_info.image
                break

        # DVD/VCD/SVCD:
        # There is disc_info from mmpython for these three types
        if disc_info['mime'] in ('video/vcd', 'video/dvd'):
            if not title:
                title = media.label.replace('_', ' ').lstrip().rstrip()
                title = '%s [%s]' % (disc_info['mime'][6:].upper(), title)

            if movie_info:
                media.item = copy.copy(movie_info)
            else:
                media.item = VideoItem('', None)
                f = os.path.join(config.OVERLAY_DIR, 'disc-set', media.id)
                media.item.image = util.getimage(f)
            variables = media.item.info.get_variables()
            media.item.name  = title
            media.item.media = media
            media.item.set_url(disc_info)
            media.item.info.set_variables(variables)
            media.type = disc_info['mime'][6:]
            self.unlock_and_send_update(media)
            return
        
        # Check for movies/audio/images on the disc
        video_files = util.find_matches(disc_info['listing'],
                                        config.VIDEO_SUFFIX)
        num_video = len(video_files)

        num_audio = len(util.find_matches(disc_info['listing'],
                                          config.AUDIO_SUFFIX))
        num_image = len(util.find_matches(disc_info['listing'],
                                          config.IMAGE_SUFFIX))
        
        media.item = DirItem(disc_info, None)
        media.item.info = disc_info

        # if there is a video file on the root dir of the disc, we guess
        # it's a video disc. There may also be audio files and images, but
        # they only belong to the movie
        if video_files:
            media.type = 'video'

            # try to find out if it is a series cd
            if not title:
                show_name = ""
                the_same  = 1
                volumes   = ''
                start_ep  = 0
                end_ep    = 0

                video_files.sort(lambda l, o: cmp(l.upper(), o.upper()))

                for movie in video_files:
                    if config.VIDEO_SHOW_REGEXP_MATCH(movie):
                        bn = os.path.basename(movie)
                        show = config.VIDEO_SHOW_REGEXP_SPLIT(bn)

                        if show_name and show_name != show[0]:
                            the_same = 0
                        if not show_name:
                            show_name = show[0]
                        if volumes:
                            volumes += ', '
                        current_ep = int(show[1]) * 100 + int(show[2])
                        if end_ep and current_ep == end_ep + 1:
                            end_ep = current_ep
                        elif not end_ep:
                            end_ep = current_ep
                        else:
                            end_ep = -1
                        if not start_ep:
                            start_ep = end_ep
                        volumes += show[1] + "x" + show[2]

                if show_name and the_same and config.VIDEO_SHOW_DATA_DIR:
                    if end_ep > 0:
                        volumes = '%dx%02d - %dx%02d' % (start_ep / 100,
                                                         start_ep % 100,
                                                         end_ep / 100,
                                                         end_ep % 100)
                    k = config.VIDEO_SHOW_DATA_DIR + show_name
                    if os.path.isfile((k + ".png").lower()):
                        image = (k + ".png").lower()
                    elif os.path.isfile((k + ".jpg").lower()):
                        image = (k + ".jpg").lower()
                    title = show_name + ' ('+ volumes + ')'
                    for mimetype in plugin.mimetype():
                        if not mimetype.database() or \
                               not hasattr(mimetype.database(), 'tv_show'):
                            continue
                        tv_show = mimetype.database().tv_show
                        if tv_show.has_key(show_name.lower()):
                            tvinfo = tv_show[show_name.lower()]
                            more_info = tvinfo[1]
                            if not image:
                                image = tvinfo[0]
                            if not fxd_file:
                                fxd_file = tvinfo[3]

                elif (not show_name) and len(video_files) == 1:
                    movie = video_files[0]
                    title = os.path.splitext(os.path.basename(movie))[0]

            # nothing found, give up: return the label
            if not title:
                title = label


        # If there are no videos and only audio files (and maybe images)
        # it is an audio disc (autostart will auto play everything)
        elif not num_video and num_audio:
            media.type = 'audio'
            title = '%s [%s]' % (media.drivename, label)

        # Only images? OK than, make it an image disc
        elif not num_video and not num_audio and num_image:
            media.type = 'image'
            title = '%s [%s]' % (media.drivename, label)

        # Mixed media?
        elif num_video or num_audio or num_image:
            media.type = None
            title = '%s [%s]' % (media.drivename, label)

        # Strange, no useable files
        else:
            media.type = None
            title = '%s [%s]' % (media.drivename, label)


        # set the infos we have now
        if title:
            media.item.name = title

        if image:
            media.item.image = image

        if more_info:
            media.item.info.set_variables(more_info)

        if fxd_file and not media.item.fxd_file:
            media.item.set_fxd_file(fxd_file)


        # One video in the root dir. This sounds like a disc with one
        # movie on it. Save the information about it and autostart will
        # play this.
        if len(video_files) == 1 and media.item['num_dir_items'] == 0:
            media.mount()
            if movie_info:
                media.videoitem = copy.deepcopy(movie_info)
            else:
                media.videoitem = VideoItem(video_files[0], None)
            media.umount()
            media.videoitem.media    = media
            media.videoitem.media_id = media.id

            # set the infos we have
            if title:
                media.videoitem.name = title

            if image:
                media.videoitem.image = image

            if more_info:
                media.videoitem.set_variables(more_info)

            if fxd_file:
                media.videoitem.fxd_file = fxd_file

        media.item.media = media
        self.unlock_and_send_update(media)
        return True


    def check_all(self):
        """
        check all drives
        """
        if not eventhandler.is_menu():
            # Some app is running, do not scan, it's not necessary
            return

        for media in rom_drives:
            if media.locked:
                # scan waiting in thread
                continue
            media.locked = True
            last_status = media.drive_status
            if last_status == None:
                first_scan = True
            else:
                first_scan = False
            if media.check_status():
                util.fthread.Thread(self.identify, media.scan).start()
                continue

            # release the lock again
            media.locked = False
                
            if last_status != media.drive_status:
                self.unlock_and_send_update(media)


    def poll(self):
        """
        Poll function
        """
        if self.locked:
            return True
        self.locked = True
        # Check if we need to update the database
        # This is a simple way for external apps to signal changes
        if os.path.exists(self.rebuild_file):
            for mimetype in plugin.mimetype():
                if mimetype.database():
                    if not mimetype.database().update():
                        # something is wrong, deactivate this feature
                        self.rebuild_file = '/this/file/should/not/exist'

            for media in rom_drives:
                media.drive_status = None

        if eventhandler.is_menu():
            # check only in the menu
            self.check_all()

        self.locked = False
        # check if we need to stop
        if hasattr(self, 'stop'):
            return False
        return True


# start the watcher
watcher = Watcher()
