import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, List

# Import your local MicrophonicsConfig and MicrophonicsCavity classes
from microphonics_core import MicrophonicsConfig, MicrophonicsCavity

logger = logging.getLogger(__name__)


class HardwareInterface:
    """Interface for handling hardware script setup and interactions"""

    def __init__(self):
        self.initialized = False
        self.data_acq = None
        self.res_ctl = None
        self.res_waves = None

    def initialize(self) -> Tuple[bool, Optional[str]]:
        """Initialize hardware interface and verify access"""
        try:
            success, error = self._setup_imports()
            if not success:
                return False, error

            success, error = self._verify_imports()
            if not success:
                return False, error

            self.initialized = True
            return True, None

        except Exception as e:
            return False, f"Failed to initialize hardware interface: {str(e)}"

    def _setup_imports(self) -> Tuple[bool, Optional[str]]:
        """Setup paths and import hardware scripts"""
        try:
            # Add path to res_data_acq.py and related scripts
            script_dir = Path('/Users/haleym/Downloads/res_ctl_2')
            logger.info(f"Looking for scripts in: {script_dir}")

            if not script_dir.exists():
                return False, f"Script directory not found: {script_dir}"

            sys.path.append(str(script_dir))

            # Try importing our local modules first
            try:
                import res_data_acq
                import res_ctl
                logger.info("Successfully imported local hardware modules")
                return True, None
            except ImportError as e:
                return False, f"Failed to import local hardware modules: {str(e)}"

        except Exception as e:
            return False, f"Error setting up imports: {str(e)}"

    def _verify_imports(self) -> Tuple[bool, Optional[str]]:
        """Verify all required imports are available"""
        try:
            # Import required modules

            import res_data_acq
            from res_ctl import c_res_ctl
            import res_waves

            # Store module references
            self.data_acq = res_data_acq.data_acq
            self.res_ctl = c_res_ctl
            self.res_waves = res_waves

            return True, None

        except ImportError as e:
            return False, f"Failed to import required module: {str(e)}"

    def create_config(self, linac: str, cryo_name: str,
                      cavities: List[int], **kwargs) -> Optional[MicrophonicsConfig]:
        """Create a measurement configuration"""
        if not self.initialized:
            logger.error("Hardware interface not initialized")
            return None

        try:
            config = MicrophonicsConfig(
                linac=linac,
                cryo_name=cryo_name,
                selected_cavities=cavities,
                **kwargs
            )
            return config
        except Exception as e:
            logger.error(f"Failed to create config: {str(e)}")
            return None

    def test_connection(self, config: MicrophonicsConfig) -> Tuple[bool, Optional[str]]:
        """Test connection to hardware with given configuration"""
        if not self.initialized:
            return False, "Hardware interface not initialized"

        try:
            # Build PV prefix
            cryo_prefix = f"ACCL:{config.linac}:{config.cryo_name}00"

            # Try creating a cavity object
            test_cavity = MicrophonicsCavity(
                cavity_num=config.selected_cavities[0],
                cryo_prefix=cryo_prefix
            )

            # Check if cavity is online
            if not test_cavity.check_cavity_online():
                return False, "Cavity PVs not responding"

            return True, None

        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
