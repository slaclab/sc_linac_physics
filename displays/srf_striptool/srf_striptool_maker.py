import math

from epics import caget

import srf_srtiptool_utils as util

CM_IDs = util.CM_IDs()
blvacPVs = util.blvacPVs()  # beamline vac
cplrvacPVs = util.cplrvacPVs()  # coupler vacuum
insvacPVs = util.insvacPVs()  # insulating vacuum
galTempPVs = util.galTempPVs()  # gallery temps


# Define functions to create pvLists
#
# USLL 10 CM
#
def tenUSLL_pvs(arglist):
    if len(arglist) < 1:
        print(
            "\ntenDSLL needs one argument(starting CM): CM ACCL:LxB:yy, yy=01-35, H1, H2\n"
        )
        raise SystemExit
    pvList = []

    idx = CM_IDs.index(arglist[0].upper())
    if idx + 10 > len(CM_IDs):
        idx = len(CM_IDs) - 10
    for nn in range(idx, idx + 10):
        pvList.append("CLL:CM" + CM_IDs[nn][-2:] + ":2601:US:LVL")

    return pvList


#
# DSLL 10 CM
#
def tenDSLL_pvs(arglist):
    if len(arglist) < 1:
        print(
            "\ntenDSLL needs one argument(starting CM): CM ACCL:LxB:yy, yy=01-35, H1, H2\n"
        )
        raise SystemExit
    pvList = []

    idx = CM_IDs.index(arglist[0].upper())
    if idx + 10 > len(CM_IDs):
        idx = len(CM_IDs) - 10
    for nn in range(idx, idx + 10):
        pvList.append("CLL:CM" + CM_IDs[nn][-2:] + ":2301:DS:LVL")

    return pvList


#
# JT 10 CM
#
def tenJT_pvs(arglist):
    if len(arglist) < 1:
        print(
            "\ntenDSLL needs one argument(starting CM): CM ACCL:LxB:yy, yy=01-35, H1, H2\n"
        )
        raise SystemExit
    pvList = []

    idx = CM_IDs.index(arglist[0].upper())
    if idx + 10 > len(CM_IDs):
        idx = len(CM_IDs) - 10
    for nn in range(idx, idx + 10):
        pvList.append("CPV:CM" + CM_IDs[nn][-2:] + ":3001:JT:POS_RBV")

    return pvList


#
# AACTMEANSUM 10 CM
#
def tenAACTSUM_pvs(arglist):
    if len(arglist) < 1:
        print(
            "\ntenDSLL needs one argument(starting CM): CM ACCL:LxB:yy, yy=01-35, H1, H2\n"
        )
        raise SystemExit
    pvList = []

    idx = CM_IDs.index(arglist[0].upper())
    if idx + 10 > len(CM_IDs):
        idx = len(CM_IDs) - 10
    for nn in range(idx, idx + 10):
        pvList.append(CM_IDs[nn] + "00:AACTMEANSUM")

    return pvList


#
# cavity pulsed sel phase offsets
#
def cmSelPoffs_pvs(arglist):
    if len(arglist) < 2:
        print(
            "\ncmSelPoffs needs two arguments: CM ACCL:LxB:yy, yy=01-35, H1, H2 and a delta\n"
        )
        print(arglist)
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:SEL_POFF".format(arglist[0], nn + 1))
    idx = CM_IDs.index(arglist[0])
    pvList.append(galTempPVs[idx])

    return pvList


def cmSelPoffs_ranges(arglist):
    # returns ranges as a tuple of lists ([lows],[highs])
    if len(arglist) < 2:
        print(
            "\ncmSelPoffs needs two arguments: CM ACCL:LxB:yy, yy=01-35, H1, H2 and delta around current value\n"
        )
        print(arglist)
        raise SystemExit
    lowList = []
    highList = []
    rangList = []

    for nn in range(8):
        #    print(f"arglist {arglist}")
        PV = "{}{}0:SEL_POFF".format(arglist[0], nn + 1)
        #    print(f"PV {PV}")
        try:
            currVal = caget(PV)
            lowList.append(currVal - arglist[1])
            highList.append(currVal + arglist[1])
        except:
            print(f"caget({PV}) failed")
            currVal = 0
            lowList.append(-180)
            highList.append(180)
    idx = CM_IDs.index(arglist[0])
    currVal = caget(galTempPVs[idx])
    lowList.append(currVal - arglist[1])
    highList.append(currVal + arglist[1])
    rangList = (lowList, highList)
    #  print(f"RangList {rangList}")
    return rangList


