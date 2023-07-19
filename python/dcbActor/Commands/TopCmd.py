#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from dcbActor.utils.dcbConfig import DcbConfig, CollSet


class TopCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        collSets = ' '.join([f'[<{setName}>]' for setName in CollSet.knownSets])

        self.vocab = [
            ('ping', '', self.ping),
            ('status', '[@all] [<controllers>]', self.status),
            ('monitor', '<controllers> <period>', self.monitor),
            ('config', '<fibers>', self.declareBundles),
            ('declareMasks', f'{collSets} [<colls>]', self.declareMasks),
            ('declareMasks', f'<install> [<into>] [<colls>]', self.declareMasks),
            ('declareBundles', f'{collSets} [<colls>]', self.declareBundles),
            ('declareBundles', f'<install> [<into>] [<colls>]', self.declareBundles),

            ('power', '@(off|on) @cableB', self.powerCableBIlluminator),
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
                                        keys.Key("into", types.String() * (1, None), help='collimator set'),
                                        keys.Key("colls", types.Int() * (1, None), help='collimator identifiers'),
                                        keys.Key("set1", types.String() * (1, None), help='collimator set 1 config'),
                                        keys.Key("set2", types.String() * (1, None), help='collimator set 2 config'),
                                        keys.Key("set3", types.String() * (1, None), help='collimator set 3 config'),
                                        keys.Key("set4", types.String() * (1, None), help='collimator set 4 config'),
                                        keys.Key("oneColl", types.String() * (1, None), help='one collimator'),
                                        )

    @property
    def dcbConfig(self):
        return self.actor.dcbConfig

    @property
    def pdu(self):
        try:
            return self.actor.controllers['lamps']
        except KeyError:
            raise RuntimeError('lamps controller is not connected.')

    def monitor(self, cmd):
        """ Enable/disable/adjust period controller monitors. """

        period = cmd.cmd.keywords['period'].values[0]
        controllers = cmd.cmd.keywords['controllers'].values

        foundOne = False
        for c in controllers:
            if c not in self.actor.knownControllers:
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
        cmd.inform('text=%s' % "Present!")
        cmd.inform('text="monitors: %s"' % self.actor.monitors)
        cmd.inform('text="config id=0x%08x %r"' % (id(self.actor.actorConfig), self.actor.actorConfig.keys()))

        self.actor.metaStates.update(cmd)

        if 'all' in cmdKeys:
            for controller in self.actor.controllers:
                self.actor.callCommand("%s status" % controller)
        if 'controllers' in cmdKeys:
            for controller in cmdKeys['controllers'].values:
                self.actor.callCommand("%s status" % controller)

        if not self.dcbConfig:
            self.actor.reloadConfiguration()

        self.dcbConfig.genKeys(cmd)
        cmd.finish(self.controllerKey())

    def declareMasks(self, cmd):
        def retrieveFNumber(vals):
            fNumbers = []

            for val in vals:
                try:
                    fNumbers.append(DcbConfig.validFNumbers[str(val)])
                except KeyError:
                    raise ValueError(f'wrong f-number:{val}, valid:{",".join(DcbConfig.validFNumberKeys)}')

            return fNumbers

        cmdKeys = cmd.cmd.keywords
        fNumbers = dict()
        fNumbers['colls'] = cmdKeys['colls'].values if 'colls' in cmdKeys else None

        # if 'install' in cmdKeys:
        #     fNumber = retrieveFNumber('install')
        #     setNames = cmdKeys['into'].values if 'into' in cmdKeys else self.dcbConfig.setNames
        #     for setName in setNames:
        #         fNumbers[setName] = fNumber

        for i, setName in enumerate(CollSet.knownSets):
            if setName in cmdKeys:
                fNumbers[setName] = retrieveFNumber(cmdKeys[setName].values)

        self.dcbConfig.declareMasks(cmd, **fNumbers)
        self.dcbConfig.genKeys(cmd)

        cmd.finish()

    def declareBundles(self, cmd):
        def validateBundleSet(bundleSet):
            for bundle in bundleSet:
                if bundle not in DcbConfig.validBundles:
                    raise ValueError(f'invalid bundle :{bundle}, valid:{",".join(DcbConfig.validBundles)}')
            return [str(bundle) for bundle in bundleSet]

        cmdKeys = cmd.cmd.keywords
        bundleSets = dict()
        bundleSets['colls'] = cmdKeys['colls'].values if 'colls' in cmdKeys else None

        for i, setName in enumerate(CollSet.knownSets):
            if setName in cmdKeys:
                bundleSets[setName] = validateBundleSet(cmdKeys[setName].values)

        if 'fibers' in cmdKeys:
            install = cmdKeys['fibers'].values
        elif 'install' in cmdKeys:
            install = cmdKeys['install'].values
        else:
            install = False

        if install:
            if 'into' in cmdKeys:
                setName = cmdKeys['into'].values[0]
            else:
                try:
                    [setName] = self.dcbConfig.setNames
                except:
                    raise ValueError(f'ambiguous bundles definition... '
                                     f'please precise one collimator set:{",".join(self.dcbConfig.setNames)}')
            bundleSets[setName] = validateBundleSet(install)

        self.dcbConfig.declareBundles(cmd, **bundleSets)
        self.dcbConfig.genKeys(cmd)

        cmd.finish()

    def powerCableBIlluminator(self, cmd):
        """Switch on/off cableB illuminator."""
        cmdKeys = cmd.cmd.keywords

        state = 'on' if 'on' in cmdKeys else 'off'

        self.pdu.crudeSwitch(cmd, 'cableB', state)
        self.pdu.getStatus(cmd)

        cmd.finish()
