#!/usr/bin/env python

import argparse
import configparser
import logging

import dcbActor.utils.makeLamDesign as lamConfig
from enuActor.main import enuActor


class DcbActor(enuActor):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        enuActor.__init__(self, name,
                          productName=productName,
                          configFile=configFile)


    def pfsDesignId(self, cmd):
        conf = configparser.ConfigParser()
        conf.read_file(open(self.config.get('dcb', 'fiberConfig')))
        fibers = [fib.strip() for fib in conf.get('current', 'fibers').split(',')]
        pfiDesignId = lamConfig.hashColors(fibers)

        cmd.inform('fiberConfig="%s"' % ';'.join(fibers))
        cmd.inform('designId=0x%016x' % pfiDesignId)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='dcb', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = DcbActor('dcb',
                        productName='dcbActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
