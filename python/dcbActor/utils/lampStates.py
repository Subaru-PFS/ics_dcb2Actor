__author__ = 'alefur'

from datetime import datetime as dt


class LampState(object):
    """ Handle lamp state and keywords. """

    def __init__(self):
        start = dt.utcnow()
        self.state = 'unknown'
        self.onTimestamp = start
        self.offTimestamp = start

    @property
    def lampOn(self):
        return self.state == 'on'

    def __str__(self):
        #return f'{self.state},{self.onTimestamp.isoformat()},{self.offTimestamp.isoformat()}'
        secs = 0 if not self.lampOn else (dt.utcnow()-self.onTimestamp).total_seconds()
        return f'{self.state},{secs}'


    def setState(self, state, genTimeStamp=False):
        """ Update current state and generate timestamp is requested. """
        self.state = state
        if genTimeStamp:
            self.genTimeStamp()

    def genTimeStamp(self):
        """ Generate timestamp as utc time. """
        if self.lampOn:
            self.onTimestamp = dt.utcnow()
        else:
            self.offTimestamp = dt.utcnow()

    def elapsed(self):
        """ Return number of seconds since the lamp is actually on. """
        if not self.lampOn:
            return 0

        return (dt.utcnow() - self.onTimestamp).total_seconds()


class LampStates(dict):
    """ Lamp state dictionnary. """

    def __init__(self, lampsName):
        for lamp in lampsName:
            self[lamp] = LampState()

    def elapsed(self, lamp):
        """ Return number of seconds since the given lamp is actually on. """
        return self[lamp].elapsed()

    def genKeys(self, cmd, ret, genTimeStamp=False):
        """ Generate lamps keywords. """
        lamp, state = [r.strip() for r in ret.split('=')]
        self[lamp].setState(state, genTimeStamp=genTimeStamp)

        cmd.inform(f'{lamp}={str(self[lamp])}')
