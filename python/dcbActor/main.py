#!/usr/bin/env python

import argparse
import logging
from importlib import reload

import dcbActor.utils.dcbConfig as dcbConfig
import ics.utils.fsm.fsmActor as fsmActor

reload(dcbConfig)


class DcbActor(fsmActor.FsmActor):
    knownControllers = ['lamps', 'filterwheel']
    # we start everything by default
    startingControllers = knownControllers

    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        self.dcbConfig = None
        fsmActor.FsmActor.__init__(self, name,
                                   productName=productName,
                                   configFile=configFile,
                                   logLevel=logLevel)

    def letsGetReadyToRumble(self):
        """Just startup nicely."""

        toStart = list(set(DcbActor.startingControllers) - set(self.ignoreControllers))

        for controller in toStart:
            self.connect(controller)

    def reloadConfiguration(self, cmd):
        """Reload dcb configuration and keywords."""
        self.dcbConfig = dcbConfig.DcbConfig(self)
        self.dcbConfig.genKeys(cmd)

    def attachController(self, name, instanceName=None, **kwargs):
        """Regular ICC attach controller with a gotcha for lamps."""

        def findPduModel():
            """ Find pduModel being used from config file. """
            try:
                pduModel = self.actorConfig['lamps']['pduModel']
            except KeyError:
                raise RuntimeError(f'lamps pdu model is not properly described')

            if pduModel not in ['aten', 'digitalLoggers']:
                raise ValueError(f'unknown pduModel : {pduModel}')

            return pduModel

        if name == 'lamps':
            name = findPduModel()
            instanceName = 'lamps'

        return fsmActor.FsmActor.attachController(self, name, instanceName=instanceName, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='dcb', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = DcbActor(args.name,
                        productName='dcbActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
