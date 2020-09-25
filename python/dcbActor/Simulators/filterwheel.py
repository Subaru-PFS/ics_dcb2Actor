__author__ = 'alefur'

import socket
import time


class FilterwheelSim(socket.socket):
    def __init__(self):
        """Fake filterwheel tcp server."""
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
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
        wheelCalib = 'port0 = |UL|  port1 = |LL| \nCalibrating FW 1 \nattached 2 filter wheel(s): \n' \
                     'index 0: ID 0 Name EFW \nindex 1: ID 1 Name EFW \nselecting 1\nCalibrating \nDone\n'
        if 'adc' in cmdStr:
            self.buf.append('-.0014\n')

        elif 'linewheel' in cmdStr:
            __, position = cmdStr.split('linewheel')
            position = int(position)
            if position == -1:
                self.buf.append(wheelCalib)
            else:
                self.buf.append('port0 = UL  port1 = LL\n')
                self.buf.append('Setting FW 0 to position 1\nattached 2 filter wheel(s):\nindex 0: ID 0 Name EFW \n'
                                'index 1: ID 1 Name EFW \nselecting 0 \n5 slots: 1 2 3 4 5 \ncurrent position: 1\n'
                                f'Moving...\nMoved to position {position}\n')

        elif 'qthwheel' in cmdStr:
            __, position = cmdStr.split('qthwheel')
            position = int(position)

            if position == -1:
                self.buf.append(wheelCalib)
            else:
                self.buf.append('port0 = UL  port1 = LL\n')
                self.buf.append('Setting FW 0 to position 1\nattached 2 filter wheel(s):\nindex 0: ID 0 Name EFW \n'
                                'index 1: ID 1 Name EFW \nselecting 0 \n5 slots: 1 2 3 4 5 \ncurrent position: 1\n'
                                f'Moving...\nMoved to position {position}\n')

    def recv(self, buffersize, flags=None):
        """Return and remove fake response from buffer."""
        time.sleep(0.02)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
