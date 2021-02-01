__author__ = 'alefur'

import dcbActor.utils.makeLamDesign as lamConfig


class DcbConfig(object):
    """Placeholder to handle dcb collimators configuration :
    dcb cables have 12 fiber bundles: each of which can be wired to a collimator with a tweakable f-number.
    """
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
        """ Load persisted dcbMasks values.

           Returns
           -------
           masks : 'tuple'
               f-Number for 12 dcb collimators
           """
        try:
            masks = self.actor.instData.loadKey('dcbMasks')
        except:
            masks = ['none' for collId in DcbConfig.validCollIds]

        return masks

    def declareMask(self, newMasks):
        """Persist new dcbMasks.
           Parameters
           ----------
           newMasks : iterable of `str`
               f-Number for 12 dcb collimators.
           """
        masks = list(self.getMasks())

        for i, mask in enumerate(newMasks):
            if mask:
                masks[i] = mask

        self.actor.instData.persistKey('dcbMasks', *masks)

    def getBundles(self):
        """Load persisted dcbBundles values
           Returns
           -------
           bundles : 'tuple'
               dcb bundle for 12 dcb collimators.
           """
        try:
            bundles = self.actor.instData.loadKey('dcbBundles')
        except:
            bundles = ['none' for collId in DcbConfig.validCollIds]

        return bundles

    def declareBundles(self, newBundles):
        """Persist new dcb bundles configuration.
           Parameters
           ----------
           newBundles : iterable of `str`
               List of 12 bundles.
           """
        bundles = list(self.getBundles())

        for i, newBundle in enumerate(newBundles):
            if newBundle:
                if newBundle != 'none' and newBundle in bundles:
                    j = bundles.index(newBundle)
                    bundles[j] = 'none'
                bundles[i] = newBundle

        self.actor.instData.persistKey('dcbBundles', *bundles)
