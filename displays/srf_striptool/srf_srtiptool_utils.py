"""
================================================================================
autoPlot utilities

list variables needed by multiple programs
Most stolen from CMIM's Utility.py - thanks, Zack!
J Nelson 3/17/2022
================================================================================
"""
import math

# ==============================================================================
# GLOBAL CONFIGURATION
# ==============================================================================

PLOTS = [
    "cavtemps",
    "cryopipe",
    "cplrtop",
    "cplrbot",
    "homus",
    "homds",
    "steptmps",
    "cmcryos",
    "cmheves",
    "cavhtrs",
    "cmpiezov",
    "cmvac",
    "cmaact",
    "cmpdes",
    "cmpact",
    "cmFwdP",
    "cmDFbest",
    "cmmag",
    "magtemps",
    "magVtaps",
    "magCLtaps",
    "QmagSigs",
    "XmagSigs",
    "YmagSigs",
    "decarad1raw",
    "decarad2raw",
    "decarad1ave",
    "decarad2ave",
    "cmJTparams",
    "cpccmp",
]
DESCS = [
    "One cavity's temps: stepper, two couplers, US HOM, DS HOM, and HeVes if Cav=1 or 5",
    "Cryopipe temps for one CM: A, B1, B2, C, D, E, F, shield, and two cooldown",
    "All coupler top (CPLRTEMP1) temps in one CM, cavities 1-8",
    "All coupler bottom (CPLRTEMP2) temps in one CM, cavities 1-8",
    "All upstream HOM temps (1x18:UH:TEMP) in one CM, cavities 1-8",
    "All downstream HOM temps (1x20:DH:TEMP) in one CM, cavities 1-8",
    "All stepper motor temps (STEPTEMP) in one CM, cavities 1-8",
    "Misc cryo signals for one CM: US/DS LL, US/DS pressure, JT/CD posn, CD:POWER",
    "All helium vessel temps in one CM, cavities 1 & 5, top and bottom",
    "All 8 cavity heaters in one CM (HV:POWER)",
    "All 8 piezo volts in one CM (PZT:V)",
    "Three vacuum signals for each CM: beamline, coupler, insulating",
    "All 8 cavity amplitudes (AACTMEAN) in one CM",
    "All 8 cavity desired phases (PDES) in one CM",
    "All 8 cavity measured phases (PACTMEAN) in one CM",
    "All 8 cavity forward powers in one CM",
    "All 8 cavity DFBEST in one CM",
    "Magnet (QUAD, XCOR, YCOR) settings (BACT), PS output volts, and magnet heater in one CM",
    "All magnet temps (magnet body and clamp) in one CM",
    "All magnet voltage taps",
    "All magnet Power Lead taps",
    "bact, ps volts, voltage taps for quad",
    "bact, ps volts, volt taps for xcor",
    "bact, ps volts, volt taps for ycor",
    "GM tubes for decarad system 1",
    "GM tubes for decarad system 2",
    "10s average for decarad system 1",
    "10s average for decarad system 2",
    "All JT params for one CM",
    "Cryoplant pressure and cold compressor speeds",
]

# Does this plot require a cavity specification too? 1 = yes, 0 = no
REQCAV = [
    1,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
]
# Does this plot require a cm specification too? 1 = yes, 0 = no
REQCM = [
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    0,
    0,
    0,
    0,
    1,
    0,
]

# Which displays are the UsualSuspects
USUALSUSPECTS = [0, 2, 3, 4, 5, 6, 7, 11]

