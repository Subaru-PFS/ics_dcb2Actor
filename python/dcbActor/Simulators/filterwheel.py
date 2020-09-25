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
        self.buf.append('-.0014\n')
        

    def recv(self, buffersize, flags=None):
        """Return and remove fake response from buffer."""
        time.sleep(0.02)
        ret = self.buf[0]
        self.buf = self.buf[1:]
        return str(ret).encode()

    def close(self):
        pass
