#!/usr/bin/env python

import time

from twisted.internet import reactor

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
            ('sources', 'prepare [<halogen>] [<argon>] [<hgar>] [<neon>] [<krypton>]', self.prepare),
            ('sources', 'go [<delay>]', self.go),
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
                                        keys.Key("halogen", types.Float(), help="requested quartz halogen lamp time" ),
                                        keys.Key("argon", types.Float(), help="requested Ar lamp time" ),
                                        keys.Key("hgar", types.Float(), help="requested HgAr lamp time" ),
                                        keys.Key("neon", types.Float(), help="requested Ne lamp time" ),
                                        keys.Key("krypton", types.Float(), help="requested Kr lamp time" ),
                                        keys.Key("delay", types.Float(), help="delay before turning lamps on" ),
                                        )
        self.lampNames = ('halogen', 'argon', 'hgar', 'neon', 'krypton')
        self.config = None

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

    @property
    def lampString(self):
        """Describe the lamps configured by the .prepare() command."""
        if self.config is None:
            ll = []
        ll = ["%s=%0.1f" % (ln, lv) for ln, lv in self.config.items()]
        return ','.join(ll)

    @blocking
    def prepare(self, cmd):
        """Configure a future illumination sequence."""

        cmdKeys = cmd.cmd.keywords

        if self.config is not None:
            cmd.warn('text="active lamp configuration being overwritten (%s)"' % self.lampString)
        self.config = dict()
        for l in self.lampNames:
            if l in cmdKeys:
                lampTime = cmdKeys[l].values[0]
                if lampTime > 60:
                    self.config = None
                    cmd.fail('text="currently limiting lamp times to 60s, sorry."')
                    return
                self.config[l] = lampTime

        # OK, this is _really_ skeevy. But we need header cards, to be grabbed at
        #   the start of integration.
        for lamp in self.lampNames:
            state = 'on' if self.config.get(lamp, 0) > 0 else 'off'
            cmd.inform(f'{lamp}={state},-1')

        cmd.finish('text="will turn on: %s"' % (self.lampString))

    def go(self, cmd):
        """Run the preconfigured illumination sequence.

        Note
        ----
        Always clears the predefined sequence.
        """

        cmdKeys = cmd.cmd.keywords

        if self.config is None or len(self.config) == 0:
            cmd.finish('text="no lamps are configured to turn on now"')
            self.config = None
            return

        delay = cmdKeys['delay'].values[0] if 'delay' in cmdKeys else 0.0
        sources = tuple(self.config.keys())

        # Build a list of (secondsToLeaveOn, sourceSet) pairs
        timeToSource = dict()
        for k, v in self.config.items(): 
            timeToSource.setdefault(v, set()).add(k)
        lastT = 0.0
        timeSequence = []
        for t in sorted(timeToSource.keys()):
            timeSequence.append([t-lastT, timeToSource[t]])
            lastT = t
        cmd.debug(f'text="lamp sequence is {timeSequence}"')

        t0 = time.time()
        if delay > 0:
            cmd.debug(f'text="will turn on {sources} in {delay}s seconds"')
            time.sleep(delay)

        t1 = time.time()
        try:
            self.controller.switchOn(cmd, sources)
        except Exception as e:
            cmd.warn(f'text="lamp switch might not have been turned on ({e} .... trying to clean up"')
            self.controller.switchOff(cmd, sources)
            self.config = None
            self.controller.generate(cmd)
            return
        t2 = time.time()
        cmd.inform('text="turned on: %s"' % (self.lampString))

        def turnLampsOff(self, cmd, timeSequence, t0=t0, t1=t1, t2=t2):
            """Turn off lamps, in order of ontime

            Parameters
            ----------
            cmd : Command
                Command to report back to.
            timeSequence : [[dOntime, {sources}]]
                array of incremental times and sets of sources. 

            Steps through the timeSequenceArray, turning off all the sources in the first item,
            then deferring until the start of second via a recursive call.
            """

            t3 = time.time()
            thisChunk, *timeSequence = timeSequence
            _, sources = thisChunk
            cmd.debug(f'text="turning lamp {sources} off..."')
            self.controller.switchOff(cmd, sources)
            t4 = time.time()
            cmd.debug(f'text="turned {sources} off. delay={t1-t0:0.2f} switchOn={t2-t1:0.2f} on={t3-t2:0.2f} switchOff={t4-t3:0.2f}"')

            if timeSequence:
                trimBy = t4-t3
                timeSequence = [[t-trimBy, sources] for t, sources in timeSequence]
                nextPause = timeSequence[0][0]
                if nextPause < 0:
                    cmd.warn(f'text="falling behind by {nextPause} on turning lamps off. Remaining changes: {timeSequence}"')
                    nextPause = 0.0001
                reactor.callLater(nextPause, turnLampsOff, self, cmd, timeSequence)
            else:
                self.config = None
                self.controller.generate(cmd)

        firstOnTime = timeSequence[0][0]
        reactor.callLater(firstOnTime, turnLampsOff, self, cmd, timeSequence)

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
