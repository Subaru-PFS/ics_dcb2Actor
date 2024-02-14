__author__ = 'alefur'

import dcbActor.utils.makeLamDesign as lamConfig
import pandas as pd
from ics.utils import time as pfsTime


class CollSet(object):
    """Placeholder to handle collimator set configuration"""
    nColls = dict(set1=5, set2=5, set3=5, set4=5, oneColl=1)
    knownSets = list(nColls.keys())

    def __init__(self, dcbActor, setName):
        if setName not in CollSet.knownSets:
            raise KeyError(f'unkown set:{setName}, valids:{",".join(CollSet.knownSets)}')

        self.dcbActor = dcbActor
        self.setName = setName
        self.setId = CollSet.knownSets.index(setName) + 1
        self.nColls = CollSet.nColls[setName]

    @property
    def masksKey(self):
        """Generate per collimator set masks key."""
        return f'collSet{self.setId}Masks'

    @property
    def bundlesKey(self):
        """Generate per collimator set bundles key."""
        return f'collSet{self.setId}Bundles'

    @property
    def iColls(self):
        """Identifier for individual collimators."""
        return list(range(1, self.nColls + 1))

    @property
    def fNumbers(self):
        """Retrieve collimator set fNumbers. """
        timestamp, fNumbers = self.compareFNumbers()
        return fNumbers

    @property
    def bundles(self):
        """Retrieve collimator set bundles configuration. """
        timestamp, bundles = self.loadBundles()
        return bundles

    def loadFNumbers(self, dcb):
        """Load persisted fNumber conf.

        Returns
        -------
        timestamp :
            mjd timestamp.
        fNumbers :
            f-Numbers values.
        """
        try:
            fNumbers = self.dcbActor.actorData.loadKey(self.masksKey, actorName=dcb)
        except:
            fNumbers = 0, ('none',) * self.nColls

        return fNumbers

    def compareFNumbers(self):
        """Load both dcb and dcb2 fNumbers for that collimator set, return the most recent one.

        Returns
        -------
        timestamp : `float`
            mjd timestamp.
        fNumbers : tuple of `str`
            f-Numbers values.

        """
        fNumbers1 = self.loadFNumbers('dcb')
        fNumbers2 = self.loadFNumbers('dcb2')
        timestamp, fNumbers = max(fNumbers1, fNumbers2)
        return timestamp, fNumbers

    def loadBundles(self):
        """Load persisted bundle conf for that collimator set.

        Returns
        -------
        bundle : tuple of `str`
            plugged fiber bundle.
        """
        try:
            bundles = self.dcbActor.actorData.loadKey(self.bundlesKey, actorName=self.dcbActor.name)
        except:
            bundles = 0, ('none',) * self.nColls

        return bundles

    def declareMasks(self, cmd, fNumbers, colls=None):
        """Persist masks configuration for that collimator set.

        Parameters
        ----------
        cmd :
            mhs command.
        colls : iterable of `int`
            matching collimator ids.
        fNumber : `str`
            fNumber value to apply.
        """
        iColls = self.iColls if colls is None else colls

        for iColl, fNumber in zip(iColls, fNumbers):
            try:
                fNumbers[iColl - 1] = fNumber
            except IndexError:
                raise ValueError(f'unknown coll{iColl} for {self.setName}, valids:{",".join(map(str, self.iColls))}')

            cmd.inform(f'text="declaring {fNumber} for {self.setName}:coll{iColl}')

        self.dcbActor.actorData.persistKey(self.masksKey, float(pfsTime.Time.now().mjd), fNumbers)

    def declareBundles(self, cmd, bundleSet, colls=None):
        """Persist fiber bundles configuration for that collimator set.

        Parameters
        ----------
        cmd :
            mhs command.
        colls : iterable of `int`
            matching collimator ids.
        bundleSet : list of `str`
            list of fiber bundle.
        """
        bundles = list(self.bundles)

        iColls = self.iColls if colls is None else colls
        if len(bundleSet) != len(iColls):
            raise ValueError(f'len(bundleSet):{len(bundleSet)} has to match nColls:{len(iColls)}')

        for iColl, bundle in zip(iColls, bundleSet):
            try:
                bundles[iColl - 1] = bundle
            except IndexError:
                raise ValueError(f'unknown coll{iColl} for {self.setName}, valids:{",".join(map(str, self.iColls))}')

            cmd.inform(f'text="declaring {bundle} for {self.setName}:coll{iColl}')

        self.dcbActor.actorData.persistKey(self.bundlesKey, float(pfsTime.Time.now().mjd), bundles)

    def dataFrame(self):
        """Generate pandas dataframe describing collimator set

        Returns
        -------
        df :
            pd.DataFrame
        """
        timestamp1, fNumbers = self.compareFNumbers()
        timestamp2, bundles = self.loadBundles()
        timestamp = max(timestamp1, timestamp2)

        table = [(self.setName, timestamp, i + 1, fNbr, bndl) for i, (fNbr, bndl) in enumerate(zip(fNumbers, bundles))]
        return pd.DataFrame(table, columns=['setName', 'timestamp', 'iColl', 'fNumber', 'bundle'])

    def genKeys(self, cmd):
        """Generate per collimator set keywords.

        Parameters
        ----------
        cmd :
            mhs command.
        """
        cmd.inform(f'{self.masksKey}={",".join(list(self.fNumbers))}')
        cmd.inform(f'{self.bundlesKey}={",".join(list(self.bundles))}')


