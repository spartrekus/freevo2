# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# imageitem.py - Item for image files
# -----------------------------------------------------------------------------
# $Id$
#
# An ImageItem is an Item handling image files for Freevo. It will use
# the viewer in viewer.py to display the image
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, 2003-2007 Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dischi@freevo.org>
# Maintainer:    Dirk Meyer <dischi@freevo.org>
#
# Please see the file AUTHORS for a complete list of authors.
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

__all__ = [ 'ImageItem' ]

# python imports
import time

# freevo imports
from freevo.ui import config
from freevo.ui.menu import MediaItem, Action
from freevo.ui.event import PLAY_END, STOP
from viewer import viewer

class ImageItem(MediaItem):
    """
    An item for image files
    """
    type = 'image'

    def __init__(self, url, parent, duration = config.image.viewer.duration):
        MediaItem.__init__(self, parent)
        self.user_stop = False
        # set url and parse the name
        self.set_url(url)
        self.duration = duration


    def get_geometry(self):
        """
        Return width x height of the image or None
        """
        if self.get('width') and self.get('height'):
            return '%sx%s' % (self.get('width'), self.get('height'))
        return None


    def actions(self):
        """
        Return a list of possible actions on this item.
        """
        return [ Action(_('View Image'), self.play) ]


    def cache(self):
        """
        Caches (loads) the next image
        """
        viewer.cache(self)


    def play(self):
        """
        View the image
        """
        viewer.view(self)


    def stop(self):
        """
        Stop viewing this item
        """
        viewer.stop()


    def eventhandler(self, event):
        """
        eventhandler for this item
        """
        if event == STOP:
            self.user_stop = True
        if event == PLAY_END:
            if not self.user_stop:
                self['last_played'] = int(time.time())
                self.user_stop = False
        return MediaItem.eventhandler(self, event)
