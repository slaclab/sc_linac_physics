from typing import Optional, Tuple


def extract_cavity_channel_from_pv(pv_string: str) -> Optional[Tuple[int, str]]:
    """
    Gets cavity number and channel type from PV string from data file headers.
    Args:
        pv_string: Full PV string were parsing
    Returns:
        A tuple with (cavity_number, channel_type)
    """
    try:
        # Breaking up the input string into a list of smaller strings using :
        parts = pv_string.split(':')
        # Checking if theres at least 6 parts (making sure basic structure is there)
        # Making sure 4th part is exactly 'PZT' and 6th part is 'WF'
        if len(parts) >= 6 and parts[3] == 'PZT' and parts[5] == 'WF':
            # So if basic structure is good we grab the 3rd part (i2) which has CM and CAV info
            segment3 = parts[2]
            # Further validating, is it exactly 4 char long and does it end with 0
            if len(segment3) == 4 and segment3.endswith('0'):
                # If segment format is right we take 3rd character and convert into int number
                # (e.g the 5 from "0250" the cavity number)
                cav_num = int(segment3[2])
                # Grab 5th part of OG split list (e.g "DF")
                channel_type = parts[4]

                return cav_num, channel_type
            else:
                return None
        else:
            # PV string does not match the expected pattern
            return None
    except(IndexError, ValueError) as e:
        return None


# PV Formatting Helpers
# Takes linac (e.g "L1B" and module e.g "3" or "03") as input
def format_accl_base(linac: str, module: str) -> str:
    """
    Formats base ACCL string
    """
    # If module is 3 module_id will = 03
    module_id = f"{module:0>2}"
    # Assembling final string
    return f"ACCL:{linac}:{module_id}00"


def format_chassis_id(accl_base: str, rack: str) -> str:
    """Formats the chassis ID used for acquisition
    Example: ACCL:L1B:0300:RESA"""
    # Checking if uppercase version of rack is "A" if true rack_suffix becomes "RESA"
    rack_suffix = 'RESA' if rack.upper() == 'A' else "RESB"
    # Returning right rack suffix (e.g "ACCL:L1B:0300:RESA")
    return f"{accl_base}:{rack_suffix}"


# Takes base and rack
def format_pv_base(accl_base: str, rack: str) -> str:
    """Formats PV base string for Channel Access script argument"""
    # Reusing prev helper function to get chassis ID
    chassis_id = format_chassis_id(accl_base, rack)
    # Needed "ca://" for -a argument of acquisition script (e.g "ca://ACCL:L1B:0300:RESA:")
    return f"ca://{chassis_id}"
