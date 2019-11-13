#!/usr/bin/env python


from enuActor.Commands import PduCmd as enuPdu


class PduCmd(enuPdu.PduCmd):
    def __init__(self, actor):
        enuPdu.PduCmd.__init__(self, actor)
