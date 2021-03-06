import sys
sys.path.append("../core/")
import math
import numpy as np
import os
from matplotlib import pyplot as plt
from scipy.signal import find_peaks, wiener, peak_widths

from ROOT import TFile, TGraph, TH1F

from DataReader           import DataReader
from NoisePSDGenerator    import NoisePSDGenerator
from save_noise_psds      import save_noise_psds
from get_noise_psds       import get_noise_psds
from calc_r               import calc_r
from calc_theta           import calc_theta
from estimate_bins_part   import estimate_bins_part
from TemplateGeneratorNxM import TemplateGeneratorNxM
from save_templates_nxm   import save_templates_nxm
from get_templates_nxm    import get_templates_nxm
from OFManagerNxM         import OFManagerNxM
from filter_wiener        import filter_wiener


sys.stdout.flush()
from utils import create_name_hist, get_angle_std, configure_draw, vector_distribution, draw_hists, draw_graphs, tree_manager

NUM_CHANNELS = 6
NUM_BINS_T = 32768
DT = 0.0016    # Width of the time bins
T_PRE = 25.728 # Interval of time between the start of the trace and the trigger, note that it is positive

GENERATE_NOISE_PSDS = False
PREVIEW_DATA = False
GENERATE_TEMPLATES = True
APPLY_FILTERS = False
CHECK = False

PATH = os.environ[ 'PWD' ]

STEP_MONITOR = 1000  # Print-outs and drawings each 10 events
STAT_ESTIMATE = 10 # Estimate the segmentation requiring at least 10 events per bin

#configure_draw()

def generate_noise_psds( inputfilepath, series , filename_data_noise, filename_noise_psds ):
    print('generate_noise_psds')

    gen = NoisePSDGenerator( NUM_CHANNELS, NUM_BINS_T )

    dr = DataReader()
    dr.OpenFile(  inputfilepath, series, 0 )

    event_count = 0

    while dr.LoadEvent(trigger='BOR'):
        #from here
        trace =  dr.GetTraces()
        dataS1 = np.asarray(trace)
        dataS1 = np.sum(dataS1, axis=0)
        if (np.mean(dataS1[0:3000])>np.mean(dataS1[3000:10000]) and np.mean(dataS1[0:3000])>np.mean(dataS1[10000:15000]) and np.mean(dataS1[0:3000])>np.mean(dataS1[30000:32000])): continue
        if (np.mean(dataS1[0:3000]) > 1.05*np.mean(dataS1[30000:32000])) : continue 
        if (1.05*np.mean(dataS1[0:3000]) < np.mean(dataS1[30000:32000])) : continue
        peaks, properties = find_peaks(dataS1.transpose(), prominence=1, width= 20)
        if (len(peaks)==0):
        #to here
            gen.IncludeEvent( dr.GetTraces() )
            event_count += 1
            if event_count%STEP_MONITOR == 0:
                print('Event %d' %event_count)

    dr.CloseFile()

    noise_psds = gen.CalculateNoisePSDs()

    if type( noise_psds ) == list:
        save_noise_psds( noise_psds, filename_noise_psds )

    gen.Draw( PATH+'/png' )

def preview_data(  inputfilepath, series, filename_noise_psds,  stat_estimate ):
    print('preview_data')

    E_min = 0.
    E_max = 1E12

    V = get_noise_psds( filename_noise_psds )

    vd = vector_distribution()

    dr = DataReader()
    dr.OpenFile(  inputfilepath, series )

    event_count = 0

    while dr.LoadEvent(trigger='Trigger'):
        S = dr.GetTraces()
        dataS = np.asarray(S)
        dataS = np.sum(dataS, axis=0)
        #after the conversion to A too small number, find_peaks doesn't work
        dataS = dataS*1E7
        peaks, properties = find_peaks(dataS.transpose(), prominence=1, width=200)
        if (len(peaks) == 0 or len(peaks) > 1) : continue

         #using scipy wiener filter
        noise_w = np.array([V[a][a] for a in range(len(S))])

        amps = [ sum( wiener( S[ a ], mysize=75, noise = noise_w[a].real ) ) for a in range(len(S)) ]
        event_count += 1
        
        if event_count%STEP_MONITOR == 0:
            print('Event', event_count)

        if  calc_r( amps ) > 5 : continue

        E = sum( amps )

        if E > E_min and E < E_max:
            vd.add( get_angle_std( calc_theta( amps ) ), calc_r( amps ) )
    
    dr.CloseFile()

    if vd.get_size() > 0:
        graph = TGraph( vd.get_size(), vd.get_array_x(), vd.get_array_y() )

        lines = estimate_bins_part( stat_estimate, vd )
        for line in lines:
            line.SetLineColor( 15 )
          
        limits_x = [ -math.pi                                 , math.pi                                   ]
        limits_y = [ min( [ line.GetY1() for line in lines ] ), max( [ line.GetY1() for line in lines ] ) ]
        filename = PATH+'/png/preview_data.png'
        draw_graphs( [ graph ], [ 2 ], 0.5, '#theta', 'r', limits_x, limits_y, filename, lines )

        graph.Delete()

