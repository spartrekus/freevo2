# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# interface.py - Base class for input plugins
# -----------------------------------------------------------------------------
# $Id$
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2005 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dischi@freevo.org>
# Maintainer:    Dirk Meyer <dischi@freevo.org>
#
# Please see the file doc/CREDITS for a complete list of authors.
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

__all__ = [ 'InputPlugin' ]


# python imports
import logging

# freevo imports
from freevo.ui import config
from freevo.ui import plugin, input

# get logging object
log = logging.getLogger('input')

class InputPlugin(plugin.Plugin):
    """
    Plugin for input devices such as keyboard and lirc. A plugin of this
    type should be in input/plugins
    """

    def post_key(self, key):
        """
        Send a keyboard event to the event queue
        """
        if not key:
            return None

        for c in (input.get_mapping(), 'global'):
            if not config.EVENTS.has_key(c):
                continue
            if not config.EVENTS[c].has_key(key):
                continue

            return config.EVENTS[c][key].post()

        log.warning('no event mapping for key %s in %s' % (key, input.get_mapping()))