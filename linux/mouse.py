#!/usr/bin/env python2
'''
Copyright (c) 2011, Michael Trunner
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

 1. Redistributions of source code must retain the above copyright notice, this
    list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

from threading import Thread

from Xlib.display import Display
from Xlib.ext import record
from Xlib.protocol import rq
from Xlib import X

import subprocess
import logging

logger = logging.getLogger('GMVD')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s(%(levelname)s): %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


# This var holds the grid as floating point values
# It is used to reinit the grid, when the workspaces have different
# sizes
DEFAULT_GRID = ([0, 0.33, 0.5, 0.67, 1], [0, 0.5, 1])


class Monitor(object):

    def __init__(self, x, y, width, height, grid=DEFAULT_GRID):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._grid = grid
        self._init_grid()

    def _init_grid(self):
        def grid_line(grid, size, offset):
            return int(round(grid * size) + offset)
        x_grid = [grid_line(x, self.width, self.x) \
                  for x in self._grid[0]]
        y_grid = [grid_line(y, self.height, self.y) \
                  for y in self._grid[1]]
        self.grid = (x_grid, y_grid)
        logger.info("x-Grid is %s" % self.grid[0])
        logger.info("y-Grid is %s" % self.grid[1])

    def filter_monitor(self, area):
        if area.x1 < self.x:
            return False
        if area.x2 > self.x + self.width:
            return False
        if area.y1 < self.y:
            return False
        if area.y2 > self.y + self.height:
            return False
        return True


class WindowManager(object):
    def __init__(self, border_padding, monitors=None, metacity=True,
                 maximize=True):
        self.metacity = metacity
        self.max = maximize
        self.set_border_padding(*border_padding)
        self.monitors = monitors
        self.init_desktop()

    def set_border_padding(self, top, left, right, bottom):
        self.border = (top + bottom, left + right)

    def init_desktop(self):
        """
        Collecting informations of the current desktop
        """
        # This function is from stiler (https://github.com/soulfx/stiler)
        desk_output = subprocess.check_output("wmctrl -d", shell=True)
        desk_output = desk_output.strip().split('\n')
        self.desk_list = [line.split()[0] for line in desk_output]

        current = filter(lambda x: x.split()[1] == "*", desk_output)[0].split()

        self.desktop = int(current[0])

        self.viewport = (int(current[5].split(",")[0]),
                         int(current[5].split(",")[1]))

        if not self.monitors:
            width = int(current[8].split("x")[0])
            height = int(current[8].split("x")[1])
            orig_x = int(current[7].split(",")[0])
            orig_y = int(current[7].split(",")[1])
            self.monitors = [Monitor(orig_x, orig_y, width, height)]

    def move_window_to_area(self, area):
        self.init_desktop()
        monitors = [m for m in self.monitors if m.filter_monitor(area)]
        if len(monitors) < 1:
            logger.warning("No monitor for are found")
            return
        if len(monitors) > 1:
            logger.warning("Area is over multiple monitors")
        monitor = monitors[0]
        try:
            posx = max(filter(lambda x: x < area.x1, monitor.grid[0]))
            posy = max(filter(lambda x: x < area.y1, monitor.grid[1]))
            w = min(filter(lambda x: x > area.x2, monitor.grid[0])) - posx
            h = min(filter(lambda x: x > area.y2, monitor.grid[1])) - posy
            logger.info("Moving window to %d, %d, %d, %d" % (posx, posy, w, h))
            max_h = w == monitor.width and self.max
            max_v = h == monitor.height and self.max
            self.move_window(":ACTIVE:", posx, posy, w, h, max_h, max_v)
        except ValueError:
            logger.warning("Mouse area is out of the defined grid layout")
        except Exception:
            logger.exception("Something stupid happens")

    def move_window(self, windowid, x, y, w, h, max_h, max_v):
        """
        Resizes and moves the given window to the given position and dimensions
        """
        # This function is from stiler (https://github.com/soulfx/stiler)
        x = int(x) + self.viewport[0]
        y = int(y) + self.viewport[1]

        h = h - self.border[0]
        w = w - self.border[1]

        if max_h:
            w = -1
        if max_v:
            h = -1

        logging.debug("moving window: %s to (%s,%s,%s,%s) " %
                      (windowid, x, y, w, h))

        if windowid == ":ACTIVE:":
            window = "-r " + windowid
        else:
            window = "-i -r " + windowid

        # unmaximize
        self._call("wmctrl %s -b remove,maximized_vert,maximized_horz"
                   % window)

        # NOTE: metacity doesn't like resizing and moving in the same step
        if self.metacity:
            # resize
            self._call("wmctrl %s -e 0,-1,-1,%i,%i" % (window, w, h))
            # move
            self._call("wmctrl %s -e 0,%i,%i,-1,-1" % (window, max(x, 0),
                                                       max(y, 0)))
        else:
            self._call("wmctrl %s -e 0,%i,%i,%i,%i" % (window,
                                                       max(x, 0), max(y, 0),
                                                       w, h))

        if max_h:
            self._call("wmctrl %s -b add,maximized_horz" % window)
        if max_v:
            self._call("wmctrl %s -b add,maximized_vert" % window)

        # set properties
        command = "wmctrl " + window + " -b remove,hidden,shaded"
        self._call(command)

    def _call(self, cmd):
        logger.debug("Calling OS-CMD: %s" % cmd)
        return subprocess.call(cmd, shell=True)


class Area(object):

    def __init__(self, x, y):
        self.x1 = x
        self.x2 = x
        self.y1 = y
        self.y2 = y
        logger.debug(self)

    def add_point(self, x, y):
        self.x1 = min(x, self.x1)
        self.x2 = max(x, self.x2)
        self.y1 = min(y, self.y1)
        self.y2 = max(y, self.y2)
        logger.debug(self)

    def __str__(self):
        return "Area: (%d, %d - %d, %d)" % (self.x1, self.y1,
                                        self.x2, self.y2)

    def __repr__(self):
        return self.__str__()


class GridMouseVooDoo(Thread):

    def __init__(self, wm, button=10):
        Thread.__init__(self)

        self.button = button

        self.display = Display()
        self.ctx = self.display.record_create_context(
            0,
            [record.AllClients],
            [{
                    'core_requests': (0, 0),
                    'core_replies': (0, 0),
                    'ext_requests': (0, 0, 0, 0),
                    'ext_replies': (0, 0, 0, 0),
                    'delivered_events': (0, 0),
                    'device_events': (X.ButtonPressMask, X.ButtonReleaseMask),
                    'errors': (0, 0),
                    'client_started': False,
                    'client_died': False,
            }])

        self.wm = wm
        self.area = None

    def run(self):
        logger.info("Starting Thread")
        self.display.record_enable_context(self.ctx, self.handler)
        self.display.record_free_context(self.ctx)

    def handler(self, reply):
        logger.debug("Handler called")
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(data,
                                self.display.display, None, None)
            if event.type == X.ButtonPress:
                if event.detail == self.button:
                    self.press(event.root_x, event.root_y)
            elif event.type == X.ButtonRelease:
                if event.detail == self.button:
                    self.release(event.root_x, event.root_y)
            else:
                self.move(event.root_x, event.root_y)

    def stop(self):
        logger.info("Stopping Thread")
        self.display.record_disable_context(self.ctx)
        self.display.ungrab_pointer(X.CurrentTime)
        self.display.flush()
        logger.debug("Thread stopped")

    def press(self, x, y):
        self.area = Area(x, y)
        logger.info("Mouse button pressed")
        self.move(x, y)

    def release(self, x, y):
        self.move(x, y)
        logger.info("%s" % self.area)
        self.wm.move_window_to_area(self.area)
        self.area = None
        logger.info("Mouse button released")

    def move(self, x, y):
        if not self.area:
            logger.debug("Mouse moved to %d, %d but no button pressed" %
                         (x, y))
            return
        self.area.add_point(x, y)
        logger.debug("Mouse moved to %d, %d" % (x, y))


logger.info("Waiting 15 sec for window manager setup")
import time
time.sleep(15)
monitor1 = Monitor(0, 0, 1080, 1920, grid=([0.0, 0.5, 1.0],
                                           [0.0, 0.33, 0.5, 0.67, 1.0]))
monitor2 = Monitor(1080, 245, 1920, 1200, grid=DEFAULT_GRID)
wm = WindowManager((32, 1, 1, 1), monitors=[monitor1, monitor2])
button = 13
gmvd = GridMouseVooDoo(wm, button)
gmvd.start()