#
# forward powers for 8 cavities
#
def cmFwdP_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmFwdP needs one argument: CM ACCL:LxB:yy, yy=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:FWD:PWRMEAN".format(arglist[0], nn + 1))
    return pvList


#
# cavtemps for one cavity
#
def cavtemps_pvs(arglist):
    if len(arglist) < 2:
        print("\ncavtemps needs two arguments: ACCL:LxB:nn (nn=1-35) and c (1-8)\n")
        raise SystemExit
    pvList = []

    cm = arglist[0]
    cav = arglist[1]
    pvList.append(cm.upper() + cav + "0:STEPTEMP")
    pvList.append(cm.upper() + cav + "0:CPLRTEMP1")
    pvList.append(cm.upper() + cav + "0:CPLRTEMP2")
    pvList.append("CTE:CM" + cm[-2:] + ":1" + cav + "20:DH:TEMP")
    pvList.append("CTE:CM" + cm[-2:] + ":1" + cav + "18:UH:TEMP")

    if cav in ["1", "5"]:
        pvList.append("CTE:CM" + cm[-2:] + ":1" + cav + "14:VT:TEMP")
        pvList.append("CTE:CM" + cm[-2:] + ":1" + cav + "15:VB:TEMP")

    return pvList


#
# cpccmp cryoplant cold compressors
#
def cpccmp_pvs(arglist):
    pvList = []

    pvList.append("CPT:CP14:1100:PRESS")
    for nn in range(5):
        pvList.append("CCMP:CP14:11{}0:ST".format(nn))

    return pvList


#
# dfbest
#
def cmDFbest_pvs(arglist):
    if len(arglist) < 1:
        print("\nDFbest needs one argument: CM ACCL:LxB:yy, yy=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:DFBEST".format(arglist[0], nn + 1))
    return pvList


#
# ranges for DFBest
#
def cmDFtune_ranges(arglist):
    # returns ranges as a tuple of lists ([lows],[highs])
    if len(arglist) < 1:
        print(
            "\ncmDFbest needs one argument: CM ACCL:LxB:yy, yy=01-35, H1, H2 and delta around current value\n"
        )
        print(arglist)
        raise SystemExit

    currValList = []

    for nn in range(8):
        #    print(f"arglist {arglist}")
        PV = "{}{}0:DF_COLD".format(arglist[0], nn + 1)
        #    print(f"PV {PV}")
        try:
            currValList.append(caget(PV))
        except:
            print(f"caget({PV}) failed")
            currValList.append(0)
    if max(currValList) < 0:
        lowVal = min(currValList)
        lowVal = 10000 * math.floor(lowVal / 10000)
        highVal = 0
    elif min(currValList) > 0:
        lowVal = 0
        highVal = max(currValList)
        highVal = 10000 * math.ceil(highVal / 10000)
    else:
        lowVal = min(currValList)
        lowVal = 10000 * math.floor(lowVal / 10000)
        highVal = max(currValList)
        highVal = 10000 * math.ceil(highVal / 10000)
    if lowVal == 0 and highVal == 0:
        lowVal = -100000
        highVal = 100000
    lowList = [lowVal] * 8
    highList = [highVal] * 8
    rangList = (lowList, highList)
    print(f"RangList {rangList}")
    return rangList


#
# decarads
#
def decarad1raw_pvs():
    pvList = []

    for ii in range(10):
        pvList.append("RADM:SYS0:100:%02d:GAMMA_DOSE_RATE" % (ii + 1))
    return pvList


def decarad2raw_pvs():
    pvList = []

    for ii in range(10):
        pvList.append("RADM:SYS0:200:%02d:GAMMA_DOSE_RATE" % (ii + 1))
    return pvList


def decarad1ave_pvs():
    pvList = []

    for ii in range(10):
        pvList.append("RADM:SYS0:100:%02d:GAMMAAVE" % (ii + 1))

    return pvList


def decarad2ave_pvs():
    pvList = []
    for ii in range(10):
        pvList.append("RADM:SYS0:200:%02d:GAMMAAVE" % (ii + 1))
    return pvList


