#!/usr/bin/env python


import dcbActor.utils.makeLamDesign as lamConfig
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from astropy import time as astroTime


class DcbConfig(object):
    validCollIds = tuple(range(1, 13))
    collNames = [f'coll{collId}' for collId in validCollIds]
    validMaskSize = '2.5', '2.8', '3.38', 'none'

    def __init__(self, actor):
        self.actor = actor

    def getMasks(self):
        try:
            masks = self.actor.instData.loadKey('masks')
        except:
            masks = ['none' for collId in DcbConfig.validCollIds]

        return masks

    def declareMask(self, newMasks):
        masks = list(self.getMasks())

        for i, mask in enumerate(newMasks):
            if mask:
                masks[i] = mask

        self.actor.instData.persistKey('masks', *masks)


class TopCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.dcbConfig = DcbConfig(actor)
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        collArgs = ' '.join([f'[<{collName}>]' for collName in DcbConfig.collNames])

        self.vocab = [
            ('ping', '', self.ping),
            ('status', '[@all] [<controllers>]', self.status),
            ('monitor', '<controllers> <period>', self.monitor),
            ('config', '<fibers>', self.configFibers),
            ('declareMasks', f'[<install>] [<collIds>] {collArgs}', self.declareMasks),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("dcb__dcb", (1, 1),
                                        keys.Key("name", types.String(),
                                                 help='an optional name to assign to a controller instance'),
                                        keys.Key("controllers", types.String() * (1, None),
                                                 help='the names of 1 or more controllers to load'),
                                        keys.Key("controller", types.String(), help='the names a controller.'),
                                        keys.Key("period", types.Int(), help='the period to sample at.'),
                                        keys.Key("fibers", types.String() * (1, None), help='current fiber bundles'),
                                        keys.Key("install", types.String() * (1, None), help=''),
                                        keys.Key("collIds", types.Int() * (1, None), help='collimator ids'),
                                        keys.Key("coll1", types.String(), help='collimator 1 config'),
                                        keys.Key("coll2", types.String(), help='collimator 2 config'),
                                        keys.Key("coll3", types.String(), help='collimator 3 config'),
                                        keys.Key("coll4", types.String(), help='collimator 4 config'),
                                        keys.Key("coll5", types.String(), help='collimator 5 config'),
                                        keys.Key("coll6", types.String(), help='collimator 6 config'),
                                        keys.Key("coll7", types.String(), help='collimator 7 config'),
                                        keys.Key("coll8", types.String(), help='collimator 8 config'),
                                        keys.Key("coll9", types.String(), help='collimator 9 config'),
                                        keys.Key("coll10", types.String(), help='collimator 10 config'),
                                        keys.Key("coll11", types.String(), help='collimator 11 config'),
                                        keys.Key("coll12", types.String(), help='collimator 12 config'),
                                        )

    def monitor(self, cmd):
        """ Enable/disable/adjust period controller monitors. """

        period = cmd.cmd.keywords['period'].values[0]
        controllers = cmd.cmd.keywords['controllers'].values

        knownControllers = [c.strip() for c in self.actor.config.get(self.actor.name, 'controllers').split(',')]

        foundOne = False
        for c in controllers:
            if c not in knownControllers:
                cmd.warn('text="not starting monitor for %s: unknown controller"' % (c))
                continue

            self.actor.monitor(c, period, cmd=cmd)
            foundOne = True

        if foundOne:
            cmd.finish()
        else:
            cmd.fail('text="no controllers found"')

    def controllerKey(self):
        """Return controllers keyword
        """
        controllerNames = list(self.actor.controllers.keys())
        key = 'controllers=%s' % (','.join([c for c in controllerNames]) if controllerNames else None)

        return key

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords
        self.actor.sendVersionKey(cmd)
        cmd.inform('text=%s' % ("Present!"))
        cmd.inform('text="monitors: %s"' % (self.actor.monitors))
        cmd.inform('text="config id=0x%08x %r"' % (id(self.actor.config),
                                                   self.actor.config.sections()))

        self.actor.updateStates(cmd=cmd)
        self.actor.pfsDesignId(cmd=cmd)

        if 'all' in cmdKeys:
            for controller in self.actor.controllers:
                self.actor.callCommand("%s status" % controller)
        if 'controllers' in cmdKeys:
            for controller in cmdKeys['controllers'].values:
                self.actor.callCommand("%s status" % controller)

        cmd.finish(self.controllerKey())

    def configFibers(self, cmd):
        cmdKeys = cmd.cmd.keywords
        fibers = [fib.strip() for fib in cmdKeys['fibers'].values]

        for fiber in fibers:
            if fiber not in lamConfig.FIBER_COLORS:
                raise KeyError(f'{fiber} not in {",".join(lamConfig.FIBER_COLORS)}')

        self.actor.instData.persistKey('fiberConfig', *fibers)
        self.actor.pfsDesignId(cmd=cmd)

        cmd.finish()

    def declareMasks(self, cmd):
        cmdKeys = cmd.cmd.keywords
        if 'install' in cmdKeys:
            maskSize = str(cmdKeys['install'].values[0])
            if maskSize not in DcbConfig.validMaskSize:
                raise ValueError(f'wrong mask value:{maskSize}, existing :{",".join(DcbConfig.validMaskSize)}')
        else:
            maskSize = False

        collIds = cmdKeys['collIds'].values if 'collIds' in cmdKeys else DcbConfig.validCollIds
        masks = [maskSize for collId in collIds]

        for i, collName in enumerate(DcbConfig.collNames):
            if collName in cmdKeys:
                maskSize = str(cmdKeys[collName].values[0])
                if maskSize not in DcbConfig.validMaskSize:
                    raise ValueError(f'wrong mask value:{maskSize}, existing :{",".join(DcbConfig.validMaskSize)}')
                masks[i] = maskSize

        self.dcbConfig.declareMask(masks)

        cmd.inform(f'dcbConfigDate={astroTime.Time.now().mjd:0.6f}')
        cmd.inform(f'dcbMasks={",".join(self.dcbConfig.getMasks())}')
        cmd.finish()

    def toto(self, cmd):
        pass