class DcbConfig(object):
    """Placeholder to handle dcb collimators configuration"""

    fNumbers = ['2.5', '2.8', '3.38']
    validFNumbers = dict([(fNumber, f'f{fNumber}') for fNumber in fNumbers] +
                         [(f'f{fNumber}', f'f{fNumber}') for fNumber in fNumbers] +
                         [('none', 'none')])

    validFNumberKeys = set(validFNumbers.values())
    validBundles = ['none'] + list(lamConfig.FIBER_COLORS.keys())

    def __init__(self, actor):
        self.actor = actor
        self.collSetDict = self.fetchIlluminationSetup()

    @property
    def setNames(self):
        """Collimator set names."""
        return self.collSetDict.keys()

    @property
    def collSets(self):
        """Collimator sets."""
        return self.collSetDict.values()

    def fetchIlluminationSetup(self):
        """Load illumination setup(1-2)."""
        setup = self.actor.actorConfig['illumination']['setup']
        return self.fetchCollSets(setup)

    def fetchCollSets(self, setup):
        """Instantiate Collimator Sets from loaded dcb setup."""
        setNames = self.actor.actorConfig['setups'][setup]
        return dict([(setName, CollSet(self.actor, setName)) for setName in setNames])

    def declareMasks(self, cmd, colls=None, **fNumbers):
        """Persist new dcbMasks for multiple collimator sets.

        Parameters
        ----------
        cmd :
            mhs command.
        colls : iterable of `int`
            matching collimator ids.
        fNumbers : dict
            fNumber value per collimator set.
        """
        for setName, fNumber in fNumbers.items():
            if setName not in self.setNames:
                raise RuntimeError(f'{setName} is not into {self.actor.name} setup, valids:{",".join(self.setNames)}')

            self.collSetDict[setName].declareMasks(cmd, fNumber, colls=colls)

    def ensureBundleIsUnic(self, cmd, bundleSets):
        """dcb cables has only one bundle each, make sure that's the case.

        Parameters
        ----------
        cmd :
            mhs command.
        bundleSets : dict
            bundle list per collimator set.
        """
        for collSet in self.collSets:
            for setName, bundleSet in bundleSets.items():
                for bundle in bundleSet:
                    try:
                        index = collSet.bundles.index(bundle)
                        collSet.declareBundles(cmd, ['none'], [index + 1])
                    except ValueError:
                        continue

    def declareBundles(self, cmd, colls=None, **bundleSets):
        """Persist new dcb bundles configuration for multiple collimator sets.

        Parameters
        ----------
        cmd :
            mhs command.
        colls : iterable of `int`
            matching collimator ids.
        bundleSets : dict
            bundle list per collimator set.
        """
        self.ensureBundleIsUnic(cmd, bundleSets)

        for setName, bundleSet in bundleSets.items():
            if setName not in self.setNames:
                raise RuntimeError(f'{setName} is not into {self.actor.name} setup, valids:{",".join(self.setNames)}')

            self.collSetDict[setName].declareBundles(cmd, bundleSet, colls=colls)

    def dcbSetup(self):
        """Generate pandas dataframe describing dcb illumination setup

        Returns
        -------
        df :
            pd.DataFrame
        """
        return pd.concat([collSet.dataFrame() for collSet in self.collSets]).reset_index(drop=True)

    def genKeys(self, cmd):
        """Generate dcb config keywords.

        Parameters
        ----------
        cmd :
            mhs command.
        """

        def mergeCollSetConfig(config):
            """Merge collimator sets config to a single list."""
            allCollConfig = 12 * ['none']

            for iColl, value in zip(config.index, config):
                allCollConfig[iColl] = value

            return allCollConfig

        for collSet in self.collSets:
            collSet.genKeys(cmd)

        dcbSetup = self.dcbSetup()
        dcbKeys = dcbSetup.query('bundle!="none"')

        # Merge collSet config and preserve collimator index (INSTRM-2166)
        dcbMasks = mergeCollSetConfig(dcbKeys.fNumber)
        dcbBundles = mergeCollSetConfig(dcbKeys.bundle)

        dcbConfigDate = dcbSetup.timestamp.max()

        colors = dcbKeys.bundle.values.tolist()
        pfiDesignId = lamConfig.hashColors(colors)
        # Persisting pfsDesignId.
        self.actor.actorData.persistKey('pfsDesignId', '0x%016x' % pfiDesignId)

        cmd.inform('designId=0x%016x' % pfiDesignId)
        cmd.inform('fiberConfig="%s"' % ';'.join(colors))

        cmd.inform(f'dcbConfigDate={dcbConfigDate:0.6f}')
        cmd.inform(f'dcbMasks={",".join(map(str, dcbMasks))}')
        cmd.inform(f'dcbBundles={",".join(map(str, dcbBundles))}')
