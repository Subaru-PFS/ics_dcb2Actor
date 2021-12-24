#!/usr/bin/env python

from importlib import reload

from ics.utils.sps.lamps.commands import LampsCmd as Cmd

reload(Cmd)


class LampsCmd(Cmd.LampsCmd):
    """ code shared among ics_utils package."""

    def __init__(self, actor):
        Cmd.LampsCmd.__init__(self, actor)
