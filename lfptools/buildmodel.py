#!/usr/bin/env python

# inst: university of bristol
# auth: jeison sosa
# mail: j.sosa@bristol.ac.uk / sosa.jeison@gmail.com

import os
import sys
import getopt
import subprocess
import configparser
import numpy as np
import pandas as pd
import gdalutils


def buildmodel(argv):
    """
    Main program to build a LISFLOOD-FP model
    """

    opts, args = getopt.getopt(argv, "i:")
    for o, a in opts:
        if o == "-i":
            inifile = a
    config = configparser.SafeConfigParser()
    config.read(inifile)

    parlfp = str(config.get('buildmodel', 'parlfp'))
    bcilfp = str(config.get('buildmodel', 'bcilfp'))
    bdylfp = str(config.get('buildmodel', 'bdylfp'))
    runcsv = str(config.get('buildmodel', 'runcsv'))
    evaplfp = str(config.get('buildmodel', 'evaplfp'))
    gaugelfp = str(config.get('buildmodel', 'gaugelfp'))
    stagelfp = str(config.get('buildmodel', 'stagelfp'))
    demtif = str(config.get('buildmodel', 'demtif'))
    dembnktif = str(config.get('buildmodel', 'dembnktif'))
    dembnktif_1D = str(config.get('buildmodel', 'dembnktif_1D'))
    fixbnktif = str(config.get('buildmodel', 'fixbnktif'))
    wdttif = str(config.get('buildmodel', 'wdttif'))
    bedtif = str(config.get('buildmodel', 'bedtif'))
    dirtif = str(config.get('buildmodel', 'dirtif'))
    reccsv = str(config.get('buildmodel', 'reccsv'))
    date1 = str(config.get('buildmodel', 'date1'))
    date2 = str(config.get('buildmodel', 'date2'))

    print("    running buildmodel.py...")

    t = (pd.to_datetime(date2, format='%Y-%m-%d') - pd.to_datetime(date1,
                                                                   format='%Y-%m-%d')).days + 1  # +1 to take into account the first date

    write_bci(bcilfp, runcsv)
    write_bdy(bdylfp, runcsv, t)
    write_evap(evaplfp, t)
    write_gauge_stage_all_cells(reccsv, dirtif, wdttif, gaugelfp, stagelfp)
    burn_banks_dem(dembnktif, demtif, fixbnktif)
    burn_banks_dem_1D(dembnktif_1D, demtif, fixbnktif)
    write_ascii(dembnktif_1D, wdttif, bedtif, dembnktif)
    write_par(parlfp, bcilfp, bdylfp, evaplfp, gaugelfp,
              stagelfp, dembnktif, wdttif, bedtif, t)


def write_gauge_stage_all_cells(reccsv, dirtif, wdttif, gaugelfp, stagelfp):

    print("     writing gauge and stage files...")

    # Reading rec file
    rec = pd.read_csv(reccsv)

    # Create a width dataframe
    dat = gdalutils.get_data(wdttif)
    geo = gdalutils.get_geo(wdttif)
    wdt = gdalutils.array_to_pandas(dat, geo, 0, 'gt')
    wdt.columns = ['x', 'y', 'width']

    # Create directions dataframe
    dat = gdalutils.get_data(dirtif)
    geo = gdalutils.get_geo(dirtif)
    drc = gdalutils.array_to_pandas(dat, geo, 0, 'gt')
    drc.columns = ['x', 'y', 'direction']

    # Find widths and directions for every lon, lat in river network
    gdalutils.assign_val(df2=rec, df2_x='lon', df2_y='lat',
                         df1=wdt, df1_x='x', df1_y='y', label='width', copy=False)
    gdalutils.assign_val(df2=rec, df2_x='lon', df2_y='lat', df1=drc,
                         df1_x='x', df1_y='y', label='direction', copy=False)

    # Change numbers (1,2,3,4,5,6,7) to letters (N,S,E,W)
    rec['direction_let'] = rec['direction'].apply(getdirletter)

    # Writing .gauge file
    with open(gaugelfp, 'w') as f:
        f.write(str(rec.shape[0])+'\n')
    rec[['lon', 'lat', 'direction_let', 'width']].to_csv(
        gaugelfp, index=False, sep=' ', header=False, float_format='%.7f', mode='a')

    # Writing .stage file
    with open(stagelfp, 'w') as f:
        f.write(str(rec.shape[0])+'\n')
    rec[['lon', 'lat']].to_csv(
        stagelfp, index=False, sep=' ', header=False, float_format='%.7f', mode='a')


def write_evap(evaplfp, t):
    """
    writing Evaporation file
    Using 5mm/day evaporation value
    """

    print("     writing .evap file...")

    with open(evaplfp, "w") as f:
        f.write("# time series"+"\n")
        time = np.arange(t)  # daily values
        f.write(str(t)+"    "+"days"+"\n")
        for i in range(t):
            f.write("%12.3f    %d" % (5, time[i])+"\n")


def write_bdy(bdylfp, runcsv, t):
    """
    Subroutine used to write .BDY file
    Inflows are based on JRC hydrological model output
    """

    print("     writing .bdy file...")

    run = pd.read_csv(runcsv, index_col=0)

    # Select only date columns
    rund = run[[i for i in run.columns if i[0] == '1']].T

    # creating file
    with open(bdylfp, 'w') as f:
        f.write('# euflood bdy file'+'\n')

    # writing inflows
    for i in rund.columns:
        r = rund[i].to_frame()
        r['hours'] = range(0, t*24, 24)
        with open(bdylfp, 'a') as f:
            f.write('in'+str(i)+'\n')
            f.write(str(r['hours'].size)+' '+'hours'+'\n')
        r.to_csv(bdylfp, sep=' ', float_format='%.7f',
                 index=False, header=False, mode='a')


