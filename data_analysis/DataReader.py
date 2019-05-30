from scdmsPyTools.BatTools.IO import *
from pandas import * 
import numpy as np 
from DataReader_base  import DataReader_base

from ROOT import TH1F
from utils import create_name_hist, draw_hists


class DataReader( DataReader_base ):

    def __init__( self ):
        DataReader_base.__init__( self )

        self.filepath = None
        self.series = None
        self.event_count = None
        self.num_events = None

    def OpenFile( self, filepath, series, num_events=0)  :

        self.ev = getRawEvents(filepath,series, outputFormat=2)
        self.event_count = 0
        if (num_events==0):
            self.num_events = len(self.ev)
        else: self.num_events = min(num_events, len(self.ev))
        return True

    def LoadEvent( self , channels = 'all', side = 'S1'):

        if (channels == 'all'):
            if (side == 'S1'):
                channels = ['PAS1','PBS1','PCS1','PDS1','PES1','PFS1']
            if (side == 'S2'):
                channels = ['PAS2','PBS2','PCS2','PDS2','PES2','PFS2']

        self.traces = []
        if self.event_count < self.num_events:
            for ch in channels:
                self.traces.append(self.ev[self.event_count]['Z6'][ch])
            self.S = self.traces
            self.event_count += 1
            return True

        self.S = None
        return False

    def CloseFile( self ):

        self.num_events = None

        self.event_count = None

        self.S = None

        return True


 
