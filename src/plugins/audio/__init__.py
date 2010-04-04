# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# audio - interface between mediamenu and audio
# -----------------------------------------------------------------------------
# $Id$
#
# This file defines the PluginInterface for the audio module of
# Freevo. It will activate the mediamenu for audio.
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, 2003-2009 Dirk Meyer, et al.
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

__all__ = [ 'PluginInterface' ]

# Python imports
import os

# Freevo imports
from ... import core as freevo

# AudioItem
from item import AudioItem, AudioDiskItem


class PluginInterface(freevo.MediaPlugin, freevo.MainMenuPlugin):
    """
    Plugin to handle all kinds of audio items
    """
    possible_media_types = [ 'audio' ]

    def plugin_activate(self, level):
        """
        Activate the plugin.
        """
        # FIXME: fxdparser is currently broken
        # freevo.add_fxdparser(['audio'], 'audio', self.fxdhandler)
        pass

    def suffix(self):
        """
        return the list of suffixes this class handles
        """
        return [ 'beacon:audio' ] + freevo.config.audio.suffix.split(',')

    def get(self, parent, listing):
        """
        return a list of items based on the files
        """
        items = []
        for suffix in self.suffix():
            for file in listing.get(suffix):
                # FIXME: better url detection
                if not file.isfile and not file.isdir and \
                       not file.url.startswith('http'):
                    items.append(AudioDiskItem(file, parent))
                else:
                    items.append(AudioItem(file, parent))
        return items

    def items(self, parent):
        """
        MainMenuPlugin.items to return the audio item.
        """
        return [ freevo.MediaMenu(parent, _('Audio Main Menu'), 'audio', freevo.config.audio.items) ]

    def fxdhandler(node, parent, listing):
        """
        Parse audio specific stuff from fxd files::

          <?xml version="1.0" ?>
          <freevo>
              <audio title="Smoothjazz">
                  <cover-img>foo.jpg</cover-img>
                  <mplayer_options></mplayer_options>
                  <player>xine</player>
                  <playlist/>
                  <reconnect/>
                  <url>http://64.236.34.141:80/stream/1005</url>

                  <info>
                      <genre>JAZZ</genre>
                      <description>A nice description</description>
                  </info>

              </audio>
          </freevo>

        Everything except title and url is optional. If <player> is
        set, this player will be used (possible xine or mplayer). The
        tag <playlist/> signals that this url is a playlist (mplayer
        needs that). <reconnect/> signals that the player should
        reconnect when the connection stopps.

        FIXME: this code is currently broken
        """
        fxd = node
        a = AudioItem('', fxd.getattr(None, 'parent', None))
        a.name = fxd.getattr(node, 'title', a.name)
        a.image = fxd.childcontent(node, 'cover-img')
        a.url = fxd.childcontent(node, 'url')
        if a.image:
            a.image = os.path.join(os.path.dirname(fxd.filename), a.image)
        a.mplayer_options = fxd.childcontent(node, 'mplayer_options')
        if fxd.get_children(node, 'player'):
            a.force_player = fxd.childcontent(node, 'player')
        if fxd.get_children(node, 'playlist'):
            a.is_playlist = True
        if fxd.get_children(node, 'reconnect'):
            a.reconnect = True
        fxd.parse_info(fxd.get_children(node, 'info', 1), a)
        fxd.getattr(None, 'items', []).append(a)