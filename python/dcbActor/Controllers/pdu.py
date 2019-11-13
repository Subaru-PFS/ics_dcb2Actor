__author__ = 'alefur'
import logging

from enuActor.Controllers import pdu as enuPdu


class pdu(enuPdu.pdu):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: enuActor.
        :param name: controller name.
        :type name: str
        """

        enuPdu.pdu.__init__(self, actor, name, loglevel=loglevel)

    def authenticate(self, pwd=None):
        """| log to the telnet server

        :param cmd : current command,
        """
        enuPdu.pdu.authenticate(self, pwd='pfsait')