# CMID = <SC linac> : <CM ID>
CRYOMODULE_IDS = [
    "ACCL:L0B:01",
    "ACCL:L1B:02",
    "ACCL:L1B:03",
    "ACCL:L1B:H1",
    "ACCL:L1B:H2",
    "ACCL:L2B:04",
    "ACCL:L2B:05",
    "ACCL:L2B:06",
    "ACCL:L2B:07",
    "ACCL:L2B:08",
    "ACCL:L2B:09",
    "ACCL:L2B:10",
    "ACCL:L2B:11",
    "ACCL:L2B:12",
    "ACCL:L2B:13",
    "ACCL:L2B:14",
    "ACCL:L2B:15",
    "ACCL:L3B:16",
    "ACCL:L3B:17",
    "ACCL:L3B:18",
    "ACCL:L3B:19",
    "ACCL:L3B:20",
    "ACCL:L3B:21",
    "ACCL:L3B:22",
    "ACCL:L3B:23",
    "ACCL:L3B:24",
    "ACCL:L3B:25",
    "ACCL:L3B:26",
    "ACCL:L3B:27",
    "ACCL:L3B:28",
    "ACCL:L3B:29",
    "ACCL:L3B:30",
    "ACCL:L3B:31",
    "ACCL:L3B:32",
    "ACCL:L3B:33",
    "ACCL:L3B:34",
    "ACCL:L3B:35",
]


# Vaccuum PVs are nonpatternistic, so they are hardocded here

PV_VAC_BEAMLINE = [
    "VGXX:L0B:0198:COMBO_P",
    "VGXX:L1B:0202:COMBO_P",
    "VGXX:L1B:0202:COMBO_P",
    "VGXX:L1B:H292:COMBO_P",
    "VGXX:L1B:H292:COMBO_P",
    "VGXX:L2B:0402:COMBO_P",
    "VGXX:L2B:0402:COMBO_P",
    "VGXX:L2B:0402:COMBO_P",
    "VGXX:L2B:0402:COMBO_P",
    "VGXX:L2B:0402:COMBO_P",
    "VGXX:L2B:0402:COMBO_P",
    "VGXX:L2B:1592:COMBO_P",
    "VGXX:L2B:1592:COMBO_P",
    "VGXX:L2B:1592:COMBO_P",
    "VGXX:L2B:1592:COMBO_P",
    "VGXX:L2B:1592:COMBO_P",
    "VGXX:L2B:1592:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:1602:COMBO_P",
    "VGXX:L3B:2594:COMBO_P",
    "VGXX:L3B:2594:COMBO_P",
    "VGXX:L3B:2594:COMBO_P",
    "VGXX:L3B:2594:COMBO_P",
    "VGXX:L3B:2594:COMBO_P",
    "VGXX:L3B:2594:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
    "VGXX:L3B:3592:COMBO_P",
]

PV_VAC_COUPLER = [
    "VGXX:L0B:0114:COMBO_P",
    "VGXX:L1B:0214:COMBO_P",
    "VGXX:L1B:0314:COMBO_P",
    "VGXX:L1B:H109:COMBO_P",
    "VGXX:L1B:H209:COMBO_P",
    "VGXX:L2B:0414:COMBO_P",
    "VGXX:L2B:0514:COMBO_P",
    "VGXX:L2B:0614:COMBO_P",
    "VGXX:L2B:0714:COMBO_P",
    "VGXX:L2B:0814:COMBO_P",
    "VGXX:L2B:0914:COMBO_P",
    "VGXX:L2B:1014:COMBO_P",
    "VGXX:L2B:1114:COMBO_P",
    "VGXX:L2B:1214:COMBO_P",
    "VGXX:L2B:1314:COMBO_P",
    "VGXX:L2B:1414:COMBO_P",
    "VGXX:L2B:1514:COMBO_P",
    "VGXX:L3B:1614:COMBO_P",
    "VGXX:L3B:1714:COMBO_P",
    "VGXX:L3B:1814:COMBO_P",
    "VGXX:L3B:1914:COMBO_P",
    "VGXX:L3B:2014:COMBO_P",
    "VGXX:L3B:2114:COMBO_P",
    "VGXX:L3B:2214:COMBO_P",
    "VGXX:L3B:2314:COMBO_P",
    "VGXX:L3B:2414:COMBO_P",
    "VGXX:L3B:2514:COMBO_P",
    "VGXX:L3B:2614:COMBO_P",
    "VGXX:L3B:2714:COMBO_P",
    "VGXX:L3B:2814:COMBO_P",
    "VGXX:L3B:2914:COMBO_P",
    "VGXX:L3B:3014:COMBO_P",
    "VGXX:L3B:3114:COMBO_P",
    "VGXX:L3B:3214:COMBO_P",
    "VGXX:L3B:3314:COMBO_P",
    "VGXX:L3B:3414:COMBO_P",
    "VGXX:L3B:3514:COMBO_P",
]

