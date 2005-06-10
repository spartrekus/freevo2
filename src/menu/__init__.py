# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# menu.py - freevo menu handling system
# -----------------------------------------------------------------------------
# $Id$
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2004 Krister Lagerstrom, Dirk Meyer, et al.
#
# First edition: Krister Lagerstrom <krister-freevo@kmlager.com>
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

# menu imports
from file import FileInformation
from item import Item
from mediaitem import MediaItem
from action import Action
from menu import Menu
from widget import MenuWidget

class MenuItem(Item):
    """
    Default item for the menu. It includes one action.
    WARNING: this class may be deleted in the future!
    """
    def __init__( self, name, action=None, arg=None, type=None, image=None,
                  icon=None, parent=None):
        Item.__init__(self, parent)
        if name:
            self.name = Unicode(name)
        if icon:
            self.icon = icon
        if image:
            self.image = image

        self.type = type
        self.action = Action(name, action)
        self.action.parameter(arg=arg)


    def actions(self):
        """
        return the default action
        """
        return [ self.action ]