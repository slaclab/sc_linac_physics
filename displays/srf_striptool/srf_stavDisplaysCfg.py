#!/usr/bin/env python

import os
import pathlib
############################################################
# NAME: srf_stavDisplaysCfg.py
# Author: Janice Nelson
# 17 March 2022
#
# From srf_makeAutoPlot.py originally created 6/14/20
#
# Description: Create config files for archiver or striptool
#              Called from edm or bash. Usage:
#              srf_stavDisplaysCfg.py var1 var2 vars
#              var1=av or st
#              var2 = plotname
#              vars = whatever info plotname needs to generate PVs
#
#              from py/edm shell command button
#
#   srf_makeAutoPlot.py var1 var2 vars ; lclsarch "srf_plotname.xml -plot"
# or
#   srf_makeAutoPlot.py var1 var2 vars ; StripTool $STRIP_CONFIGFILE_DIR/srf_plotname.stp
#
# MODS:
#  4 Aug 2022 J Nelson
#    add functionality for striptool to write mins and maxs
# 21 Jul 2022 J Nelson
#    rework so classes that call functions rather than lots of lists...
# 18 Jul 2022 J Nelson
#    add forward powers
# 12 Jul 2022 J Nelson
#    add voltage taps, and misc mag signals per magnet
# 13 Jun 2022 J Nelson
#    add ave of decarads
# 18 Apr 2022 J Nelson
#    add cold compressors
# 1 apr 2022 J Nelson
#    add JT params
# 29 Mar 2022 J Nelson
#    add decarads and dfbest plots
# 17 Mar 2022 J Nelson
#    name change and use utility functions
#    maybe tomorrow add vacuum capability
#  7 Mar 2022 J. Nelson
#    add archive viewer capability and fix act to actmean
############################################################
#
import sys

import srf_srtiptool_utils as util
from displays.srf_striptool.srf_striptool_maker import make_plotz

# sanity checks
# enough variables passed
# cpccmp only needs plotname + av/st so change 3 to 2
narg = len(sys.argv)
if narg < 2:
    print("Too few arguments. Usage: srf_stavDisplays.py av/st plotname vars")
    raise SystemExit

# archiver or striptool
configType = sys.argv[1].lower()
if configType not in ["av", "st"]:
    print("Archiver or striptool config? av or st after script call")
    raise SystemExit

# get lists from Utility file

plot_z = make_plotz()
plots = list(plot_z.keys())
CM_IDs = util.CM_IDs()

# this had a .lower() at the end
plotName = sys.argv[2]

if plotName not in plots:
    print("\n2nd arg needs to be a valid plot name\n")
    print(plotName)
    print(plots)
    raise SystemExit
else:
    fileNamePrefix = "srf_" + plotName

# put rest of passed variables into arglist for plotName function
arglist = []
if narg > 3:
    arglist = sys.argv[3 : narg + 1]
#  print('arglist {}'.format(arglist))
# print(f"sys.argv {sys.argv}")

# This calls the function whose name is stored in plotName
# globals()[plotName]()

# print(f"plotz[plotname].rangeDelta {Plotz[plotName].rangeDelta}")

if plot_z[plotName].rangeDelta is not None:
    arglist.append(plot_z[plotName].rangeDelta)
    pvList = plot_z[plotName].pvFun(arglist)
    rangeList = plot_z[plotName].rangeFun(arglist)
else:
    #  print(f"Plotz[{plotName}].pvFun(arglist) {Plotz[plotName].pvFun} {arglist}")
    pvList = plot_z[plotName].pvFun(arglist)
    rangeList = None


# print(pvList)

if configType == "st":
    # Create config file
    config_dir = os.getenv(
        "STRIP_CONFIGFILE_DIR", f"{pathlib.Path(__file__).parent.resolve()}/config"
    )
    filename = f"{fileNamePrefix}.stp"
    filedir = f"{config_dir}/SRF"

    os.makedirs(filedir, exist_ok=True)
    f = open(f"{filedir}/{filename}", "w")

    #  f=open(fileNamePrefix+'.stp', 'w')

    # Write header
    f.write("StripConfig                     1.2\n")
    f.write("Strip.Time.Timespan             600\n")
    f.write("Strip.Time.NumSamples           65536\n")
    f.write("Strip.Time.SampleInterval       0.500000\n")
    f.write("Strip.Time.RefreshInterval      0.500000\n")
    f.write("Strip.Color.Grid                49071     49071     49071\n")
    f.write("Strip.Color.Background          65535     65535     65535\n")
    f.write("Strip.Color.Foreground          0     0     0\n")
    f.write("Strip.Option.GridXon            1\n")
    f.write("Strip.Option.GridYon            1\n")
    f.write("Strip.Option.AxisYcolorStat     1\n")
    f.write("Strip.Option.GraphLineWidth     2\n")
    f.write("Strip.Color.Color1            42919     8224      7967\n")
    f.write("Strip.Color.Color2            63222     40863     12336\n")
    f.write("Strip.Color.Color3            59881     55769     514\n")
    f.write("Strip.Color.Color4            31868     64764     6168\n")
    f.write("Strip.Color.Color5            16705     35466     11565\n")
    f.write("Strip.Color.Color6            15934     59110     63479\n")
    f.write("Strip.Color.Color7            7453      14135     57311\n")
    f.write("Strip.Color.Color8            46260     23387     61166\n")
    f.write("Strip.Color.Color9            26728     9509      52685\n")
    f.write("Strip.Color.Color10           61680     44204     60652\n")
    print("Strip Tools In Living Color")
    # Write PV names, 10 max
    for nn in range(len(pvList[0:10])):
        str = "Strip.Curve.{}.Name              " + pvList[nn] + "\n"
        f.write(str.format(nn))
        if plotName == "cmvac":
            str = "Strip.Curve.{}.Scale              1\n"
            f.write(str.format(nn))
        else:
            str = "Strip.Curve.{}.Scale              0\n"
            f.write(str.format(nn))
    if plotName == "cmvac":
        f.write("Strip.Curve.0.Min          0.00000000001\n")
        f.write("Strip.Curve.1.Min          0.00000000010\n")
        f.write("Strip.Curve.2.Min          0.00000001000\n")
        f.write("Strip.Curve.0.Max          0.00000010000\n")
        f.write("Strip.Curve.1.Max          0.00000010000\n")
        f.write("Strip.Curve.2.Max          0.00010000000\n")
    elif rangeList is not None:
        (minList, maxList) = rangeList
        for ii, minVal in enumerate(minList):
            str = "Strip.Curve.{}.Min              {}\n"
            f.write(str.format(ii, minVal))
        for ii, maxVal in enumerate(maxList):
            str = "Strip.Curve.{}.Max              {}\n"
            f.write(str.format(ii, maxVal))

    # Close file

    f.close()
