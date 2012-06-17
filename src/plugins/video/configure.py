# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# configure.py - Configure video playing
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2012 Dirk Meyer, et al.
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

# kaa imports
import kaa.popcorn

# freevo imports
from ... import core as freevo

class PluginInterface(freevo.ItemPlugin):
    """
    class to configure video playback
    """
    def actions(self, item):
        """
        Return additional actions for the item.
        """
        if item.type == 'video':
            return [ freevo.Action(_('Configure'), self.configure) ]
        return []

    def get_items(self, item):
        return [
            (freevo.ActionItem(_('Player: %s') % item.player, item, self.player_selection))
        ]

    def configure(self, item):
        item.menustack.pushmenu(freevo.Menu(_('Configure'), self.get_items(item), type='submenu'))

    def player_selection(self, item):
        """
        Submenu for player selection.
        """
        if item.player == 'gstreamer':
            item.player = 'mplayer'
        elif item.player == 'mplayer':
            item.player = 'gstreamer'
        item.menustack.current.selected.name = _('Player: %s') % item.player
        item.menustack.current.state += 1
        item.menustack.context.sync(force=True)
