import asyncio
import concurrent.futures
import functools
import os
import threading
from asyncio import create_subprocess_exec
from datetime import datetime
from time import sleep

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyChar,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyBoolEnum,
)
from caproto.server.server import PVGroupMeta

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp

# ca_attach_context in libca is not thread-safe: concurrent calls from
# multiple executor threads segfault.  This lock serialises our
# use_initial_context() calls so each thread attaches cleanly in turn.
# After attachment, PV.context == initial_context, so _ensure_context
# never needs to re-attach and there are no further concurrent calls.
_ca_init_lock = threading.Lock()


def _epics_thread(fn):
    """Attach the main EPICS CA context before calling fn, detach after.

    ThreadPoolExecutor workers are non-EPICS threads.  If they call into
    pyepics without attaching the initial context first, libCom creates a
    per-thread context; when the thread exits libCom's TLS destructor fires
    and panics with "free_threadInfo … can't proceed".  Attaching the shared
    initial context avoids both the implicit context creation and the noisy
    shutdown crash.

    Attachment is serialised via _ca_init_lock because ca_attach_context is
    not safe to call from multiple threads simultaneously.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        import epics.ca

        with _ca_init_lock:
            epics.ca.use_initial_context()
        try:
            return fn(*args, **kwargs)
        finally:
            epics.ca.detach_context()

    return wrapper


# Cavity setups are long-running (minutes). Cap at cpu_count so a full CM (8 cavities)
# can run concurrently on most machines without spawning more threads than cores.
_CAVITY_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=os.cpu_count(), thread_name_prefix="cavity-setup"
)

# Orchestrators (CM/Linac/Global/Rack) just propagate flags and fire STRT PV writes;
# they finish in seconds, so a larger pool is fine.
_ORCHESTRATOR_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=16, thread_name_prefix="setup-orch"
)


# ---------------------------------------------------------------------------
# In-process cavity functions
# ---------------------------------------------------------------------------


@_epics_thread
def _run_setup_cavity(cm_name: str, cav_num: int) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )

    SETUP_MACHINE.cryomodules[cm_name].cavities[cav_num].setup()


@_epics_thread
def _run_shutdown_cavity(cm_name: str, cav_num: int) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )

    SETUP_MACHINE.cryomodules[cm_name].cavities[cav_num].shut_down()


# ---------------------------------------------------------------------------
# In-process CM functions
# ---------------------------------------------------------------------------


@_epics_thread
def _run_setup_cm(cm_name: str) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )

    cm = SETUP_MACHINE.cryomodules[cm_name]
    for cavity in cm.cavities.values():
        cavity.ssa_cal_requested = cm.ssa_cal_requested
        cavity.auto_tune_requested = cm.auto_tune_requested
        cavity.cav_char_requested = cm.cav_char_requested
        cavity.rf_ramp_requested = cm.rf_ramp_requested
        cavity.trigger_start()
        sleep(0.1)


@_epics_thread
def _run_shutdown_cm(cm_name: str) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )

    for cavity in SETUP_MACHINE.cryomodules[cm_name].cavities.values():
        cavity.trigger_shutdown()
        sleep(0.1)


# ---------------------------------------------------------------------------
# In-process Rack functions (no sc-setup-rack script exists)
# Flag values are read from the PVGroup in the async context and passed in.
# ---------------------------------------------------------------------------


@_epics_thread
def _run_setup_rack(
    cm_name: str,
    rack_name: str,
    ssa_cal: bool,
    auto_tune: bool,
    cav_char: bool,
    rf_ramp: bool,
) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )

    cm = SETUP_MACHINE.cryomodules[cm_name]
    cav_range = range(1, 5) if rack_name == "A" else range(5, 9)
    for cav_num in cav_range:
        cavity = cm.cavities[cav_num]
        cavity.ssa_cal_requested = ssa_cal
        cavity.auto_tune_requested = auto_tune
        cavity.cav_char_requested = cav_char
        cavity.rf_ramp_requested = rf_ramp
        cavity.trigger_start()
        sleep(0.1)


@_epics_thread
def _run_shutdown_rack(cm_name: str, rack_name: str) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )

    cm = SETUP_MACHINE.cryomodules[cm_name]
    cav_range = range(1, 5) if rack_name == "A" else range(5, 9)
    for cav_num in cav_range:
        cm.cavities[cav_num].trigger_shutdown()
        sleep(0.1)


# ---------------------------------------------------------------------------
# In-process Linac functions
# ---------------------------------------------------------------------------


@_epics_thread
def _run_setup_linac(linac_idx: int) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )
    from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_DICT

    linac = SETUP_MACHINE.linacs[linac_idx]
    for cm_name in LINAC_CM_DICT[linac_idx]:
        cm = SETUP_MACHINE.cryomodules[cm_name]
        cm.ssa_cal_requested = linac.ssa_cal_requested
        cm.auto_tune_requested = linac.auto_tune_requested
        cm.cav_char_requested = linac.cav_char_requested
        cm.rf_ramp_requested = linac.rf_ramp_requested
        cm.trigger_start()
        sleep(0.5)


@_epics_thread
def _run_shutdown_linac(linac_idx: int) -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )
    from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_DICT

    for cm_name in LINAC_CM_DICT[linac_idx]:
        SETUP_MACHINE.cryomodules[cm_name].trigger_shutdown()
        sleep(0.5)


# ---------------------------------------------------------------------------
# In-process Global functions
# ---------------------------------------------------------------------------


@_epics_thread
def _run_setup_global() -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )
    from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

    for cm_name in ALL_CRYOMODULES:
        cm = SETUP_MACHINE.cryomodules[cm_name]
        cm.ssa_cal_requested = SETUP_MACHINE.ssa_cal_requested
        cm.auto_tune_requested = SETUP_MACHINE.auto_tune_requested
        cm.cav_char_requested = SETUP_MACHINE.cav_char_requested
        cm.rf_ramp_requested = SETUP_MACHINE.rf_ramp_requested
        cm.trigger_start()


@_epics_thread
def _run_shutdown_global() -> None:
    from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
        SETUP_MACHINE,
    )
    from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

    for cm_name in ALL_CRYOMODULES:
        SETUP_MACHINE.cryomodules[cm_name].trigger_shutdown()


class LauncherPVGroupMeta(PVGroupMeta):
    """Metaclass that adds launcher-specific PVs before PVGroup processes them"""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Check if this class has LAUNCHER_NAME set
        launcher_name = namespace.get("LAUNCHER_NAME")

        if launcher_name is not None:
            # Add dynamic properties to the namespace before the class is created

            # Start property
            async def _start_putter(obj, instance, value):
                await obj.trigger_start()
                return value

            start_prop = pvproperty(
                name=f"{launcher_name}STRT",
                dtype=ChannelType.ENUM,
                enum_strings=("Start", "Start"),
            ).putter(_start_putter)
            namespace["start"] = start_prop

            # Stop property
            async def _stop_putter(obj, instance, value):
                await obj.trigger_stop()
                return value

            stop_prop = pvproperty(
                name=f"{launcher_name}STOP",
                dtype=ChannelType.ENUM,
                enum_strings=("Stop", "Stop"),
            ).putter(_stop_putter)
            namespace["stop"] = stop_prop

            # Timestamp property
            namespace["timestamp"] = pvproperty(
                name=f"{launcher_name}TS",
                dtype=ChannelType.STRING,
                value="",
            )

            # Status property
            namespace["status"] = pvproperty(
                name=f"{launcher_name}STS",
                dtype=ChannelType.STRING,
                value="Ready",
            )

            # Add Setup-specific properties (SETUP is the most complex)
            if launcher_name == "SETUP":
                namespace["ssa_cal"] = pvproperty(
                    name=f"{launcher_name}_SSAREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )
                namespace["tune"] = pvproperty(
                    name=f"{launcher_name}_TUNEREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )
                namespace["cav_char"] = pvproperty(
                    name=f"{launcher_name}_CHARREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )
                namespace["ramp"] = pvproperty(
                    name=f"{launcher_name}_RAMPREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )

            # Handle OFF-specific init wrapping (only OFF needs the -off flag)
            if launcher_name == "OFF":
                original_init = namespace.get("__init__")
                if original_init is None:
                    # Find __init__ in base classes
                    for base in bases:
                        if hasattr(base, "__init__"):
                            original_init = base.__init__
                            break

                def new_init(self, *args, **kwargs):
                    original_init(self, *args, **kwargs)
                    self.extra_flags = ["-off"]

                namespace["__init__"] = new_init

        # Now let PVGroup's metaclass do its magic
        return super().__new__(mcs, name, bases, namespace, **kwargs)


class LauncherPVGroup(PVGroup, metaclass=LauncherPVGroupMeta):
    """Base class for all launcher types"""

    LAUNCHER_NAME = None

    note: PvpropertyChar = pvproperty(
        name="NOTE",
        value="This is as long of a sentence as I can type in order to test wrapping",
    )

    abort: PvpropertyEnum = pvproperty(
        name="ABORT",
        dtype=ChannelType.ENUM,
        enum_strings=("No abort request", "Abort request"),
    )

    use_rf: PvpropertyBoolEnum = pvproperty(
        name="USE_RF",
        dtype=ChannelType.ENUM,
        enum_strings=("Use Steps", "Use RF"),
        value=1,
    )

    def __init__(self, prefix: str):
        super().__init__(prefix + "AUTO:")
        self.subgroups = []

    @abort.putter
    async def _abort_putter(self, instance, value):
        await self.handle_abort()
        return value  # Keep the value that was written

    async def handle_abort(self):
        """Propagate abort to subgroups - applications detect the PV write"""
        for subgroup in self.subgroups:
            if hasattr(subgroup, "abort"):
                await subgroup.abort.write(1)

    async def trigger_start(self):
        """Override this in subclasses"""
        raise NotImplementedError

    async def trigger_stop(self):
        """Override this in subclasses"""
        raise NotImplementedError


class BaseScriptPVGroup(LauncherPVGroup):
    """Base class for script-based launchers"""

    def __init__(self, prefix: str, script_name: str, **script_args):
        super().__init__(prefix)
        self.script_name = script_name
        self.script_args = script_args
        self.extra_flags = []
        self.process = None
        self._future = None

    def get_command_args(self):
        """Build command arguments from script name, args, and extra flags"""
        args = [self.script_name]
        for key, value in self.script_args.items():
            args.append(f"-{key}={value}")
        args.extend(self.extra_flags)
        return args

    def _get_run_fn(self):
        """Return a no-arg callable for in-process execution, or None to use subprocess."""
        return None

    def _get_executor(self):
        return _ORCHESTRATOR_EXECUTOR

    async def trigger_start(self):
        run_fn = self._get_run_fn()
        if run_fn is not None:
            if self._future is not None and not self._future.done():
                await self.status.write("Already running")
                return
            await self.timestamp.write(
                datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            )
            await self.status.write("Running")
            self._future = asyncio.get_running_loop().run_in_executor(
                self._get_executor(), run_fn
            )
            asyncio.create_task(self._monitor_future())
        else:
            if self.process and self.process.returncode is None:
                await self.status.write("Already running")
                return
            args = self.get_command_args()
            self.process = await create_subprocess_exec(*args)
            await self.timestamp.write(
                datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            )
            await self.status.write("Running")
            asyncio.create_task(self._monitor_process())

    async def trigger_stop(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()
        await self.timestamp.write(
            datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
        )
        await self.status.write("Stopped")

    async def _monitor_process(self):
        """Monitor process and update status when complete"""
        if self.process:
            returncode = await self.process.wait()
            await self.timestamp.write(
                datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            )
            if returncode == 0:
                await self.status.write("Completed")
            else:
                await self.status.write(f"Failed (exit code: {returncode})")

    async def _monitor_future(self):
        try:
            await self._future
            await self.timestamp.write(
                datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            )
            await self.status.write("Completed")
        except Exception as e:
            await self.timestamp.write(
                datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            )
            await self.status.write(f"Failed: {type(e).__name__}")


class BaseCMPVGroup(BaseScriptPVGroup):
    """Base class for CM launchers"""

    def __init__(self, prefix: str, cm_name: str, cavity_groups=None):
        script_map = {
            "COLD": "sc-cold-cm",
            "PARK": "sc-park-cm",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-cm")
        super().__init__(prefix, script_name, cm=cm_name)
        self.cm_name = cm_name
        self.subgroups = cavity_groups or []


class BaseLinacPVGroup(BaseScriptPVGroup):
    """Base class for linac launchers"""

    def __init__(self, prefix: str, linac_idx: int, cm_groups=None):
        script_map = {
            "COLD": "sc-cold-linac",
            "PARK": "sc-park-linac",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-linac")
        super().__init__(prefix, script_name, l=linac_idx)
        self.linac_idx = linac_idx
        self.subgroups = cm_groups or []


class BaseGlobalPVGroup(BaseScriptPVGroup):
    """Base class for global launchers"""

    def __init__(self, prefix: str, linac_groups=None):
        script_map = {
            "COLD": "sc-cold-all",
            "PARK": "sc-park-all",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-all")
        super().__init__(prefix, script_name)
        self.subgroups = linac_groups or []


class BaseRackPVGroup(BaseScriptPVGroup):
    """Base class for rack launchers"""

    def __init__(
        self, prefix: str, cm_name: str, rack_name: str, rack_groups=None
    ):
        script_map = {
            "COLD": "sc-cold-rack",
            "PARK": "sc-park-rack",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-rack")
        # Use 'cm' and 'r' to match the script's short flags
        super().__init__(prefix, script_name, cm=cm_name, r=rack_name)
        self.cm_name = cm_name
        self.rack_name = rack_name
        self.subgroups = rack_groups or []


class BaseCavityPVGroup(BaseScriptPVGroup):
    """Base class for cavity launchers"""

    # Cavity-specific additional properties
    progress: PvpropertyFloat = pvproperty(
        name="PROG", value=0.0, dtype=ChannelType.FLOAT
    )
    status_sevr: SeverityProp = SeverityProp(name="STATUS", value=0)

    status_enum: PvpropertyEnum = pvproperty(
        name="STATUS",
        dtype=ChannelType.ENUM,
        enum_strings=("Ready", "Running", "Error"),
    )

    status_message: PvpropertyChar = pvproperty(
        name="MSG", value="Ready", max_length=256
    )

    time_stamp: PvpropertyChar = pvproperty(
        name="TS",
        value=datetime.now().strftime("%m/%d/%y %H:%M:%S.%f"),
        dtype=ChannelType.CHAR,
    )

    def __init__(self, prefix: str, cm_name: str, cav_num: int):
        script_map = {
            "COLD": "sc-cold-cav",
            "PARK": "sc-park-cav",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-cav")
        super().__init__(prefix, script_name, cm=cm_name, cav=cav_num)
        self.cm_name = cm_name
        self.cav_num = cav_num
        self.subgroups = []

    def _get_executor(self):
        return _CAVITY_EXECUTOR

    @status_enum.putter
    async def _status_enum_putter(self, instance, value):
        if isinstance(value, int):
            await self.status_sevr.write(value)
        else:
            await self.status_sevr.write(
                ["Ready", "Running", "Error"].index(value)
            )
        return value


# ============================================================================
# SETUP Launchers
# ============================================================================


class SetupCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "SETUP"

    def _get_run_fn(self):
        return functools.partial(_run_setup_cm, self.cm_name)


class SetupLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "SETUP"

    def _get_run_fn(self):
        return functools.partial(_run_setup_linac, self.linac_idx)


class SetupGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "SETUP"

    def _get_run_fn(self):
        return _run_setup_global


class SetupCavityPVGroup(BaseCavityPVGroup):
    """In-process setup simulation: runs as an asyncio coroutine instead of
    spawning a subprocess, so hundreds of cavities can run concurrently on the
    single caproto event loop without overwhelming the server.
    """

    LAUNCHER_NAME = "SETUP"

    def _get_run_fn(self):
        return functools.partial(_run_setup_cavity, self.cm_name, self.cav_num)


class SetupRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "SETUP"

    def _get_run_fn(self):
        return functools.partial(
            _run_setup_rack,
            self.cm_name,
            self.rack_name,
            bool(self.ssa_cal.value),
            bool(self.tune.value),
            bool(self.cav_char.value),
            bool(self.ramp.value),
        )


# ============================================================================
# OFF Launchers
# ============================================================================


class OffCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "OFF"

    def _get_run_fn(self):
        return functools.partial(_run_shutdown_cm, self.cm_name)


class OffLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "OFF"

    def _get_run_fn(self):
        return functools.partial(_run_shutdown_linac, self.linac_idx)


class OffGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "OFF"

    def _get_run_fn(self):
        return _run_shutdown_global


class OffCavityPVGroup(BaseCavityPVGroup):
    """In-process shutdown simulation — mirrors SetupCavityPVGroup."""

    LAUNCHER_NAME = "OFF"

    def _get_run_fn(self):
        return functools.partial(
            _run_shutdown_cavity, self.cm_name, self.cav_num
        )


class OffRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "OFF"

    def _get_run_fn(self):
        return functools.partial(
            _run_shutdown_rack, self.cm_name, self.rack_name
        )


# ============================================================================
# COLD Launchers
# ============================================================================


class ColdCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "COLD"


# ============================================================================
# PARK Launchers
# ============================================================================


class ParkCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "PARK"