PV_VAC_INSULATING = [
    "VGXX:L0B:0196:COMBO_P",
    "VGXX:L1B:0296:COMBO_P",
    "VGXX:L1B:0296:COMBO_P",
    "VGXX:L1B:H196:COMBO_P",
    "VGXX:L1B:H196:COMBO_P",
    "VGXX:L2B:0496:COMBO_P",
    "VGXX:L2B:0496:COMBO_P",
    "VGXX:L2B:0696:COMBO_P",
    "VGXX:L2B:0696:COMBO_P",
    "VGXX:L2B:0896:COMBO_P",
    "VGXX:L2B:0896:COMBO_P",
    "VGXX:L2B:1096:COMBO_P",
    "VGXX:L2B:1096:COMBO_P",
    "VGXX:L2B:1296:COMBO_P",
    "VGXX:L2B:1296:COMBO_P",
    "VGXX:L2B:1496:COMBO_P",
    "VGXX:L2B:1496:COMBO_P",
    "VGXX:L3B:1696:COMBO_P",
    "VGXX:L3B:1696:COMBO_P",
    "VGXX:L3B:1896:COMBO_P",
    "VGXX:L3B:1896:COMBO_P",
    "VGXX:L3B:2096:COMBO_P",
    "VGXX:L3B:2096:COMBO_P",
    "VGXX:L3B:2296:COMBO_P",
    "VGXX:L3B:2296:COMBO_P",
    "VGXX:L3B:2496:COMBO_P",
    "VGXX:L3B:2496:COMBO_P",
    "VGXX:L3B:2796:COMBO_P",
    "VGXX:L3B:2796:COMBO_P",
    "VGXX:L3B:2796:COMBO_P",
    "VGXX:L3B:2996:COMBO_P",
    "VGXX:L3B:2996:COMBO_P",
    "VGXX:L3B:3196:COMBO_P",
    "VGXX:L3B:3196:COMBO_P",
    "VGXX:L3B:3396:COMBO_P",
    "VGXX:L3B:3496:COMBO_P",
    "VGXX:L3B:3496:COMBO_P",
]

PV_GAL_TEMPS = [
    "ROOM:LI00:1:KG:TEMP",
    "ROOM:LI01:1:KG:TEMP",
    "ROOM:LI01:1:KG:TEMP",
    "ROOM:LI02:1:KG:TEMP",
    "ROOM:LI02:1:KG:TEMP",
    "ROOM:LI02:1:KG:TEMP",
    "ROOM:LI02:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI03:1:KG:TEMP",
    "ROOM:LI04:1:KG:TEMP",
    "ROOM:LI04:1:KG:TEMP",
    "ROOM:LI04:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI05:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI06:1:KG:TEMP",
    "ROOM:LI07:1:KG:TEMP",
    "ROOM:LI07:1:KG:TEMP",
]


# calculate how many rows (nr) and columns (nc) for the grid
#  of plot names on the ui
def aspectRatio(listLen):
    if listLen > 100:
        nr = 10
        nc = 10
        print("function aspectRatio can only make a grid for 100 or less plot names")
    else:
        nr = math.ceil(math.sqrt(listLen))
        nc = math.floor(math.sqrt(listLen))
        if nr * nc < listLen:
            nc += 1
    return (nr, nc)


# ==============================================================================
# GETTERS
# ==============================================================================


def plots():
    return PLOTS


def descs():
    return DESCS


def reqcav():
    return REQCAV


def reqcm():
    return REQCM


def CM_IDs():
    return CRYOMODULE_IDS


def blvacPVs():
    return PV_VAC_BEAMLINE


def cplrvacPVs():
    return PV_VAC_COUPLER


def insvacPVs():
    return PV_VAC_INSULATING


def galTempPVs():
    return PV_GAL_TEMPS
