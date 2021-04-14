#!/usr/bin/env python

import time

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
            ('sources', '[<on>] [<warmingTime>] [force]', self.warmup),
            ('sources', '<off>', self.switchOff),
            ('sources', 'abort', self.abort),
            ('sources', 'prepare [<halogen>] [<argon>] [<hgar>] [<neon>] [<krypton>]', self.prepare),
            ('sources', 'go [<delay>]', self.go),
            ('sources', 'stop', self.stop),
            ('sources', 'start [@(operation|simulation)]', self.start),
        ]

        self.vocab += [('arc', cmdStr, func) for __, cmdStr, func in self.vocab]
        self.vocab += [('lamps', cmdStr, func) for __, cmdStr, func in self.vocab]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__sources", (1, 1),
                                        keys.Key("on", types.String() * (1, None),
                                                 help='which outlet to switch on.'),
                                        keys.Key("off", types.String() * (1, None),
                                                 help='which outlet to switch off.'),
                                        keys.Key("warmingTime", types.Float(), help="customizable warming time"),
                                        keys.Key("halogen", types.Float(), help="requested quartz halogen lamp time"),
                                        keys.Key("argon", types.Float(), help="requested Ar lamp time"),
                                        keys.Key("hgar", types.Float(), help="requested HgAr lamp time"),
                                        keys.Key("neon", types.Float(), help="requested Ne lamp time"),
                                        keys.Key("krypton", types.Float(), help="requested Kr lamp time"),
                                        keys.Key("delay", types.Float(), help="delay before turning lamps on"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers['sources']
        except KeyError:
            raise RuntimeError('sources controller is not connected.')

    @property
    def lampNames(self):
        return self.controller.lampNames

    @property
    def config(self):
        return self.controller.config

    @property
    def lampString(self):
        """Describe the lamps configured by the .prepare() command."""
        ll = [] if self.config is None else ["%s=%0.1f" % (ln, lv) for ln, lv in self.config.items()]
        return ','.join(ll)

    @threaded
    def status(self, cmd):
        """Report state, mode, status."""
        self.controller.generate(cmd)

    @singleShot
    def warmup(self, cmd):
        """Switch on light sources and warm it up if requested, FSM protect from go command."""
        cmdKeys = cmd.cmd.keywords

        sourcesOn = cmdKeys['on'].values if 'on' in cmdKeys else []
        warmingTime = cmdKeys['warmingTime'].values[0] if 'warmingTime' in cmdKeys else None
        warmingTime = 0 if 'force' in cmdKeys else warmingTime

        for name in sourcesOn:
            if name not in self.lampNames:
                raise ValueError(f'{name} : unknown source')

        self.controller.substates.warming(cmd, lamps=sourcesOn, warmingTime=warmingTime)
        self.controller.generate(cmd)

    @blocking
    def switchOff(self, cmd):
        """Switch off light sources."""
        cmdKeys = cmd.cmd.keywords
        sourcesOff = cmdKeys['off'].values

        for name in sourcesOff:
            if name not in self.lampNames:
                raise ValueError(f'{name} : unknown source')

        self.controller.switchOff(cmd, sourcesOff)
        self.controller.generate(cmd)

    @blocking
    def prepare(self, cmd):
        """Configure a future illumination sequence."""
        cmdKeys = cmd.cmd.keywords

        if self.config is not None:
            cmd.warn('text="active lamp configuration being overwritten (%s)"' % self.lampString)

        self.config.clear()
        for l in self.lampNames:
            if l in cmdKeys:
                lampTime = cmdKeys[l].values[0]
                self.config[l] = lampTime

        self.controller.prepare(cmd)
        # OK, this is _really_ skeevy. But we need header cards, to be grabbed at
        #   the start of integration.
        for lamp in self.lampNames:
            state = 'on' if self.config.get(lamp, 0) > 0 else 'off'
            cmd.inform(f'{lamp}={state},-1')
        cmd.finish('text="will turn on: %s"' % (self.lampString))

    @blocking
    def go(self, cmd):
        """Run the preconfigured illumination sequence.

        Note
        ----
        Currently don't clear the predefined sequence.
        """
        cmdKeys = cmd.cmd.keywords

        if self.config is None or len(self.config) == 0:
            cmd.finish('text="no lamps are configured to turn on now"')
            self.config.clear()
            return

        delay = cmdKeys['delay'].values[0] if 'delay' in cmdKeys else 0.0
        sources = tuple(self.config.keys())

        if delay > 0:
            cmd.debug(f'text="will turn on {sources} in {delay}s seconds"')
            time.sleep(delay)

        self.controller.substates.triggering(cmd)
        cmd.finish()

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
        host = self.actor.config.get('sources', 'host')
        port = self.actor.config.get('sources', 'port')
        mode = 'operation' if 'operation' in cmdKeys else mode
        mode = 'simulation' if 'simulation' in cmdKeys else mode

        waitForTcpServer(host=host, port=port, cmd=cmd, mode=mode)

        cmd.inform('text="connecting sources..."')
        self.actor.connect('sources', cmd=cmd, mode=mode)
        cmd.finish()
