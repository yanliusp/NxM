import numpy as np

from ROOT import TH1F

from utils import create_name_hist, draw_hists

class NoisePSDGenerator:

    def __init__( self, num_channels, num_bins_t ):
        self.num_channels = num_channels
        self.num_bins_t = num_bins_t

        self.loop_channels = range( self.num_channels )
        self.loop_bins_t = range( self.num_bins_t )

        self.cumul_V = [ [ [ 0.0 for n in self.loop_bins_t ] for b in self.loop_channels ] for a in self.loop_channels ]
        self.event_count = 0

    def IncludeEvent( self, S ):
        S_fft = [ np.fft.fft( S[ a ] ).tolist() for a in self.loop_channels ]

        for a in self.loop_channels:
            for b in self.loop_channels:
                for n in self.loop_bins_t:
                    self.cumul_V[ a ][ b ][ n ] += np.conj( S_fft[ a ][ n ] )*S_fft[ b ][ n ]

        self.event_count += 1

        return True

    def CalculateNoisePSDs( self ):
        if self.event_count == 0:
            return None

        noise_psds = []

        for a in self.loop_channels:
            noise_psds.append( [] )

            for b in self.loop_channels:
                noise_psds[ -1 ].append( [ self.cumul_V[ a ][ b ][ n ]/float( self.event_count ) for n in self.loop_bins_t ] )

        return noise_psds


    def Draw( self, path ):
        noise_psds = self.CalculateNoisePSDs()

        if type( noise_psds ) != list:
            return False

        hists = []

        for a in self.loop_channels:
            hists.append( TH1F( create_name_hist(), '', int(( self.num_bins_t+2 )/2), 0.0, float( ( self.num_bins_t+2 )/2 ) ) )

        for a in self.loop_channels:
            for b in self.loop_channels:
                for n in range( int (( self.num_bins_t+2 )/2) ):
                    hists[ b ].SetBinContent( n+1, np.absolute( noise_psds[ a ][ b ][ n ] ) )

            filename = path+'/'+self.__class__.__name__+'_spec_'+str( a+1 )+'.png'
            draw_hists( hists, [ 2+b for b in self.loop_channels ], 'Frequency (bin)', '', filename, a, True, True )

            for hist in hists:
                hist.Reset()

        for hist in hists:
            hist.Delete()

        return True

