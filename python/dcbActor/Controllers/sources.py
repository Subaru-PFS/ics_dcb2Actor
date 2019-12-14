__author__ = 'alefur'
import logging
import time

from dcbActor.Controllers import pdu
from enuActor.Simulators.pdu import PduSim
from enuActor.utils import wait
from enuActor.utils.fsmThread import FSMThread


class sources(pdu.pdu):
    warmingTime = dict(hgar=15, neon=15, krypton=15, halogen=60)
    names = ['hgar', 'neon', 'krypton', 'halogen']

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """
        substates = ['IDLE', 'WARMING', 'FAILED']
        events = [{'name': 'warming', 'src': 'IDLE', 'dst': 'WARMING'},
                  {'name': 'idle', 'src': ['WARMING', ], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['WARMING', ], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('WARMING', self.warming)
        self.sim = PduSim()
        self.abortWarmup = False

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def _loadCfg(self, cmd, mode=None):
        """Load iis configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        mode = self.actor.config.get('sources', 'mode') if mode is None else mode
        pdu.pdu._loadCfg(self, cmd=cmd, mode=mode)

        for source in sources.names:
            if source not in self.powerPorts.keys():
                raise ValueError(f'{source} : unknown source')

    def getStatus(self, cmd):
        """Get and generate iis keywords.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        for source in sources.names:
            state = self.getState(source, cmd=cmd)
            cmd.inform(f'{source}={state}')

    def getState(self, source, cmd):
        """Get current light source state.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        state = self.sendOneCommand('read status o%s simple' % self.powerPorts[source], cmd=cmd)
        if state == 'pending':
            wait(secs=2)
            return self.getState(source, cmd=cmd)

        return state

    def warming(self, cmd, sourcesOn, warmingTime, ti=0.01):
        """Switch on source lamp and wait for iis.warmingTime.

        :param cmd: current command.
        :param sourcesOn: light source lamp to switch on.
        :type sourcesOn: list
        :raise: Exception with warning message.
        """
        for outlet in sourcesOn:
            self.sendOneCommand('sw o%s on imme' % outlet, cmd=cmd)
            self.portStatus(cmd, outlet=outlet)

        if sourcesOn:
            start = time.time()
            self.abortWarmup = False
            while time.time() < start + warmingTime:
                time.sleep(ti)
                self.handleTimeout()
                if self.abortWarmup:
                    raise RuntimeError('sources warmup aborted')

    def isOff(self, source):
        """Check if light source is currently off.

        :param source: source name.
        :type source: str
        :return: state
        :rtype: bool
        """
        state = self.actor.models[self.actor.name].keyVarDict[source].getValue()
        return not bool(state)

    def doAbort(self):
        """Abort warmup.
        """
        self.abortWarmup = True
        while self.currCmd:
            pass
        return

    def leaveCleanly(self, cmd):
        """Clear and leave.

        :param cmd: current command.
        """
        self.monitor = 0
        self.doAbort()

        powerOff = dict([(self.powerPorts[name], 'off') for name in self.names])

        try:
            self.switching(cmd, powerPorts=powerOff)
            self.getStatus(cmd)
        except Exception as e:
            cmd.warn('text=%s' % self.actor.strTraceback(e))

        self._closeComm(cmd=cmd)
