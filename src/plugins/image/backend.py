# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# backend.py - image viewer kaa.candy backend
# -----------------------------------------------------------------------------
# This file is imported by the backend process in the clutter
# mainloop. Importing and using clutter is thread-safe.
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, 2003-2013 Dirk Meyer, et al.
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

__all__ = [ 'PhotoGroup' ]

import os
import tempfile

import kaa
import kaa.imlib2

from gi.repository import Clutter as clutter

# candy backend import
import candy

kaa.register_thread_pool('candy::photo', kaa.ThreadPool())

CENTER = clutter.Point()
CENTER.x = 0.5
CENTER.y = 0.5

class PhotoGroup(candy.Widget):
    """
    Texture
    """
    def create(self):
        """
        Create the clutter object
        """
        self.obj = clutter.Group.new()
        self.obj.show()
        self.textures = {}
        self.current = None

    @kaa.threaded('candy::photo')
    def loadimage_async(self, filename):
        # clutter has problems with large images and may
        # crash. Theerefore, we load the images using kaa.imlib2 and
        # scale them before loading them into clutter.
        i = kaa.imlib2.Image(filename)
        if float(self.width) / self.height < float(i.width) / i.height:
            i = i.scale((self.width, -1))
        else:
            i = i.scale((-1, self.height))
        fd, cachefile = tempfile.mkstemp(prefix='candy', suffix='.png', dir='/dev/shm')
        os.close(fd)
        i.save(cachefile)
        self.loadimage_clutter(filename, cachefile, i.width, i.height)

    @kaa.threaded(kaa.GOBJECT)
    def loadimage_clutter(self, filename, cachefile, width, height):
        t = clutter.Texture.new()
        t.set_from_file(cachefile)
        os.unlink(cachefile)
        self.textures[filename] = t, width, height
        self.showimage()

    def showimage(self):
        if not self.filename in self.textures:
            # not loaded yet, wait
            return
        width, height = self.textures[self.filename][1:]
        factor = 1
        if self.rotation in (90, 270):
            factor = min(float(self.width) / height, float(self.height) / width)
        if self.current != self.textures[self.filename][0]:
            # new photo
            if self.current:
                # TODO: add animation
                self.obj.remove_actor(self.current)
            self.current, width, height = self.textures[self.filename]
            self.current.set_position(0, 0)
            if width < self.width:
                self.current.set_x((self.width - width) / 2)
            if height < self.height:
                self.current.set_y((self.height - height) / 2)
            self.current.set_size(width, height)
            self.current.set_property('pivot-point', CENTER)
            self.current.show()
            self.obj.add_actor(self.current)
            self.current.set_scale(factor, factor)
            self.current.set_property('rotation-angle-z', self.rotation)
            self.current_rotation = self.rotation
        elif self.current_rotation != self.rotation:
            # rotation changed
            if self.rotation == 0 and self.current_rotation == 270:
                self.current.set_property('rotation-angle-z', -90)
            if self.rotation == 270 and self.current_rotation == 0:
                self.current.set_property('rotation-angle-z', 360)
            self.current.animatev(clutter.AnimationMode.EASE_OUT_QUAD, 200,
                   ['rotation-angle-z', 'scale_x', 'scale_y'],
                   [self.rotation, factor, factor])
            self.current_rotation = self.rotation

    def update(self, modified):
        """
        Render the widget (gobject thread)
        """
        super(PhotoGroup, self).update(modified)
        if 'cached' in modified:
            for f in self.cached:
                if not f in self.textures:
                    self.loadimage_async(f)
            for f in self.textures.keys()[:]:
                if not f in self.cached:
                    del self.textures[f]
        if 'filename' in modified or 'rotation' in modified:
            self.showimage()