#
# cryopipe temps in one CM
#
def cryopipe_pvs(arglist):
    if len(arglist) < 1:
        print("\ncryopipe needs one argument: ACCL:LxB:cm or cm (01-35,H1,H2)\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]

    pvPre = "CTE:CM" + cm
    pvList.append(pvPre + ":2501:A1:TEMP")
    pvList.append(pvPre + ":2502:B1:TEMP")
    pvList.append(pvPre + ":2503:B2:TEMP")
    pvList.append(pvPre + ":2508:C1:TEMP")
    pvList.append(pvPre + ":2509:D1:TEMP")
    pvList.append(pvPre + ":2510:E1:TEMP")
    pvList.append(pvPre + ":2511:F1:TEMP")
    pvList.append(pvPre + ":2512:S1:TEMP")
    pvList.append(pvPre + ":2514:CD:TEMP")
    pvList.append(pvPre + ":2515:CD:TEMP")

    return pvList


#
# cplrtop all coupler top temps in one CM
#
def cplrtop_pvs(arglist):
    if len(arglist) < 1:
        print("\ncplrtop needs one argument: CM ACCL:LxB:yy, yy=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:CPLRTEMP1".format(arglist[0], nn + 1))
    return pvList


#
# cplrbot all coupler bottom temps in one CM
#
def cplrbot_pvs(arglist):
    if len(arglist) < 1:
        print("\ncplrbot needs one argument: CM ACCL:LxB:yy, yy=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:CPLRTEMP2".format(arglist[0], nn + 1))

    return pvList


#
# homus all HOM upstream temps in one CM
#
def homus_pvs(arglist):
    if len(arglist) < 1:
        print("\nhomus needs one argument: ACCL:LxB:cm or cm 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    for nn in range(8):
        pvList.append("CTE:CM{}:1{}18:UH:TEMP".format(cm, nn + 1))
    return pvList


#
# homds all HOM upstream temps in one CM
#
def homds_pvs(arglist):
    if len(arglist) < 1:
        print("\nhomds needs one argument: ACCL:LxB:cm or cm 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    for nn in range(8):
        pvList.append("CTE:CM{}:1{}20:DH:TEMP".format(cm, nn + 1))
    return pvList


#
# steptmps all stepper motor temps in one CM
#
def steptmps_pvs(arglist):
    if len(arglist) < 1:
        print("\nsteptmps needs one argument: CM ACCL:LxB:yy, yy=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:STEPTEMP".format(arglist[0], nn + 1))

    return pvList


#
# cmcryos various cryo things in one cm: LL, pres, valvs, cd htr
#
def cmcryos_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmcryos needs one argument: ACCL:LxB:CM or CM = 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    pvList.append("CLL:CM" + cm + ":2601:US:LVL")
    pvList.append("CLL:CM" + cm + ":2301:DS:LVL")
    #  pvList.append('CPT:CM'+cm+':2602:US:PRESS')
    pvList.append("CPT:CM" + cm + ":2302:DS:PRESS")
    pvList.append("CPV:CM" + cm + ":3001:JT:POS_RBV")
    #  pvList.append('CPV:CM'+cm+':3002:CD:POS_RBV')
    #  pvList.append('CHTR:CM'+cm+':2261:CD:POWER_RBV')
    if cm[0] == "H":
        pvList.append("CPIC:HL0" + cm[1] + ":0000:EHCV:ORBV")
    else:
        pvList.append("CPIC:CM" + cm + ":0000:EHCV:ORBV")

    return pvList


#
# All JT PID params one CM
#
def cmJTparams_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmcryos needs one argument: ACCL:LxB:CM or CM = 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:DMAX")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:DMIN")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:MDT")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:KP")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:KI")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:KD")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:MAX")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:MIN")
    pvList.append("CLIC:CM" + cm + ":3001:PVJT:SP_RQST")
    pvList.append("CPV:CM" + cm + ":3001:JT:POS_RBV")

    return pvList


#
# cmheves helium vessel temps from one cm
#
def cmheves_pvs(arglist):
    if len(arglist) < 1:
        print(
            "\ncmheves needs one argument: ACCL:LxB:nn (nn=1-35) or cm (01-35,h1,h2)\n"
        )
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    for cav in ["1", "5"]:
        pvList.append("CTE:CM" + cm + ":1" + cav + "14:VT:TEMP")
        pvList.append("CTE:CM" + cm + ":1" + cav + "15:VB:TEMP")
    return pvList