def write_bci(bcilfp, runcsv):
    """
    Writes bcif: XXX.bci file to be used in LISFLOOD-FP
    Uses runfcsv: XXX_run.csv
    """

    print("     writing .bci file...")

    run = pd.read_csv(runcsv, index_col=0)

    runi = run[['x', 'y', 'near_x', 'near_y', 'link']].T

    # creating file
    with open(bcilfp, 'w') as f:
        f.write('# euflood bci file'+'\n')

    # writing inflows
    with open(bcilfp, 'a') as f:
        for i in runi.columns:
            t = 'P'
            x = str(runi[i].loc['x'])
            y = str(runi[i].loc['y'])
            n = 'in' + str(i)
            f.write(t + ' ' + x + ' ' + y + ' ' + 'QVAR' + ' ' + n + '\n')


def write_ascii(dembnktif_1D, wdttif, bedtif, dembnktif):

    print("     writing ASCII files...")

    fmt2 = "AAIGRID"

    name2 = dembnktif_1D
    name3 = os.path.splitext(dembnktif_1D)[0]+'.asc'
    subprocess.call(["gdal_translate", "-of", fmt2, name2, name3])

    name2 = wdttif
    name3 = os.path.splitext(wdttif)[0]+'.asc'
    subprocess.call(["gdal_translate", "-of", fmt2, name2, name3])

    name2 = bedtif
    name3 = os.path.splitext(bedtif)[0]+'.asc'
    subprocess.call(["gdal_translate", "-of", fmt2, name2, name3])

    name2 = dembnktif
    name3 = os.path.splitext(dembnktif)[0]+'.asc'
    subprocess.call(["gdal_translate", "-of", fmt2, name2, name3])


def burn_banks_dem(dembnktif, demtif, fixbnktif):

    print("     burning banks in dem...")

    nodata = -9999
    fout = dembnktif
    base = gdalutils.get_data(demtif)
    basegeo = gdalutils.get_geo(demtif)
    new = gdalutils.get_data(fixbnktif)
    out = np.where(new > 0, new, base)
    gdalutils.write_raster(out, fout, basegeo, "Float32", nodata)


def burn_banks_dem_1D(dembnktif, demtif, fixbnktif):

    print("     burning banks in dem 1D...")

    nodata = -9999
    fout = dembnktif
    base = gdalutils.get_data(demtif)
    basegeo = gdalutils.get_geo(demtif)
    new = (np.ma.masked_values(gdalutils.get_data(
        fixbnktif), nodata)+10000).filled(nodata)
    out = np.where(new > 0, new, base)
    gdalutils.write_raster(out, fout, basegeo, "Float32", nodata)


def getdirletter(dirval):

    if dirval == 1:
        dirlet = "E"
    elif dirval == 3:
        dirlet = "N"
    elif dirval == 5:
        dirlet = "W"
    elif dirval == 7:
        dirlet = "S"
    else:
        sys.exit('ERROR: Wrong direction found')
    return dirlet


def write_par(parlfp, bcilfp, bdylfp, evaplfp, gaugelfp, stagelfp, dembnktif, wdttif, bedtif, t):

    print("     writing .par file...")

    with open(parlfp, "w") as file:

        file.write("latlong" + "\n")
        file.write("dirroot        " +
                   os.path.basename(parlfp).split('.')[0] + "\n")
        file.write("resroot        " +
                   os.path.basename(parlfp).split('.')[0] + "\n")
        file.write("sim_time       " + str((t-1)*86400) +
                   "\n")  # t-1, because first date
        file.write("initial_tstep  " + "10.0" + "\n")
        file.write("massint        " + "86400.0" + "\n")
        file.write("saveint        " + "86400.0" + "\n")
        file.write("fpfric         " + "0.05" + "\n")
        file.write("SGCn           " + "0.05" + "\n")
        if os.path.isfile(bcilfp):
            file.write("bcifile        " + os.path.basename(bcilfp) + "\n")
        if os.path.isfile(bdylfp):
            file.write("bdyfile        " + os.path.basename(bdylfp) + "\n")
        if os.path.isfile(evaplfp):
            file.write("evaporation    " + os.path.basename(evaplfp) + "\n")
        if os.path.isfile(gaugelfp):
            file.write("gaugefile      " + os.path.basename(gaugelfp) + "\n")
        if os.path.isfile(stagelfp):
            file.write("stagefile      " + os.path.basename(stagelfp) + "\n")
        if os.path.isfile(dembnktif):
            file.write("DEMfile        " +
                       os.path.basename(dembnktif).split('.')[0] + '.asc' + "\n")
        if os.path.isfile(dembnktif):
            file.write("SGCbank        " +
                       os.path.basename(dembnktif).split('.')[0] + '.asc' + "\n")
        if os.path.isfile(wdttif):
            file.write("SGCwidth       " +
                       os.path.basename(wdttif).split('.')[0] + '.asc' + "\n")
        if os.path.isfile(bedtif):
            file.write("SGCbed         " +
                       os.path.basename(bedtif).split('.')[0] + '.asc' + "\n")


if __name__ == '__main__':
    buildmodel(sys.argv[1:])