__author__ = 'alefur'

import logging
import time
from importlib import reload

import dcbActor.Simulators.filterwheel as simulator
import ics.utils.tcp.bufferedSocket as bufferedSocket
from ics.utils.fsm.fsmThread import FSMThread

reload(simulator)


class filterwheel(FSMThread, bufferedSocket.EthComm):
    wheelPortConfig = dict(dcb=dict(linewheel=1, qthwheel=0),
                           dcb2=dict(linewheel=0, qthwheel=1))

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: dcbActor.
        :param name: controller name.
        :type name: str
        """
        substates = ['IDLE', 'MOVING', 'FAILED']
        events = [{'name': 'move', 'src': 'IDLE', 'dst': 'MOVING'},
                  {'name': 'idle', 'src': ['MOVING', ], 'dst': 'IDLE'},
                  {'name': 'fail', 'src': ['MOVING', ], 'dst': 'FAILED'},
                  ]

        FSMThread.__init__(self, actor, name, events=events, substates=substates)

        self.addStateCB('MOVING', self.moving)
        self.sim = simulator.FilterwheelSim(self.actor.name)

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
        return dict([(i + 1, str(h).strip()) for i, h in enumerate(self.controllerConfig['lineHoles'])])

    @property
    def qthHoles(self):
        return dict([(i + 1, str(h).strip()) for i, h in enumerate(self.controllerConfig['qthHoles'])])

    def _loadCfg(self, cmd, mode=None):
        """Load filterwheel configuration.

        :param cmd: current command.
        :param mode: operation|simulation, loaded from config file if None.
        :type mode: str
        :raise: Exception if config file is badly formatted.
        """
        self.mode = self.controllerConfig['mode'] if mode is None else mode
        self.wheelPort = self.wheelPortConfig[self.actor.name]
        bufferedSocket.EthComm.__init__(self,
                                        host=self.controllerConfig['host'],
                                        port=self.controllerConfig['port'],
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

    def _init(self, cmd, doLineWheel=True, doQthWheel=True, doReset=True):
        """Initialise both wheel by default

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        if doReset:
            self.actor.actorData.persistKey('linewheel', -1)
            self.actor.actorData.persistKey('qthwheel', -1)

        if doLineWheel:
            try:
                self.initWheel(cmd, 'linewheel')
                cmd.inform('text="line wheel init OK"')
            except:
                cmd.warn('text="line wheel init FAILED ! "')
                raise

        if doQthWheel:
            try:
                self.initWheel(cmd, 'qthwheel')
                cmd.inform('text="qth wheel init OK"')
            except:
                cmd.warn('text="qth wheel init FAILED ! "')
                raise

    def loadWheelPosition(self, wheel):
        """load persisted wheel position and hole from instdata

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        try:
            position, = self.actor.actorData.loadKey(wheel)
            holes = self.lineHoles if wheel == 'linewheel' else self.qthHoles
            hole = holes[position]
        except:
            # a bit of flexibility, to be removed later
            position = -1
            hole = 'unknown'

        return position, hole

    def getStatus(self, cmd):
        """Get all ports status.

        :param cmd: current command.
        :raise: Exception with warning message.
        """
        adc1 = self.sendOneCommand('adc 1', cmd=cmd)
        adc2 = self.sendOneCommand('adc 2', cmd=cmd)

        linePosition, lineHole = self.loadWheelPosition('linewheel')
        qthPosition, qthHole = self.loadWheelPosition('qthwheel')

        cmd.inform(f'adc={adc1},{adc2}')
        cmd.inform(f'linewheel={linePosition},{lineHole}')
        cmd.inform(f'qthwheel={qthPosition},{qthHole}')

    def moving(self, cmd, wheel, position):
        """Move required wheel to required position
        :param cmd: current command.
        :param wheel: linewheel|qthwheel
        :param position: int(1-5)
        :raise: Exception with warning message.
        """
        current, __ = self.loadWheelPosition(wheel)
        if current == -1:
            raise UserWarning(f'{wheel} has not been initialized properly')

        ret = self.sendOneCommand(f'{wheel} {position}', cmd=cmd)
        cmd.inform(f'text="{ret}"')

        ret = self.waitForEndBlock(cmd, 'Moved to position', timeout=10, timeLim=30)

        __, position = ret.split('Moved to position')
        position = int(position)

        self.actor.actorData.persistKey(wheel, position)

    def initWheel(self, cmd, wheel):
        """Init required wheel
        :param cmd: current command.
        :param wheel: linewheel|qthwheel
        :param position: int(1-5)
        :raise: Exception with warning message.
        """
        cmd.inform(f'text="initializing {wheel}..."')

        ret = self.sendOneCommand(f'{wheel} {-1}', cmd=cmd)
        cmd.inform(f'text="{ret}"')
        # declaring which wheel is going to be calibrated.
        self.waitForEndBlock(cmd, f'Calibrating FW {self.wheelPort[wheel]}', timeout=30, timeLim=60)
        # wait for the start the calibration
        self.waitForEndBlock(cmd, f'Calibrating')
        # wait for DONE or CALIBRATE FAILED basically.
        try:
            self.waitForEndBlock(cmd, 'Done', timeout=10, timeLim=30)
        except TimeoutError:
            raise RuntimeError(f'{wheel} CALIBRATION FAILED !')

        self.actor.actorData.persistKey(wheel, 1)

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
