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
        parts = pv_string.split(':')
        if len(parts) >= 6 and parts[3] == 'PZT' and parts[5] == 'WF':
            segment3 = parts[2]
            if len(segment3) == 4 and segment3.endswith('0'):
                cav_num = int(segment3[2])
                channel_type = parts[4]

                return cav_num, channel_type
            else:
                return None
        else:
            return None
    except(IndexError, ValueError) as e:
        return None


# PV Formatting Helpers
def format_accl_base(linac: str, module: str) -> str:
    """
    Formats base ACCL string
    """
    module_id = f"{module:0>2}"
    # Assembling final string
    return f"ACCL:{linac}:{module_id}00"


def format_chassis_id(accl_base: str, rack: str) -> str:
    """Formats the chassis ID used for acquisition
    Example: ACCL:L1B:0300:RESA"""
    rack_suffix = 'RESA' if rack.upper() == 'A' else "RESB"
    # Returning right rack suffix (e.g "ACCL:L1B:0300:RESA")
    return f"{accl_base}:{rack_suffix}"


# Takes base and rack
def format_pv_base(accl_base: str, rack: str) -> str:
    """Formats PV base string for Channel Access script argument"""
    # Reusing prev helper function to get chassis ID
    chassis_id = format_chassis_id(accl_base, rack)
    # Needed "ca://" for -a argument of acquisition script (e.g "ca://ACCL:L1B:0300:RESA:")
    return f"ca://{chassis_id}:"