def generate_templates( inputfilepath, series, filename_noise_psds, vec_r_lim, mat_theta_lim, filename_templates ):
    print('generate_templates')

    E_min = 0.
    E_max = 1E12

    V = get_noise_psds( filename_noise_psds )

    gen = TemplateGeneratorNxM( V, calc_r, calc_theta, E_min, E_max, vec_r_lim, mat_theta_lim )

    dr = DataReader()
    dr.OpenFile( inputfilepath, series, 0 )

    event_count = 0

    while dr.LoadEvent(trigger='Trigger'):
        gen.IncludeEvent( dr.GetTraces() )
        event_count += 1

        if event_count%STEP_MONITOR == 1:
            print('Event', event_count)

    dr.CloseFile()

    templates = gen.GetTemplates()

    if type( templates ) == list:
        map_bins_part = gen.GetMapBinsPart()
        save_templates_nxm( templates, E_min, E_max, map_bins_part, filename_templates )

    gen.Draw( PATH+'/png' )

def apply_filters( filename_noise_psds, filename_templates, inputfilepath, series, filename_root ):
    print('apply_filters')

    V = get_noise_psds( filename_noise_psds )
    templates, E_min, E_max, map_bins_part = get_templates_nxm( filename_templates )

    man = OFManagerNxM( DT, T_PRE, templates, V, calc_r, calc_theta, E_min, E_max, map_bins_part )

    dr = DataReader()
    dr.OpenFile(  inputfilepath, series, 0 )

    tm_nxm = tree_manager( 'NxM' )

    tm_nxm.Branch( 't0'    )
    tm_nxm.Branch( 'chisq' )
    tm_nxm.Branch( 'E'     )

    event_count = 0

    while dr.LoadEvent(trigger='Trigger'):
        S = dr.GetTraces()
        dataS = np.asarray(S)
        dataS = np.sum(dataS, axis=0)
        if (np.mean(dataS[0:3000])>np.mean(dataS[3000:10000]) and np.mean(dataS[0:3000])>np.mean(dataS[10000:15000]) and np.mean(dataS[0:3000])>np.mean(dataS[30000:32000])): continue
        if (np.mean(dataS[0:3000]) > 1.05*np.mean(dataS[30000:32000])) : continue 
        if (1.05*np.mean(dataS[0:3000]) < np.mean(dataS[30000:32000])) : continue
        dataS = dataS*1E7
        peaks, properties = find_peaks(dataS.transpose(), prominence=1, width=20)
        width_half = peak_widths(dataS.transpose(), peaks, rel_height=0.5)

        if (len(peaks) == 0 or len(peaks) > 1 or any(width_half)>2000) :
            continue
        tmp_S = np.array(S)
        avg =  np.mean(tmp_S[:,0:5000],axis=1) 
        for i in range(len(S)):
            S[i] = S[i]-avg[i]


        result = man.ProcessEvent( S )

        event_count += 1


        if event_count%STEP_MONITOR == 0 :
            print('Event', event_count)
            man.Draw( PATH+'/png', event_count )

        if type( result ) == dict:
            tm_nxm[ 't0'    ] = result[ 't0'    ]
            tm_nxm[ 'chisq' ] = result[ 'chisq' ]
            tm_nxm[ 'E'     ] = result[ 'E'     ]

        else:
            tm_nxm[ 't0'    ] = -999999.0
            tm_nxm[ 'chisq' ] = -999999.0
            tm_nxm[ 'E'     ] = -999999.0

        tm_nxm.Fill()

    dr.CloseFile()

    filepointer = TFile( filename_root, 'recreate' )
    tm_nxm.Write()
    filepointer.Close()

def check( filename_noise_psds, filename_templates, filename_root ):
    print('check')

    list_E = []

    hist = TH1F( create_name_hist(), '', 100, 0.0, 2.0 )

    filepointer = TFile( filename_root )
    tree_nxm = filepointer.Get( 'NxM' )

    for event_index in range( tree_nxm.GetEntries() ):
        tree_nxm.GetEntry( event_index )

        list_E.append( tree_nxm.E )
        hist.Fill( list_E[ -1 ] )
    filepointer.Close()

    print('std( list_E ) \t', float( np.std( list_E  ) ), '\tmean( list_E )\t', float( np.mean( list_E ) ))

    filename = PATH+'/png/check.png'
    draw_hists( [ hist ], [ 2 ], 'E_{rec}', '', filename )

    hist.Delete()

# path to directory containing data files
filepath='/gpfs/slac/staas/fs1/g/supercdms//data/CDMS/SLAC/R56/Raw/09190602_1927'
 
# specifies series to be analyzed
series=["09190602_1927_F0"+str(i)+".mid.gz" for i in range(100,140)] 

if GENERATE_NOISE_PSDS:
    generate_noise_psds(filepath, series, 'data_noise.gz', PATH+'/noise_psds.gz' )

if PREVIEW_DATA:
    preview_data( filepath, series, PATH+'/noise_psds.gz',  STAT_ESTIMATE )

if GENERATE_TEMPLATES:
    from bins_part import vec_r_lim, mat_theta_lim
    generate_templates( filepath, series, PATH+'/noise_psds.gz', vec_r_lim, mat_theta_lim, PATH+'/templates.gz' )

if APPLY_FILTERS:
    apply_filters( PATH+'/noise_psds.gz', PATH+'/templates.gz', filepath, series, PATH+'/root/reco.root' )

if CHECK:
    check( PATH+'/noise_psds.gz', PATH+'/templates.gz', PATH+'/root/reco.root' )

