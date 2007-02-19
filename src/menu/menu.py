# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# menu.py - a page for the menu stack
# -----------------------------------------------------------------------------
# $Id$
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

__all__ = [ 'Menu' ]

# python imports
import logging

# kaa imports
from kaa.weakref import weakref

# freevo imports
from freevo.ui.config import config
from freevo.ui.event import *

# menu imports
from item import Item
from listing import ItemList

# get logging object
log = logging.getLogger()

class Menu(ItemList):
    """
    A Menu page with Items for the MenuStack. It is not allowed to change
    the selected item or the internal choices directly, use 'select',
    'set_items' or 'change_item' to do this.
    """
    next_id = 0

    def __init__(self, heading, choices=[], reload_func = None, type = None):
        ItemList.__init__(self, choices)

        self.heading = heading
        self.stack   = None

        # unique id of the menu object
        Menu.next_id += 1
        self.id = Menu.next_id
        # position in the menu stack
        self.pos = -1

        # special items for the new skin to use in the view or info
        # area. If None, menu.selected will be taken
        self.infoitem = None
        self.viewitem = None

        # Called when a child menu returns. This function returns a new menu
        # or None and the old menu will be reused
        self.reload_func = reload_func
        self.type = type

        # Menu type
        self.submenu = False

        # Reference to the item that created this menu
        self.item = None

        # Autoselect menu if it has only one item
        self.autoselect = False

        # how many rows and cols does the menu has
        # (will be changed by the skin code)
        self.cols = 1
        self.rows = 1


    def set_items(self, items, refresh=True):
        """
        Set/replace the items in this menu. If refresh is True, the menu
        stack will be refreshed and redrawn.
        """
        # delete ref to menu for old choices
        for c in self.choices:
            c.menu = None

        # set new choices and selection
        ItemList.set_items(self, items)

        # set menu (self) pointer to the items
        sref = weakref(self)
        for c in self.choices:
            c.menu = sref

        if refresh and self.stack:
            self.stack.refresh()


    def change_item(self, old, new):
        """
        Replace the item 'old' with the 'new'.
        """
        ItemList.change_item(self, old, new)
        old.menu = None
        new.menu = weakref(self)


    def eventhandler(self, event):
        """
        Handle events for this menu page.
        """

        if not self.choices:
            return False

        if self.cols == 1:
            if config.menu.arrow_navigation:
                if event == MENU_LEFT:
                    event = MENU_BACK_ONE_MENU
                elif event == MENU_RIGHT:
                    event = MENU_SELECT
            else:
                if event == MENU_LEFT:
                    event = MENU_PAGEUP
                elif event == MENU_RIGHT:
                    event = MENU_PAGEDOWN

        if self.rows == 1:
            if event == MENU_LEFT:
                event = MENU_UP
            if event == MENU_RIGHT:
                event = MENU_DOWN

        if event == MENU_UP:
            self.select(-self.cols)
            return True

        if event == MENU_DOWN:
            self.select(self.cols)
            return True

        if event == MENU_PAGEUP:
            self.select(-(self.rows * self.cols))
            return True

        if event == MENU_PAGEDOWN:
            self.select(self.rows * self.cols)
            return True

        if event == MENU_LEFT:
            self.select(-1)
            return True

        if event == MENU_RIGHT:
            self.select(1)
            return True

        if event == MENU_PLAY_ITEM and hasattr(self.selected, 'play'):
            self.selected.play()
            return True

        if event == MENU_CHANGE_SELECTION:
            self.select(event.arg)
            return True

        if event == MENU_SELECT or event == MENU_PLAY_ITEM:
            actions = self.selected.get_actions()
            if not actions:
                OSD_MESSAGE.post(_('No action defined for this choice!'))
            else:
                actions[0]()
            return True

        if event == MENU_SUBMENU:
            if self.submenu or not self.stack:
                return False

            actions = self.selected.get_actions()
            if not actions or len(actions) <= 1:
                return False
            items = []
            for action in actions:
                items.append(Item(self.selected, action))

            # FIXME: remove this for loop
            for i in items:
                if not self.selected.type == 'main':
                    i.image = self.selected.image
                if hasattr(self.selected, 'display_type'):
                    i.display_type = self.selected.display_type
                else:
                    i.display_type = self.selected.type

            s = Menu(self.selected.name, items)
            s.submenu = True
            s.item = self.selected
            self.stack.pushmenu(s)
            return True

        if event == MENU_CALL_ITEM_ACTION:
            log.info('calling action %s' % event.arg)
            for action in self.selected.get_actions():
                if action.shortcut == event.arg:
                    action()
                    return True
            log.info('action %s not found' % event.arg)
            return True

        return False
