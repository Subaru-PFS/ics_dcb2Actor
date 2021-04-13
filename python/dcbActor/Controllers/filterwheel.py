__author__ = 'alefur'

import logging
import time

import enuActor.utils.bufferedSocket as bufferedSocket
from dcbActor.Simulators.filterwheel import FilterwheelSim
from enuActor.utils.fsmThread import FSMThread


class filterwheel(FSMThread, bufferedSocket.EthComm):
    wheelPort = dict(linewheel=0, qthwheel=1)

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """
        substates = ['IDLE', 'MOVING', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'idle', 'src': ['MOVING', ], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', ], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates, doInit=True)

        self.addStateCB('MOVING', self.moving)
        self.sim = FilterwheelSim()

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    @property
    def simulated(self):
        """Return True if self.mode=='simulation', return False if self.mode='operation'."""
        if self.mode == 'simulation':
            return True
        elif self.mode == 'operation':
            return False
        else:
            raise ValueError('unknown mode')

    @property
    def lineHoles(self):
        return dict(
            [(i + 1, h.strip()) for i, h in enumerate(self.actor.config.get('filterwheel', 'lineHoles').split(','))])

    @property
    def qthHoles(self):
        return dict(
            [(i + 1, h.strip()) for i, h in enumerate(self.actor.config.get('filterwheel', 'qthHoles').split(','))])

    def _loadCfg(self, cmd, mode=None):
        """Load filterwheel configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        self.mode = self.actor.config.get('filterwheel', 'mode') if mode is None else mode
        bufferedSocket.EthComm.__init__(self,
                                        host=self.actor.config.get('filterwheel', 'host'),
                                        port=int(self.actor.config.get('filterwheel', 'port')),
                                        EOL='\r\n')

    def _openComm(self, cmd):
        """Open socket with filterwheel controller or simulate it.

        :param cmd: current command.
        :raise: socket.error if the communication has failed.
        """
        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + 'IO', EOL='\n', timeout=3)
        s = self.connectSock()

    def _closeComm(self, cmd):
        """Close socket.

        :param cmd: current command.
        """
        self.closeSock()

    def _testComm(self, cmd):
        """Test communication.

        :param cmd: current command.
        :raise: Exception if the communication has failed with the controller.
        """
        return self.sendOneCommand('adc 1', cmd=cmd)

    def getStatus(self, cmd):
        """Get all ports status.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        adc1 = self.sendOneCommand('adc 1', cmd=cmd)
        adc2 = self.sendOneCommand('adc 2', cmd=cmd)

        try:
            lineWheel, = self.actor.instData.loadKey('linewheel')
            lineHole = self.lineHoles[lineWheel]
        except:
            # a bit of flexibility, to be removed later
            lineWheel = -1
            lineHole = 'unknown'

        try:
            qthWheel, = self.actor.instData.loadKey('qthwheel')
            qthHole = self.qthHoles[qthWheel]
        except:
            # a bit of flexibility, to be removed later
            qthWheel = -1
            qthHole = 'unknown'

        cmd.inform(f'adc={adc1},{adc2}')
        cmd.inform(f'linewheel={lineWheel},{lineHole}')
        cmd.inform(f'qthwheel={qthWheel},{qthHole}')

    def moving(self, cmd, wheel, position):
        """Move required wheel to required position
        :param cmd: current command.
        :param wheel: linewheel|qthwheel
        :param position: int(1-5)
        :raise: Exception with warning message.
        """
        ret = self.sendOneCommand(f'{wheel} {position}', cmd=cmd)
        cmd.inform(f'text="{ret}"')

        ret = self.waitForEndBlock(cmd, 'Moved to position', timeout=10, timeLim=30)

        __, position = ret.split('Moved to position')
        position = int(position)

        self.actor.instData.persistKey(wheel, position)

    def initWheel(self, cmd, wheel):
        """Init required wheel
        :param cmd: current command.
        :param wheel: linewheel|qthwheel
        :param position: int(1-5)
        :raise: Exception with warning message.
        """
        ret = self.sendOneCommand(f'{wheel} {-1}', cmd=cmd)
        cmd.inform(f'text="{ret}"')

        cmd.inform(f'text="waiting for filterwheel-dcb response within 20 seconds...')
        self.waitForEndBlock(cmd,  f'Calibrating FW {filterwheel.wheelPort[wheel]}', timeout=30, timeLim=60)
        self.waitForEndBlock(cmd, 'Done', timeout=5, timeLim=15)

        self.actor.instData.persistKey(wheel, 1)

    def adcCalib(self, cmd):
        """zeros adc channels.
        :param cmd: current command.
        :raise: Exception with warning message.
        """
        ret = self.sendOneCommand('adccalib ', cmd=cmd)
        cmd.inform(f'text="{ret}"')

        ret = self.sendOneCommand('continue ', cmd=cmd)
        cmd.inform(f'text="{ret}"')

        self.waitForEndBlock(cmd, 'Zeros for channel', timeout=5, timeLim=15)

    def waitForEndBlock(self, cmd, endBlock, timeout=10, timeLim=30, maxIter=100):
        """Wait until end block is returned, various check are made to avoid endless loop.
        :param cmd: current command.
        :param endBlock: expected end block
        :param timeout: buffer timeout.
        :param timeLim: total timeout.
        :raise: Exception with warning message.
        """
        ret = ''
        start = time.time()
        iter = 0

        while endBlock not in ret:
            ret = self.getOneResponse(cmd=cmd, timeout=timeout)
            if ret:
                cmd.inform(f'text="{ret}"')
            if (time.time() - start) > timeLim:
                raise TimeoutError('filterwheel-dcb has not answered in the appropriate timing...')
            if iter > maxIter:
                raise RuntimeError('socket is broken...')
            iter += 1

        return ret

    def createSock(self):
        """Create socket in operation, simulator otherwise.
        """
        if self.simulated:
            s = self.sim
        else:
            s = bufferedSocket.EthComm.createSock(self)

        return s
