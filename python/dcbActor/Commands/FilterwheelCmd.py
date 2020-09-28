#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded, blocking


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
            ('set', '@(<linewheel>|<qthwheel>)', self.moveWheel),
            ('init', '@(linewheel|qthwheel)', self.initWheel),
            ('adc', 'calib', self.adcCalib)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__filterwheel", (1, 1),
                                        keys.Key('linewheel', types.Int(), help='line wheel position (1-5)'),
                                        keys.Key('qthwheel', types.Int(), help='qth wheel position (1-5)'),
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

    @blocking
    def moveWheel(self, cmd):
        """set linewheel to required position."""
        cmdKeys = cmd.cmd.keywords
        wheel = 'linewheel' if 'linewheel' in cmdKeys else 'qthwheel'
        position = cmdKeys[wheel].values[0]

        self.controller.moving(wheel=wheel, position=position, cmd=cmd)
        self.controller.generate(cmd)

    @blocking
    def initWheel(self, cmd):
        """set linewheel to required position."""
        cmdKeys = cmd.cmd.keywords
        wheel = 'linewheel' if 'linewheel' in cmdKeys else 'qthwheel'

        self.controller.initWheel(wheel=wheel, cmd=cmd)
        self.controller.generate(cmd)

    @blocking
    def adcCalib(self, cmd):
        """set linewheel to required position."""
        cmdKeys = cmd.cmd.keywords
        wheel = 'linewheel' if 'linewheel' in cmdKeys else 'qthwheel'

        self.controller.adcCalib(cmd=cmd)
        self.controller.generate(cmd)