elif configType == "av":
    # Create archive viewer config file
    #
    # -205 yellow
    # -26215 peachy pink
    # -26317 orange
    # -39169 light magenta
    # -39424 orange
    # -52225 magenta
    # -65281 magenta
    # -65536 dk red
    # -70000 yellow
    # -110000 salmon
    # -614608 orange
    # -1004308 pink
    # -1006630 pink
    # -1451774 yellow
    # -3355648 shit yellow
    # -4957202 reddish purple
    # -5824481 dk red
    # -6710785 lavender
    # -6710887 light grey
    # -6750055 purplish brick
    # -8586216 lt green
    # -9951795 med purple
    # -10027009 turquoise
    # -10027162 bright/lt green
    # -10092391 purple/red
    # -10092289 purple
    # -12482003 dk green
    # -12654857 turquoise
    # -13395559 turquoise
    # -14862369 dk purple
    # -16711936 med green
    # -16738048 dk green
    # -16776961 royal
    # -16777216 brown
    #
    #  colors = [ -13395559, -6710887,-65536, -16776961, -16711936, -65281, -16777216, -10092391, -39424 ]
    #  colors = [-65281, -1006630, -6710785, -9951795, -4957202, -14862369,
    #            -12654857, -12482003, -8586216, -1451774, -614608, -5824481, -1004308,]
    colors = [
        -65536,
        -26317,
        -3355648,
        -16738048,
        -16776961,
        -10092289,
        -52225,
        -26215,
        -10027009,
        -10027162,
    ]
    #  print(len(colors))
    #
    #  print(os.getenv('ARCHCONFIGFILES'))
    #  print(fileNamePrefix)

    f = open(os.getenv("ARCHCONFIGFILES") + "/SRF/" + fileNamePrefix + ".xml", "w")
    f.write('<?xml version="1.0" encoding="UTF-16"?>\n')
    f.write("<AVConfiguration>\n")
    f.write(
        "    <connection_parameter>pbraw://lcls-archapp.slac.stanford.edu/retrieval</connection_parameter>\n"
    )
    f.write('    <time_axis name="Main Time Axis">\n')
    f.write("        <start>-1d</start>\n")
    f.write("        <end>now</end>\n")
    f.write("        <location>bottom</location>\n")
    f.write("    </time_axis>\n")
    f.write('    <range_axis name="Main Range Axis">\n')
    f.write("        <min/>\n")
    f.write("        <max/>\n")
    if plotName == "cmvac":
        f.write("        <type>log</type>\n")
    else:
        f.write("        <type>normal</type>\n")
    f.write("        <location>left</location>\n")
    f.write("    </range_axis>\n")
    f.write(
        '    <legend_configuration show_ave_name="true" show_directory_name="false" show_range="true" show_units="true"/>\n'
    )
    f.write("    <plot_title/>\n")
    #
    if len(colors) > len(pvList):
        npvs = len(colors)
    else:
        npvs = len(pvList)
    #  print(npvs)

    for nn in range(len(pvList[0:npvs])):
        f.write('    <pv directory_name="Default" name="' + pvList[nn] + '">\n')
        f.write("        <time_axis_name>Main Time Axis</time_axis_name>\n")
        f.write("        <range_axis_name>Main Range Axis</range_axis_name>\n")
        f.write("        <color>" + str(colors[nn]) + "</color>\n")
        f.write("        <draw_type>steps</draw_type>\n")
        f.write("        <draw_width>1.0</draw_width>\n")
        f.write("        <visibility>true</visibility>\n")
        f.write("    </pv>\n")
    f.write("</AVConfiguration>\n")
    f.close()
