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


class WindowManager(object):
    # Most of that functions are from stiler (https://github.com/soulfx/stiler)
    def __init__(self, (xgrid, ygrid), (top, bottom, left, right),
                 metacity=True):
        """
        Collecting informations of desktops and windows
        """
        # This function is from stiler (https://github.com/soulfx/stiler)
        desk_output = subprocess.check_output("wmctrl -d", shell=True)
        desk_output = desk_output.strip().split('\n')
        self.desk_list = [line.split()[0] for line in desk_output]

        current = filter(lambda x: x.split()[1] == "*" , desk_output)[0].split()

        self.desktop = int(current[0])

        width = int(current[8].split("x")[0])
        height = int(current[8].split("x")[1])
        self.size = (width, height)

        orig_x = int(current[7].split(",")[0])
        orig_y = int(current[7].split(",")[1])
        self.offset = (orig_x, orig_y)
        self.border = (top + bottom, left + right)

        logger.info("Desktop dimensions are: (%d, %d)  (%d, %d)" % (orig_x,
                                                                    orig_y,
                                                                    width,
                                                                    height))
        self.grid = (map(lambda x: int(round(x * width)), xgrid),
                     map(lambda y: int(round(y * height)), ygrid))

        logger.info("x-Grid is %s" % self.grid[0])
        logger.info("y-Grid is %s" % self.grid[1])
        self.metacity = metacity
        self.max = True


    def windows(self):
        # This function is from stiler (https://github.com/soulfx/stiler)
        win_output = subprocess.check_output("wmctrl -lG", shell=True)
        win_output = win_output.strip().split("\n")
        win_list = {}

        for desk in self.desk_list:
            win_list[desk] = map(lambda y: hex(int(y.split()[0], 16)),
                                filter(lambda x: x.split()[1] == desk,
                                       win_output))
        return win_list


    def move_window_to_area(self, area):
        try:
            posx = max(filter(lambda x: x < area.x1, self.grid[0]))
            posy = max(filter(lambda x: x < area.y1, self.grid[1]))
            w = min(filter(lambda x: x > area.x2, self.grid[0])) - posx
            h = min(filter(lambda x: x > area.y2, self.grid[1])) - posy
            logger.info("Moving window to %d, %d, %d, %d" % (posx, posy, w, h))
            self.move_window(":ACTIVE:", posx, posy, w, h)
        except Exception as e:
            print e


    def move_window(self, windowid, x, y, w, h):
        """
        Resizes and moves the given window to the given position and dimensions
        """
        # This function is from stiler (https://github.com/soulfx/stiler)
        x = int(x) + self.offset[0]
        y = int(y) + self.offset[1]

        max_h, max_v = False, False
        if self.max:
            if w == self.size[0]:
                max_h = True
            if h == self.size[1]:
                max_v = True

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
        cmd = "wmctrl " + window + " -b remove,maximized_vert,maximized_horz"
        self._call(cmd)

        # NOTE: metacity doesn't like resizing and moving in the same step    
        if self.metacity:
            # resize
            cmd = "wmctrl %s -e 0,-1,-1,%i,%i" % (window, w, h)
            self._call(cmd)
            # move    
            cmd = "wmctrl %s -e 0,%i,%i,-1,-1" % (window, max(x, 0), max(y, 0))
            self._call(cmd)
        else:
            cmd = "wmctrl %s -e 0,%i,%i,%i,%i" % (window,
                                                  max(x, 0), max(y, 0),
                                                  w, h)


        if max_h:
            cmd = "wmctrl %s -b add,maximized_horz" % window
            self._call(cmd)
        if max_v:
            cmd = "wmctrl %s -b add,maximized_vert" % window
            self._call(cmd)

        # set properties
        command = "wmctrl " + window + " -b remove,hidden,shaded"
        self._call(command)


    def get_mouse_on_desktop(self, x, y):
        return (x - self.offset[0], y - self.offset[1])


    def _call(self, cmd):
        logger.info("Calling OS-CMD: %s" % cmd)
        return subprocess.call(cmd, shell=True)



class Area(object):

    def __init__(self, x, y):
        self.x1 = x
        self.x2 = x
        self.y1 = y
        self.y2 = y

    def add_point(self, x, y):
        self.x1 = min(x, self.x1)
        self.x2 = max(x , self.x2)
        self.y1 = min(y, self.y1)
        self.y2 = max(y, self.y2)

    def __str__(self):
        return "Area: (%d, %d - %d, %d)" % (self.x1, self.y1,
                                        self.x2, self.y2)

    def __repr__(self):
        return self.__str__()


class GridMouseVooDoo(Thread):

    def __init__(self, wm, button=10, daemon=True):
        Thread.__init__(self)
        
        # Set the Thread.daemon flag
        self.daemon = daemon
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
        x, y = wm.get_mouse_on_desktop(x, y)
        if not self.area:
            logger.debug("Mouse moved to %d, %d but not button not pressed" %
                         (x, y))
            return
        self.area.add_point(x, y)
        logger.debug("Mouse moved to %d, %d" % (x, y))


import time
time.sleep(15)
wm = WindowManager(([0, 0.33, 0.5, 0.67, 1], [0, 0.5, 1]), (32, 1, 1, 1))
button = 13
gmvd = GridMouseVooDoo(wm, button, False)
gmvd.start()
