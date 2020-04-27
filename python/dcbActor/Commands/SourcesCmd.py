#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils import waitForTcpServer
from enuActor.utils.wrap import threaded, blocking, singleShot


class SourcesCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('sources', 'status', self.status),
            ('sources', '[<on>] [<attenuator>] [<warmingTime>] [force]', self.switchOn),
            ('sources', '<off>', self.switchOff),
            ('sources', 'abort', self.abort),
            ('sources', 'stop', self.stop),
            ('sources', 'start [@(operation|simulation)]', self.start),
        ]

        self.vocab += [('arc', cmdStr, func) for __, cmdStr, func in self.vocab]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__sources", (1, 1),
                                        keys.Key("on", types.String() * (1, None),
                                                 help='which outlet to switch on.'),
                                        keys.Key("off", types.String() * (1, None),
                                                 help='which outlet to switch off.'),
                                        keys.Key("attenuator", types.Int(), help="attenuator value"),
                                        keys.Key("warmingTime", types.Float(), help="customizable warming time"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['sources']
        except KeyError:
            raise RuntimeError('sources controller is not connected.')

    @threaded
    def status(self, cmd):
        """Report state, mode, status."""
        self.controller.generate(cmd)

    @blocking
    def switchOn(self, cmd):
        """Switch on light sources."""
        cmdKeys = cmd.cmd.keywords
        sourcesOn = cmdKeys['on'].values if 'on' in cmdKeys else []

        for name in sourcesOn:
            if name not in self.controller.names:
                raise ValueError(f'{name} : unknown source')

        warmingTime = max([self.controller.warmingTime[source] for source in sourcesOn]) if sourcesOn else 0
        warmingTime = cmdKeys['warmingTime'].values[0] if 'warmingTime' in cmdKeys else warmingTime
        warmingTime = 0 if 'force' in cmdKeys else warmingTime

        toBeWarmed = sourcesOn if sourcesOn else self.controller.sourcesOn
        remainingTimes = [warmingTime - self.controller.elapsed(source) for source in toBeWarmed]
        warmingTime = max(remainingTimes) if remainingTimes else 0

        self.controller.substates.warming(cmd, sourcesOn=sourcesOn, warmingTime=warmingTime)
        self.controller.generate(cmd)

    @blocking
    def switchOff(self, cmd):
        """Switch off light sources."""
        cmdKeys = cmd.cmd.keywords

        sourcesOff = cmdKeys['off'].values if 'off' in cmdKeys else []

        for name in sourcesOff:
            if name not in self.controller.names:
                raise ValueError(f'{name} : unknown source')

        self.controller.switchOff(cmd, sourcesOff)
        self.controller.generate(cmd)

    def abort(self, cmd):
        """Abort iis warmup."""
        self.controller.doAbort()
        cmd.finish("text='warmup aborted'")

    @singleShot
    def stop(self, cmd):
        """Abort iis warmup, turn iis lamp off and disconnect."""
        self.actor.disconnect('sources', cmd=cmd)
        cmd.finish()

    @singleShot
    def start(self, cmd):
        """Wait for pdu host, connect iis controller."""
        cmdKeys = cmd.cmd.keywords
        mode = self.actor.config.get('sources', 'mode')
        host = self.actor.config.get('pdu', 'host')
        port = self.actor.config.get('pdu', 'port')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        waitForTcpServer(host=host, port=port, cmd=cmd, mode=mode)

        cmd.inform('text="connecting sources..."')
        self.actor.connect('sources', cmd=cmd, mode=mode)
        cmd.finish()
