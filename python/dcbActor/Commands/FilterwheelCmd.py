#!/usr/bin/env python

import opscore.protocols.keys as keys
from enuActor.utils.wrap import threaded


class FilterwheelCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('filterwheel', 'status', self.status),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__filterwheel", (1, 1),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['filterwheel']
        except KeyError:
            raise RuntimeError('filterwheel controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report state, mode, status."""
        self.controller.generate(cmd)
