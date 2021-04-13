#!/usr/bin/env python

import argparse
import logging

from enuActor.main import enuActor


class DcbActor(enuActor):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        enuActor.__init__(self, name,
                          productName=productName,
                          configFile=configFile)

    def connectionMade(self):
        """Attach all controllers."""
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            setup = self.config.get(self.name, 'illumination').strip()
            sources = self.config.get(setup, 'pdu').strip()
            try:
                self.connect(sources, instanceName="sources")
            except Exception as e:
                self.logger.warn('text=%s' % self.strTraceback(e))

            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True


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
