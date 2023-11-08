__author__ = 'alefur'

import socket
import time


class FilterwheelSim(socket.socket):
    wheelPortConfig = dict(dcb=dict(line=1, qth=0),
                           dcb2=dict(line=0, qth=1))

    def __init__(self, name):
        """Fake filterwheel tcp server."""
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.wheelPort = self.wheelPortConfig[name]
        self.buf = []

    def connect(self, server):
        """Fake the connection to tcp server."""
        (ip, port) = server
        time.sleep(0.2)
        if type(ip) is not str:
            raise TypeError
        if type(port) is not int:
            raise TypeError

    def sendall(self, cmdStr, flags=None):
        """Send fake packets, append fake response to buffer."""
        time.sleep(0.02)
        cmdStr = cmdStr.decode()
        cmdStr, __ = cmdStr.split('\r\n')

        if 'adc ' in cmdStr:
            self.buf.append('-.0014\n')

        elif 'linewheel' in cmdStr:
            __, position = cmdStr.split('linewheel')
            position = int(position)
            if position == -1:
                self.buf.append(self.wheelCalib('line'))
            else:
                self.buf.append('port0 = UL  port1 = LL\n')
                self.buf.append('Setting FW 0 to position 1\nattached 2 filter wheel(s):\nindex 0: ID 0 Name EFW \n'
                                'index 1: ID 1 Name EFW \nselecting 0 \n5 slots: 1 2 3 4 5 \ncurrent position: 1\n'
                                f'Moving...\nMoved to position {position}\n')

        elif 'qthwheel' in cmdStr:
            __, position = cmdStr.split('qthwheel')
            position = int(position)

            if position == -1:
                self.buf.append(self.wheelCalib('qth'))
            else:
                self.buf.append('port0 = UL  port1 = LL\n')
                self.buf.append('Setting FW 0 to position 1\nattached 2 filter wheel(s):\nindex 0: ID 0 Name EFW \n'
                                'index 1: ID 1 Name EFW \nselecting 0 \n5 slots: 1 2 3 4 5 \ncurrent position: 1\n'
                                f'Moving...\nMoved to position {position}\n')

        elif 'adccalib' in cmdStr:
            self.buf.append('Turn off all lamps so that the integrating sphere is dark.\n')
            self.buf.append('When this is done, hit any key to continue\n')

        elif 'continue' in cmdStr:
            self.buf.append('iteration 1 z1=0.0491  z2=0.0486 \n')
            self.buf.append('iteration 2 z1=0.0491  z2=0.0488 \n'
                            'iteration 3 z1=0.0491  z2=0.0486 \n'
                            'iteration 4 z1=0.0491  z2=0.0486 \n'
                            'iteration 5 z1=0.0491  z2=0.0486 \n'
                            '\nZeros for channel 1, 2 = .0491, .0486\n')

    def wheelCalib(self, wheel):
        wheelId = self.wheelPort[wheel]
        wheelCalib = f'port0 = |UL|  port1 = |LL| \nCalibrating FW {wheelId} \nattached 2 filter wheel(s): \n' \
                     'index 0: ID 0 Name EFW \nindex 1: ID 1 Name EFW \nselecting 1\nCalibrating \nDone\n'
        return wheelCalib

    def recv(self, buffersize, flags=None):
        """Return and remove fake response from buffer."""
        time.sleep(0.02)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
