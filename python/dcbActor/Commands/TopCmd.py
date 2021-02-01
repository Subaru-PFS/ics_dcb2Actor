#!/usr/bin/env python


import dcbActor.utils.makeLamDesign as lamConfig
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from astropy import time as astroTime


class DcbConfig(object):
    validCollIds = tuple(range(1, 13))
    collNames = [f'coll{collId}' for collId in validCollIds]

    fNumbers = ['2.5', '2.8', '3.38']
    validFNumbers = dict([(fNumber, f'f{fNumber}') for fNumber in fNumbers] +
                         [(f'f{fNumber}', f'f{fNumber}') for fNumber in fNumbers] +
                         [('none', 'none')])

    validFNumberKeys = set(validFNumbers.values())

    validBundles = ['none'] + list(lamConfig.FIBER_COLORS.keys())

    def __init__(self, actor):
        self.actor = actor

    def getMasks(self):
        try:
            masks = self.actor.instData.loadKey('dcbMasks')
        except:
            masks = ['none' for collId in DcbConfig.validCollIds]

        return masks

    def declareMask(self, newMasks):
        masks = list(self.getMasks())

        for i, mask in enumerate(newMasks):
            if mask:
                masks[i] = mask

        self.actor.instData.persistKey('dcbMasks', *masks)

    def getBundles(self):
        try:
            masks = self.actor.instData.loadKey('dcbBundles')
        except:
            masks = ['none' for collId in DcbConfig.validCollIds]

        return masks

    def declareBundles(self, newBundles):
        bundles = list(self.getBundles())

        for i, newBundle in enumerate(newBundles):
            if newBundle:
                if newBundle != 'none' and newBundle in bundles:
                    j = bundles.index(newBundle)
                    bundles[j] = 'none'
                bundles[i] = newBundle

        self.actor.instData.persistKey('dcbBundles', *bundles)


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
            ('config', '<fibers>', self.declareBundles),
            ('declareMasks', f'[<install>] [<collIds>] {collArgs}', self.declareMasks),
            ('declareBundles', f'[<install>] [<collIds>] {collArgs}', self.declareBundles),
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

        if 'all' in cmdKeys:
            for controller in self.actor.controllers:
                self.actor.callCommand("%s status" % controller)
        if 'controllers' in cmdKeys:
            for controller in cmdKeys['controllers'].values:
                self.actor.callCommand("%s status" % controller)

        self.genDcbConfigKeys(cmd)
        cmd.finish(self.controllerKey())

    def declareMasks(self, cmd):
        cmdKeys = cmd.cmd.keywords
        fNumber = False
        masks = [fNumber for collId in DcbConfig.validCollIds]

        if 'install' in cmdKeys:
            key = str(cmdKeys['install'].values[0])
            try:
                fNumber = DcbConfig.validFNumbers[key]
            except KeyError:
                raise ValueError(f'wrong f-number:{key}, valid:{",".join(DcbConfig.validFNumberKeys)}')

        collIds = cmdKeys['collIds'].values if 'collIds' in cmdKeys else DcbConfig.validCollIds
        for collId in collIds:
            if collId not in DcbConfig.validCollIds:
                print(collId)
                print(DcbConfig.validCollIds)
                raise ValueError(f'wrong collId:{collId}, valid:{",".join(map(str, DcbConfig.validCollIds))}')
            masks[collId - 1] = fNumber

        for i, collName in enumerate(DcbConfig.collNames):
            if collName in cmdKeys:
                key = str(cmdKeys[collName].values[0])
                try:
                    fNumber = DcbConfig.validFNumbers[key]
                except KeyError:
                    raise ValueError(f'wrong f-number:{key}, valid:{",".join(DcbConfig.validFNumberKeys)}')
                masks[i] = fNumber

        self.dcbConfig.declareMask(masks)
        cmd.inform(f'dcbConfigDate={astroTime.Time.now().mjd:0.6f}')

        self.genDcbConfigKeys(cmd)
        cmd.finish()

    def declareBundles(self, cmd):
        cmdKeys = cmd.cmd.keywords
        bundles = [False for collId in DcbConfig.validCollIds]

        if 'fibers' in cmdKeys:
            bundles = ['none' for collId in DcbConfig.validCollIds]
            install = cmdKeys['fibers'].values
        elif 'install' in cmdKeys:
            install = cmdKeys['install'].values
        else:
            install = False

        if install:
            collIds = cmdKeys['collIds'].values if 'collIds' in cmdKeys else range(1, len(install) + 1)
            if len(install) != len(collIds):
                raise ValueError('len(install) has to match collIds')
            for collId, bundle in zip(collIds, install):
                if collId not in DcbConfig.validCollIds:
                    raise ValueError(f'wrong collId:{collId}, valid:{",".join(map(str, DcbConfig.validCollIds))}')
                if bundle not in DcbConfig.validBundles:
                    raise ValueError(f'invalid bundle :{bundle}, valid:{",".join(DcbConfig.validBundles)}')
                bundles[collId - 1] = str(bundle)

        for i, collName in enumerate(DcbConfig.collNames):
            if collName in cmdKeys:
                bundle = str(cmdKeys[collName].values[0])
                if bundle not in DcbConfig.validBundles:
                    raise ValueError(f'invalid bundle :{bundle}, valid:{",".join(DcbConfig.validBundles)}')
                bundles[i] = bundle

        self.dcbConfig.declareBundles(bundles)
        cmd.inform(f'dcbConfigDate={astroTime.Time.now().mjd:0.6f}')

        self.genDcbConfigKeys(cmd)
        cmd.finish()

    def genDcbConfigKeys(self, cmd):
        bundles = self.dcbConfig.getBundles()
        colors = [bundle for bundle in bundles if bundle != 'none']
        pfiDesignId = lamConfig.hashColors(colors)

        cmd.inform(f'dcbBundles={",".join(bundles)}')
        cmd.inform(f'dcbMasks={",".join(self.dcbConfig.getMasks())}')
        cmd.inform('designId=0x%016x' % pfiDesignId)
        cmd.inform('fiberConfig="%s"' % ';'.join(colors))
