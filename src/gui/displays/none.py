# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# none.py - Hidden display (no output)
# -----------------------------------------------------------------------------
# $Id$
#
# This file defines a Freevo display without any output. It is more or less
# useless, Freevo will switch to that display on shutdown.
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

__all__ = [ 'Display' ]

# mevas imports
from mevas.displays.bitmapcanvas import BitmapCanvas

# display imports
from display import Display as Base


class Display(BitmapCanvas, Base):
    """
    Display class for no output
    """
    def __init__(self, size, default=False):
        BitmapCanvas.__init__(self, size)
        Base.__init__(self)


    def __del__(self):
        """
        Delete the object
        """
        try:
            # __del__ can fail on shutdown
            super(Display, self).__del__(size)
        except:
            pass