#
# cavhtrs all cavity heaters in one CM
#
def cavhtrs_pvs(arglist):
    if len(arglist) < 1:
        print("\ncavhtrs needs one argument: CM ACCL:LxB:cm or cm 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    for nn in range(8):
        pvList.append("CHTR:CM{}:1{}55:HV:POWER_RBV".format(cm, nn + 1))
    return pvList


#
# cmpiezov all piezo volts in one CM
#
def cmpiezov_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmpiezov needs one argument: ACCL:LxB:cm cm=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:PZT:V".format(arglist[0], nn + 1))
    return pvList


#
# cmvac all vac in one CM
#
def cmvac_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmvac needs one arguments: ACCL:LxB:cm cm=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    idx = CM_IDs.index(arglist[0])
    pvList.append(blvacPVs[idx])
    pvList.append(cplrvacPVs[idx])
    pvList.append(insvacPVs[idx])

    return pvList


#
# cmaact all AACTs in one CM
#
def cmaact_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmaact needs one argument: ACCL:LxB:cm cm=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:AACTMEAN".format(arglist[0], nn + 1))
    pvList.append("{}00:AACTMEANSUM".format(arglist[0]))

    return pvList


#
# allAACTMEANSUMs for 4 linac sections, plus 0+1+2 and 0+1+2+3
#
def allAACTMEANSUMs_pvs():
    pvList = []

    for nn in range(4):
        pvList.append("ACCL:L{}B:1:AACTMEANSUM".format(nn))
    pvList.append("ACCL:L1B:1:HL_AACTMEANSUM")
    pvList.append("ACCL:L1B:1:EXCLHL_AACTMEANSUM")
    pvList.append("ACCL:SYS0:SC:L0B_L1B_AACTMEANSUM")
    pvList.append("ACCL:SYS0:SC:L0B_L2B_AACTMEANSUM")
    pvList.append("ACCL:SYS0:SC:AACTMEANSUM")

    return pvList


#
# cmpdes all PDESs in one CM
#
def cmpdes_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmpdes needs one argument: ACCL:LxB:cm cm=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:PDES".format(arglist[0], nn + 1))

    return pvList


#
# cmpact all PACTs in one CM
#
def cmpact_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmpact needs one argument: ACCL:LxB:cm cm=01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    for nn in range(8):
        pvList.append("{}{}0:PACTMEAN".format(arglist[0], nn + 1))
    return pvList


#
# cmmag all magnet temps in one CM
#
def cmmag_pvs(arglist):
    if len(arglist) < 1:
        print("\ncmmag needs one or two arguments: ACCL:LxB:cm OR")
        print("area (LxB) and CM 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    area = arglist[0].upper()
    if area[0] == "A":
        cm = area[-2:]
        area = area[5:8]
    else:
        try:
            cm = arglist[1]
        except:
            print("\ncmmag needs one or two arguments: ACCL:LxB:cm OR")
            print("area (LxB) and CM 01-35, H1, H2\n")
            raise SystemExit

    for mType in ["QUAD", "XCOR", "YCOR"]:
        pvList.append(mType + ":" + area + ":" + cm + "85:BACT")
    #
    # decode MG ioc number.
    # L0B CM01 MG01-03
    # L1B CM02 MG01-03
    # L1B CM03 MG04-06 (cm-1)*3
    # L2B CM04 MG01-03
    # L2B CM15 MG34-36 (cm-3)*3
    # L3B CM16 MG01-03 (cm-15)*3
    # L3B CM35 MG58-60
    cmNum = int(cm)
    areaNum = int(area[1])
    if areaNum == 0:
        mgmax = 3
    elif areaNum == 1:
        mgmax = (cmNum - 1) * 3
    elif areaNum == 2:
        mgmax = (cmNum - 3) * 3
    else:  # boy I hope areaNum==3
        mgmax = (cmNum - 15) * 3

    mgNums = []
    for nn in range(mgmax - 2, mgmax + 1):
        numstr = str(nn)
        mgNums.append(numstr.zfill(2))

    for mgNum in mgNums:
        pvList.append("PSC:" + area + ":MG" + mgNum + ":PSVOUT")

    pvList.append("CHTR:CM" + cm + ":2140:MP:POWER")

    return pvList


#
# magtemps all magnet temps in one CM
#
def magtemps_pvs(arglist):
    if len(arglist) < 1:
        print("\nmagtemps needs one argument: CM ACCL:LxB:cm or cm 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    for nn in range(4):
        pvList.append("CTE:CM{}:240{}:MP:TEMP".format(cm, nn + 1))
    for nn in range(4):
        pvList.append("CTE:CM{}:240{}:CL:TEMP".format(cm, nn + 5))

    return pvList


#
# magVtaps all magnet voltage taps in one CM
#
def magVtaps_pvs(arglist):
    if len(arglist) < 1:
        print("\nmagtemps needs one argument: CM ACCL:LxB:cm or cm 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    unitNums = ["12", "34"]
    secns = ["VD", "HD", "SQ"]
    for nn in range(3):
        for mm in range(2):
            pvList.append("CVT:CM{}:{}:{}:VOLTAGE".format(cm, unitNums[mm], secns[nn]))
    return pvList


#
# magCLtaps all magnet power lead taps in one CM
#
def magCLtaps_pvs(arglist):
    if len(arglist) < 1:
        print("\nmagtemps needs one argument: CM ACCL:LxB:cm or cm 01-35, H1, H2\n")
        raise SystemExit
    pvList = []

    # arglist[0] should be 2 characters for the CM id (01, 35, H1) or
    #    ACCL:LxB:CM
    # If it starts with an A, then the CM id is the last two digits, if
    #   not arglist[0].upper() is the CM id (in case someone passes h1)

    cm = arglist[0].upper()
    if cm[0] == "A":
        cm = cm[-2:]
    unitNums = ["12", "34"]
    secns = ["VD", "HD", "SQ"]
    for nn in range(3):
        for mm in range(2):
            pvList.append("CVT:CM{}:{}:P{}:VOLTAGE".format(cm, unitNums[mm], secns[nn]))

    return pvList


#
# QmagSigs signals for the quad
#
def QmagSigs_pvs(arglist):
    if len(arglist) < 1:
        print("\nQmagSigs needs one argument: CM ACCL:LxB:cm\n")
        raise SystemExit
    pvList = []

    # If arglist[0] starts with an A, then the CM id is the last two digits

    area = arglist[0].upper()
    if area[0] == "A":
        cm = area[-2:]
        area = area[5:8]
    else:
        print("\ncmmag needs one argument: ACCL:LxB:cm\n")
        raise SystemExit

    #  for mType in ['QUAD', 'XCOR', 'YCOR'] :
    pvList.append("QUAD:" + area + ":" + cm + "85:BACT")
    #
    # decode MG ioc number.
    # L0B CM01 MG01-03 (Q,X,Y)
    # L1B CM02 MG01-03
    # L1B CM03 MG04-06 (cm-1)*3
    # L2B CM04 MG01-03
    # L2B CM15 MG34-36 (cm-3)*3
    # L3B CM16 MG01-03 (cm-15)*3
    # L3B CM35 MG58-60
    cmNum = int(cm)
    areaNum = int(area[1])
    if areaNum == 0:
        mgmax = 3
    elif areaNum == 1:
        mgmax = (cmNum - 1) * 3
    elif areaNum == 2:
        mgmax = (cmNum - 3) * 3
    else:  # boy I hope areaNum==3
        mgmax = (cmNum - 15) * 3

    # quad so mgNum=mgmax-2
    mgNum = str(mgmax - 2).zfill(2)
    pvList.append("PSC:" + area + ":MG" + mgNum + ":PSVOUT")

    unitNums = ["12", "34"]
    #  secns=['VD','HD','SQ']
    secns = ["SQ"]
    prefixes = ["", "P"]
    for prefix in prefixes:
        for unitNum in unitNums:
            for secn in secns:
                pvList.append(
                    "CVT:CM{}:{}:{}{}:VOLTAGE".format(cm, unitNum, prefix, secn)
                )
    return pvList


#
# XmagSigs signals for the xcor
#
def XmagSigs_pvs(arglist):
    if len(arglist) < 1:
        print("\nQmagSigs needs one argument: CM ACCL:LxB:cm\n")
        raise SystemExit
    pvList = []

    # If arglist[0] starts with an A, then the CM id is the last two digits

    area = arglist[0].upper()
    if area[0] == "A":
        cm = area[-2:]
        area = area[5:8]
    else:
        print("\ncmmag needs one argument: ACCL:LxB:cm\n")
        raise SystemExit

    #  for mType in ['QUAD', 'XCOR', 'YCOR'] :
    pvList.append("XCOR:" + area + ":" + cm + "85:BACT")
    #
    # decode MG ioc number.
    # L0B CM01 MG01-03 (Q,X,Y)
    # L1B CM02 MG01-03
    # L1B CM03 MG04-06 (cm-1)*3
    # L2B CM04 MG01-03
    # L2B CM15 MG34-36 (cm-3)*3
    # L3B CM16 MG01-03 (cm-15)*3
    # L3B CM35 MG58-60
    cmNum = int(cm)
    areaNum = int(area[1])
    if areaNum == 0:
        mgmax = 3
    elif areaNum == 1:
        mgmax = (cmNum - 1) * 3
    elif areaNum == 2:
        mgmax = (cmNum - 3) * 3
    else:  # boy I hope areaNum==3
        mgmax = (cmNum - 15) * 3

    # xcor so mgNum=mgmax-1
    mgNum = str(mgmax - 1).zfill(2)
    pvList.append("PSC:" + area + ":MG" + mgNum + ":PSVOUT")

    unitNums = ["12", "34"]
    #  secns=['VD','HD','SQ']
    secns = ["HD"]
    prefixes = ["", "P"]
    for prefix in prefixes:
        for unitNum in unitNums:
            for secn in secns:
                pvList.append(
                    "CVT:CM{}:{}:{}{}:VOLTAGE".format(cm, unitNum, prefix, secn)
                )
    return pvList


#
# YmagSigs signals for the ycor
#
def YmagSigs_pvs(arglist):
    if len(arglist) < 1:
        print("\nQmagSigs needs one argument: CM ACCL:LxB:cm\n")
        raise SystemExit
    pvList = []

    # If arglist[0] starts with an A, then the CM id is the last two digits

    area = arglist[0].upper()
    if area[0] == "A":
        cm = area[-2:]
        area = area[5:8]
    else:
        print("\ncmmag needs one argument: ACCL:LxB:cm\n")
        raise SystemExit

    #  for mType in ['QUAD', 'XCOR', 'YCOR'] :
    pvList.append("YCOR:" + area + ":" + cm + "85:BACT")
    #
    # decode MG ioc number.
    # L0B CM01 MG01-03 (Q,X,Y)
    # L1B CM02 MG01-03
    # L1B CM03 MG04-06 (cm-1)*3
    # L2B CM04 MG01-03
    # L2B CM15 MG34-36 (cm-3)*3
    # L3B CM16 MG01-03 (cm-15)*3
    # L3B CM35 MG58-60
    cmNum = int(cm)
    areaNum = int(area[1])
    if areaNum == 0:
        mgmax = 3
    elif areaNum == 1:
        mgmax = (cmNum - 1) * 3
    elif areaNum == 2:
        mgmax = (cmNum - 3) * 3
    else:  # boy I hope areaNum==3
        mgmax = (cmNum - 15) * 3

    # ycor so mgNum=mgmax-1
    mgNum = str(mgmax).zfill(2)
    pvList.append("PSC:" + area + ":MG" + mgNum + ":PSVOUT")

    unitNums = ["12", "34"]
    #  secns=['VD','HD','SQ']
    secns = ["VD"]
    prefixes = ["", "P"]
    for prefix in prefixes:
        for unitNum in unitNums:
            for secn in secns:
                pvList.append(
                    "CVT:CM{}:{}:{}{}:VOLTAGE".format(cm, unitNum, prefix, secn)
                )
    return pvList


def COL0_BLMs_pvs(arglist):
    pvList = []
    pblmnums = ["390", "450", "710", "790"]
    lblmnums = ["HTR:167:A", "HTR:167:B", "COL0:862:A", "COL0:862:B"]

    for unitNum in pblmnums:
        pvList.append("PBLM:COL0:{}:I0_LOSS".format(unitNum))

    for unitNum in lblmnums:
        pvList.append("LBLM:{}:I0_LOSS".format(unitNum))
    return pvList


def passme():
    pass


#
# End function definitions
#


class PlotType:
    def __init__(
        self,
        name,
        pvFun=None,
        desc=None,
        needCav=False,
        needCM=False,
        rangeDelta=None,
        rangeFun=None,
    ):
        # name is the name of the group of PVs
        # pvFun is the function to make a list of PVs
        # desc is a description of the group
        # needCav is a boolean to indicate if a cavity specification is required
        # needCM is a boolean to indicate if a cryomod spec is required
        # rangeDelta is a float value used to determine the min/mix
        #   written to the strip tool config file
        # rangeFun is the function to make the list of mins and maxs for striptool

        self.name = name
        if pvFun is None:
            pvFun = passme
        self.pvFun = pvFun
        self.desc = desc
        self.needCav = needCav
        self.needCM = needCM
        self.rangeDelta = rangeDelta
        if rangeDelta is None:
            self.rangeFun = passme
        else:
            self.rangeFun = rangeFun


def make_plotz():
    plotz = {
        "cavtemps": PlotType(
            name="cavtemps",
            pvFun=cavtemps_pvs,
            needCav=True,
            needCM=True,
            desc="One cavity's temps: stepper, two couplers, US & DS HOM, and HeVes if cav=1 or 5",
        ),
        "cryopipe": PlotType(
            name="cryopipe",
            pvFun=cryopipe_pvs,
            needCav=False,
            needCM=True,
            desc="Cryopipe temps for one CM: A B1 B2 C D E F shield and two cooldown",
        ),
        "cplrtop": PlotType(
            name="cplrtop",
            pvFun=cplrtop_pvs,
            needCav=False,
            needCM=True,
            desc="All coupler top (CPLRTEMP1) temps in one CM",
        ),
        "cplrbot": PlotType(
            name="cplrbot",
            pvFun=cplrbot_pvs,
            needCav=False,
            needCM=True,
            desc="All coupler bot (CPLRTEMP2) temps in one CM",
        ),
        "homus": PlotType(
            name="homus",
            pvFun=homus_pvs,
            needCav=False,
            needCM=True,
            desc="All upstream HOM temps (1x18:UH:TEMP) in one CM",
        ),
        "homds": PlotType(
            name="homds",
            pvFun=homds_pvs,
            needCav=False,
            needCM=True,
            desc="All downstream HOM temps (1x18:UH:TEMP) in one CM",
        ),
        "steptmps": PlotType(
            name="steptmps",
            pvFun=steptmps_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' stepper motor temps (STEPTEMP) in one CM",
        ),
        "cmcryos": PlotType(
            name="cmcryos",
            pvFun=cmcryos_pvs,
            needCav=False,
            needCM=True,
            desc="Misc cryo signals for one CM: US/DS LL, US/DS pressure, JT/CD posn, CD:POWER",
        ),
        "cmheves": PlotType(
            name="cmheves",
            pvFun=cmheves_pvs,
            needCav=False,
            needCM=True,
            desc="All helium vessel temps in noe CM, cavs 1 & 5, top & bottom",
        ),
        "cavhtrs": PlotType(
            name="cavhtrs",
            pvFun=cavhtrs_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' heaters (HV:POWER_RBV)",
        ),
        "cmpiezov": PlotType(
            name="cmpiezov",
            pvFun=cmpiezov_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' piezo volts",
        ),
        "cmvac": PlotType(
            name="cmvac",
            pvFun=cmvac_pvs,
            needCav=False,
            needCM=True,
            desc="Three vacuum signals for each CM: beamline, coupler, insulating",
        ),
        "cmaact": PlotType(
            name="cmaact",
            pvFun=cmaact_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' AACTMEANs",
        ),
        "cmpdes": PlotType(
            name="cmpdes",
            pvFun=cmpdes_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' PDESs",
        ),
        "cmpact": PlotType(
            name="cmpact",
            pvFun=cmpact_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' PACTMEANs",
        ),
        "cmFwdP": PlotType(
            name="cmFwdP",
            pvFun=cmFwdP_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' forward powers",
        ),
        "cmDFbest": PlotType(
            name="cmDFbest",
            pvFun=cmDFbest_pvs,
            needCav=False,
            needCM=True,
            desc="All 8 cavities' DF:BESTs",
        ),
        "cmDFtune": PlotType(
            name="cmDFtune",
            pvFun=cmDFbest_pvs,
            needCav=False,
            needCM=True,
            rangeDelta=0,
            rangeFun=cmDFtune_ranges,
            desc="All 8 cavities' DF:BESTs for tuning",
        ),
        "cmmag": PlotType(
            name="cmmag",
            pvFun=cmmag_pvs,
            needCav=False,
            needCM=True,
            desc="QUAD/XCOR/YCOR magnet settings (BACT), PS output volts, and magnet heater in one CM",
        ),
        "magtemps": PlotType(
            name="magtemps",
            pvFun=magtemps_pvs,
            needCav=False,
            needCM=True,
            desc="All magnet temps (magnet body and clamp) in one CM",
        ),
        "magVtaps": PlotType(
            name="magVtaps",
            pvFun=magVtaps_pvs,
            needCav=False,
            needCM=True,
            desc="All magnet voltage taps",
        ),
        "magCLtaps": PlotType(
            name="magCLtaps",
            pvFun=magCLtaps_pvs,
            needCav=False,
            needCM=True,
            desc="All magnet power lead taps",
        ),
        "QmagSigs": PlotType(
            name="QmagSigs",
            pvFun=QmagSigs_pvs,
            needCav=False,
            needCM=True,
            desc="Quad: bact, ps volts, and voltage taps",
        ),
        "XmagSigs": PlotType(
            name="XmagSigs",
            pvFun=XmagSigs_pvs,
            needCav=False,
            needCM=True,
            desc="Xcor: bact, ps volts, and voltage taps",
        ),
        "YmagSigs": PlotType(
            name="YmagSigs",
            pvFun=YmagSigs_pvs,
            needCav=False,
            needCM=True,
            desc="Ycor: bact, ps volts, and voltage taps",
        ),
        "decarad1raw": PlotType(
            name="decarad1raw",
            pvFun=decarad1raw_pvs,
            needCav=False,
            needCM=False,
            desc="GM tubes for decarad 1 system raw signals",
        ),
        "decarad2raw": PlotType(
            name="decarad2raw",
            pvFun=decarad2raw_pvs,
            needCav=False,
            needCM=False,
            desc="GM tubes for decarad 2 system raw signals",
        ),
        "decarad1ave": PlotType(
            name="decarad1ave",
            pvFun=decarad1ave_pvs,
            needCav=False,
            needCM=False,
            desc="GM tubes for decarad 1 system signals averaged for 10s",
        ),
        "decarad2ave": PlotType(
            name="decarad2ave",
            pvFun=decarad2ave_pvs,
            needCav=False,
            needCM=False,
            desc="GM tubes for decarad 2 system signals averaged for 10s",
        ),
        "cmJTparams": PlotType(
            name="cmJTparams",
            pvFun=cmJTparams_pvs,
            needCav=False,
            needCM=True,
            desc="All JT params for one CM",
        ),
        "cpccmp": PlotType(
            name="cpccmp",
            pvFun=cpccmp_pvs,
            needCav=False,
            needCM=False,
            desc="Cryoplant pressure and cold compressor speeds",
        ),
        "allAACTMEANSUMs": PlotType(
            name="allAACTMEANSUMs",
            pvFun=allAACTMEANSUMs_pvs,
            needCav=False,
            needCM=False,
            desc="LxB:1:AACTMEANSUM",
        ),
        "COL0_BLMs": PlotType(
            name="COL0_BLMs",
            pvFun=COL0_BLMs_pvs,
            needCav=False,
            needCM=False,
            desc="All BLMs in COL0 & HTR areas",
        ),
        "cmSelPoffs": PlotType(
            name="cmSelPoffs",
            pvFun=cmSelPoffs_pvs,
            needCav=False,
            needCM=False,
            desc="All BLMs in COL0 & HTR areas",
            rangeDelta=10,
            rangeFun=cmSelPoffs_ranges,
        ),
        "tenUSLL": PlotType(
            name="tenUSLL",
            pvFun=tenUSLL_pvs,
            needCav=False,
            needCM=False,
            desc="10 US LL starting with selected cm",
        ),
        "tenDSLL": PlotType(
            name="tenDSLL",
            pvFun=tenDSLL_pvs,
            needCav=False,
            needCM=False,
            desc="10 DS LL starting with selected cm",
        ),
        "tenJT": PlotType(
            name="tenJT",
            pvFun=tenJT_pvs,
            needCav=False,
            needCM=False,
            desc="10 JT readbacks starting with selected cm",
        ),
        "tenAACTSUM": PlotType(
            name="tenAACTSUM",
            pvFun=tenAACTSUM_pvs,
            needCav=False,
            needCM=False,
            desc="10 AACTMEANSUM starting with selected cavity",
        ),
    }

    return plotz
