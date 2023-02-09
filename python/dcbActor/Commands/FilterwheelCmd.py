#!/usr/bin/env python

import time

import ics.utils.tcp.utils as tcpUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils.threading import threaded, blocking, singleShot


class FilterwheelCmd(object):
    # time to wait(seconds) between switchOn and switchOff
    waitBetweenSwitch = 10

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
            ('filterwheel', 'init', self.initWheel),
            ('set', '@(<linewheel>|<qthwheel>)', self.moveWheel),
            ('init', '@(linewheel|qthwheel)', self.initWheel),
            ('adc', 'calib', self.adcCalib),

            ('filterwheel', 'reboot', self.reboot),
            ('power', '@(off|on) @filterwheel', self.reboot),
            ('filterwheel', 'start', self.start)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__filterwheel", (1, 1),
                                        keys.Key('linewheel', types.String(), help='line wheel position (1-5)'),
                                        keys.Key('qthwheel', types.String(), help='qth wheel position (1-5)'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['filterwheel']
        except KeyError:
            raise RuntimeError('filterwheel controller is not connected.')

    @property
    def pdu(self):
        try:
            return self.actor.controllers['lamps']
        except KeyError:
            raise RuntimeError('lamps controller is not connected.')

    def config(self, option):
        return self.actor.actorConfig['filterwheel'][option]

    @threaded
    def status(self, cmd):
        """Report state, mode, status."""
        self.controller.generate(cmd)

    @blocking
    def moveWheel(self, cmd):
        """set linewheel to required position."""
        cmdKeys = cmd.cmd.keywords
        if 'linewheel' in cmdKeys:
            wheel = 'linewheel'
            holeDict = self.controller.lineHoles
        else:
            wheel = 'qthwheel'
            holeDict = self.controller.qthHoles

        revHoleDict = dict([(v, k) for k, v in holeDict.items()])
        existingHoles = ",".join([str(key) for key in revHoleDict.keys()])
        hole = cmdKeys[wheel].values[0]

        if hole not in revHoleDict.keys():
            try:
                hole = '{:.1f}'.format(float(hole))
                position = revHoleDict[hole]
            except:
                raise ValueError(f'unknown hole:{hole}, existing are {existingHoles}')

        position = revHoleDict[hole]
        self.controller.substates.move(wheel=wheel, position=position, cmd=cmd)
        self.controller.generate(cmd)

    @blocking
    def initWheel(self, cmd):
        """set linewheel to required position."""
        cmdKeys = cmd.cmd.keywords
        doLineWheel = 'qthwheel' not in cmdKeys
        doQthWheel = 'linewheel' not in cmdKeys

        if self.controller.states.current == 'LOADED':
            self.controller.substates.init(cmd, doLineWheel=doLineWheel, doQthWheel=doQthWheel)
        else:
            self.controller.init(cmd, doLineWheel=doLineWheel, doQthWheel=doQthWheel, doReset=False)

        self.controller.generate(cmd)

    @blocking
    def adcCalib(self, cmd):
        """set linewheel to required position."""
        cmdKeys = cmd.cmd.keywords

        self.controller.adcCalib(cmd=cmd)
        self.controller.generate(cmd)

    def reboot(self, cmd):
        """ reboot switch on/off filterwheel controller"""
        cmdKeys = cmd.cmd.keywords

        powerOn = False
        powerOff = False

        if 'reboot' in cmdKeys:
            powerOff = powerOn = True
        elif 'on' in cmdKeys:
            powerOn = True
        elif 'off' in cmdKeys:
            powerOff = True

        self.slapController(cmd, powerOn=powerOn, powerOff=powerOff)

        cmd.finish()

    def slapController(self, cmd, powerOn, powerOff):
        """Switch filterwheel controller given powerOn and powerOff boolean."""

        def powerSwitch(cmd, state):
            """Trigger filterwheel power switch"""
            self.pdu.crudeSwitch(cmd, 'filterwheel', state)
            self.pdu.getStatus(cmd)

        if powerOff:
            powerSwitch(cmd, 'off')

        if powerOff and powerOn:
            cmd.inform(f'text="waiting now {FilterwheelCmd.waitBetweenSwitch} secs"')
            time.sleep(FilterwheelCmd.waitBetweenSwitch)

        if powerOn:
            powerSwitch(cmd, 'on')

    @singleShot
    def start(self, cmd):
        """Power on hxp controller, connect slit controller, and init."""
        cmdKeys = cmd.cmd.keywords

        host, port = self.config('host'), int(self.config('port'))

        mode = self.config('mode')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        # if filterwheel server is down.
        if mode == 'operation' and not tcpUtils.serverIsUp(host, port):
            self.slapController(cmd, powerOff=True, powerOn=True)
            tcpUtils.waitForTcpServer(host, port, cmd=cmd)

        # connect controller.
        self.actor.connect('filterwheel', cmd=cmd, mode=mode)

        # init is required if LOADED state.
        if self.controller.states.current == 'LOADED':
            self.controller.substates.init(cmd)

        self.controller.generate(cmd)
