# CHANGELOG

<!-- version list -->

## v5.0.0 (2025-11-24)

### Bug Fixes

- Removing unused flag from pv object put call
  ([#153](https://github.com/slaclab/sc_linac_physics/pull/153),
  [`928b85f`](https://github.com/slaclab/sc_linac_physics/commit/928b85f00ccc77ddd869a79268b3eefa3bc4e66f))

### Refactoring

- Migrate PV wrapper from lcls_tools to internal implementation
  ([#153](https://github.com/slaclab/sc_linac_physics/pull/153),
  [`928b85f`](https://github.com/slaclab/sc_linac_physics/commit/928b85f00ccc77ddd869a79268b3eefa3bc4e66f))

- **epics**: Implement lazy PV initialization and improve robustness
  ([#153](https://github.com/slaclab/sc_linac_physics/pull/153),
  [`928b85f`](https://github.com/slaclab/sc_linac_physics/commit/928b85f00ccc77ddd869a79268b3eefa3bc4e66f))

- **test**: Prevent log file creation during tests
  ([#153](https://github.com/slaclab/sc_linac_physics/pull/153),
  [`928b85f`](https://github.com/slaclab/sc_linac_physics/commit/928b85f00ccc77ddd869a79268b3eefa3bc4e66f))

### Testing

- **sel-phase-optimizer**: Fix flaky tests and improve determinism
  ([#153](https://github.com/slaclab/sc_linac_physics/pull/153),
  [`928b85f`](https://github.com/slaclab/sc_linac_physics/commit/928b85f00ccc77ddd869a79268b3eefa3bc4e66f))


## v4.2.0 (2025-11-21)

### Bug Fixes

- **logger**: Set proper file permissions for log files and directories
  ([#163](https://github.com/slaclab/sc_linac_physics/pull/163),
  [`06bff30`](https://github.com/slaclab/sc_linac_physics/commit/06bff30c32edbfe9f0da9ea2930eacaf9ad70493))

### Features

- **logging**: Add automatic retry for failed file handler creation
  ([#163](https://github.com/slaclab/sc_linac_physics/pull/163),
  [`06bff30`](https://github.com/slaclab/sc_linac_physics/commit/06bff30c32edbfe9f0da9ea2930eacaf9ad70493))


## v4.1.0 (2025-11-20)

### Features

- **logging**: Add automatic retry for failed file handler creation
  ([#162](https://github.com/slaclab/sc_linac_physics/pull/162),
  [`b5492da`](https://github.com/slaclab/sc_linac_physics/commit/b5492da8281eea29bf5b77d9dc504ab41771af55))


## v4.0.2 (2025-11-20)

### Bug Fixes

- **launcher**: Set current_file on main window for Python displays
  ([#160](https://github.com/slaclab/sc_linac_physics/pull/160),
  [`0fa8e10`](https://github.com/slaclab/sc_linac_physics/commit/0fa8e1034cf28c8c7c69cae4eb4192c0d2e6e60b))

- **logger**: Handle permission errors gracefully with console-only fallback
  ([#161](https://github.com/slaclab/sc_linac_physics/pull/161),
  [`89383ed`](https://github.com/slaclab/sc_linac_physics/commit/89383edfa68f340662c30996f9a8f7935ca45525))

- **srfhome**: Make ui_filename a method instead of attribute
  ([#160](https://github.com/slaclab/sc_linac_physics/pull/160),
  [`0fa8e10`](https://github.com/slaclab/sc_linac_physics/commit/0fa8e1034cf28c8c7c69cae4eb4192c0d2e6e60b))

- **srfhome**: Set ui_filename to resolve PyDMRelatedDisplayButton parent path error
  ([#160](https://github.com/slaclab/sc_linac_physics/pull/160),
  [`0fa8e10`](https://github.com/slaclab/sc_linac_physics/commit/0fa8e1034cf28c8c7c69cae4eb4192c0d2e6e60b))


## v4.0.1 (2025-11-20)

### Bug Fixes

- **srfhome**: Make ui_filename a method instead of attribute
  ([#159](https://github.com/slaclab/sc_linac_physics/pull/159),
  [`8257240`](https://github.com/slaclab/sc_linac_physics/commit/825724004b93f9c2808fa014a0946869228a77e0))

- **srfhome**: Set ui_filename to resolve PyDMRelatedDisplayButton parent path error
  ([#159](https://github.com/slaclab/sc_linac_physics/pull/159),
  [`8257240`](https://github.com/slaclab/sc_linac_physics/commit/825724004b93f9c2808fa014a0946869228a77e0))

- **test**: Prevent permission errors during test collection
  ([#155](https://github.com/slaclab/sc_linac_physics/pull/155),
  [`8857ab7`](https://github.com/slaclab/sc_linac_physics/commit/8857ab789524085bf1118be663b6889d74be32ac))

### Chores

- **ci**: Make Python 3.14 tests non-blocking for releases
  ([`41f277f`](https://github.com/slaclab/sc_linac_physics/commit/41f277f30c1c4a4cf3d6d33c2178f0c9a79649d1))

### Refactoring

- Add rack-level launchers and reorganize launcher architecture
  ([#156](https://github.com/slaclab/sc_linac_physics/pull/156),
  [`bf18dea`](https://github.com/slaclab/sc_linac_physics/commit/bf18dea6aaf0f9d20d4f87a1b9ba058b3a6c9494))

- **test**: Reorganize conftest.py for better maintainability
  ([#155](https://github.com/slaclab/sc_linac_physics/pull/155),
  [`8857ab7`](https://github.com/slaclab/sc_linac_physics/commit/8857ab789524085bf1118be663b6889d74be32ac))

- **utils**: Add rack-level launchers and reorganize launcher architecture
  ([#156](https://github.com/slaclab/sc_linac_physics/pull/156),
  [`bf18dea`](https://github.com/slaclab/sc_linac_physics/commit/bf18dea6aaf0f9d20d4f87a1b9ba058b3a6c9494))

### Testing

- Add comprehensive test coverage for q0, quench processing, and tuning applications
  ([#154](https://github.com/slaclab/sc_linac_physics/pull/154),
  [`e7fa22c`](https://github.com/slaclab/sc_linac_physics/commit/e7fa22ca253fdb910c44a1cd03200a5db28ca710))

- **quench_cavity**: Fix PV access in check_abort uncaught quench test
  ([#154](https://github.com/slaclab/sc_linac_physics/pull/154),
  [`e7fa22c`](https://github.com/slaclab/sc_linac_physics/commit/e7fa22ca253fdb910c44a1cd03200a5db28ca710))

- **simulation**: Add SCLinacPhysicsService test suite
  ([#156](https://github.com/slaclab/sc_linac_physics/pull/156),
  [`bf18dea`](https://github.com/slaclab/sc_linac_physics/commit/bf18dea6aaf0f9d20d4f87a1b9ba058b3a6c9494))


## v4.0.0 (2025-11-19)

### Features

- Add structured logging to cavity operations and setup scripts
  ([#152](https://github.com/slaclab/sc_linac_physics/pull/152),
  [`f2d920f`](https://github.com/slaclab/sc_linac_physics/commit/f2d920f81c8e42874d9b11fcbd330a50e35a73c2))

### Refactoring

- **quench**: Consolidate logging to QuenchCavity level
  ([#152](https://github.com/slaclab/sc_linac_physics/pull/152),
  [`f2d920f`](https://github.com/slaclab/sc_linac_physics/commit/f2d920f81c8e42874d9b11fcbd330a50e35a73c2))

### Testing

- Add logger mocking to prevent file creation
  ([#152](https://github.com/slaclab/sc_linac_physics/pull/152),
  [`f2d920f`](https://github.com/slaclab/sc_linac_physics/commit/f2d920f81c8e42874d9b11fcbd330a50e35a73c2))

### Breaking Changes

- **quench**: QuenchCryomodule class removed


## v3.2.0 (2025-11-18)

### Bug Fixes

- **tests**: Patch failing test ([#149](https://github.com/slaclab/sc_linac_physics/pull/149),
  [`bd90fbe`](https://github.com/slaclab/sc_linac_physics/commit/bd90fbecabe9d8cf31448cef1c412e96813e8f41))

### Build System

- **pyproject**: Add detune launcher CLI commands
  ([#149](https://github.com/slaclab/sc_linac_physics/pull/149),
  [`bd90fbe`](https://github.com/slaclab/sc_linac_physics/commit/bd90fbecabe9d8cf31448cef1c412e96813e8f41))

### Chores

- **tuning**: Add TUNE_MACHINE singleton for reusability
  ([#149](https://github.com/slaclab/sc_linac_physics/pull/149),
  [`bd90fbe`](https://github.com/slaclab/sc_linac_physics/commit/bd90fbecabe9d8cf31448cef1c412e96813e8f41))

### Features

- **launcher**: Add hierarchical abort system and multi-launcher support
  ([#149](https://github.com/slaclab/sc_linac_physics/pull/149),
  [`bd90fbe`](https://github.com/slaclab/sc_linac_physics/commit/bd90fbecabe9d8cf31448cef1c412e96813e8f41))

- **simulation**: Add hierarchical abort system and multi-launcher support
  ([#149](https://github.com/slaclab/sc_linac_physics/pull/149),
  [`bd90fbe`](https://github.com/slaclab/sc_linac_physics/commit/bd90fbecabe9d8cf31448cef1c412e96813e8f41))

### Refactoring

- **simulation**: Restructure main service into modular components
  ([#149](https://github.com/slaclab/sc_linac_physics/pull/149),
  [`bd90fbe`](https://github.com/slaclab/sc_linac_physics/commit/bd90fbecabe9d8cf31448cef1c412e96813e8f41))


## v3.1.0 (2025-11-18)

### Features

- **microphonics**: Add time-based progress estimation for data acquisition
  ([#151](https://github.com/slaclab/sc_linac_physics/pull/151),
  [`5d9d003`](https://github.com/slaclab/sc_linac_physics/commit/5d9d0033fb65a7f12e90a56e32b709714a288992))


## v3.0.3 (2025-11-12)

### Chores

- Patching tests ([#147](https://github.com/slaclab/sc_linac_physics/pull/147),
  [`6fae9eb`](https://github.com/slaclab/sc_linac_physics/commit/6fae9eb4ef502f0eb2457e05ba3320cd0c46471f))

### Refactoring

- **quench**: Replace print statements with structured logging
  ([#147](https://github.com/slaclab/sc_linac_physics/pull/147),
  [`6fae9eb`](https://github.com/slaclab/sc_linac_physics/commit/6fae9eb4ef502f0eb2457e05ba3320cd0c46471f))


## v3.0.2 (2025-11-12)

### Bug Fixes

- **build**: Resolve packaging warnings and deprecated license format
  ([#148](https://github.com/slaclab/sc_linac_physics/pull/148),
  [`12c6df4`](https://github.com/slaclab/sc_linac_physics/commit/12c6df470ddd3d170cbf6c74e692fce55b25c6ab))


## v3.0.1 (2025-11-12)

### Bug Fixes

- **ci**: Prevent release job from hanging when no version is created
  ([`553af91`](https://github.com/slaclab/sc_linac_physics/commit/553af91845a602742fc4931c7f4cd4d732fac12f))


## v3.0.0 (2025-11-10)

### Refactoring

- Delete setup_linac_object.py ([#144](https://github.com/slaclab/sc_linac_physics/pull/144),
  [`6c8e0e6`](https://github.com/slaclab/sc_linac_physics/commit/6c8e0e675bc128e047bc5852b61826a0d638c9c9))

- Extract common launcher functionality to base classes
  ([#144](https://github.com/slaclab/sc_linac_physics/pull/144),
  [`6c8e0e6`](https://github.com/slaclab/sc_linac_physics/commit/6c8e0e675bc128e047bc5852b61826a0d638c9c9))

- Remove unused AutoLinacObject class ([#144](https://github.com/slaclab/sc_linac_physics/pull/144),
  [`6c8e0e6`](https://github.com/slaclab/sc_linac_physics/commit/6c8e0e675bc128e047bc5852b61826a0d638c9c9))


## v2.2.1 (2025-11-10)

### Chores

- Patching tests ([#143](https://github.com/slaclab/sc_linac_physics/pull/143),
  [`e93fb99`](https://github.com/slaclab/sc_linac_physics/commit/e93fb993de3d3045445f6d838acc21534a7c4dc6))

### Refactoring

- **simulation**: Remove deprecated auto_setup_service module
  ([#143](https://github.com/slaclab/sc_linac_physics/pull/143),
  [`e93fb99`](https://github.com/slaclab/sc_linac_physics/commit/e93fb993de3d3045445f6d838acc21534a7c4dc6))

- **simulation**: Rename launcher services and add Off groups
  ([#143](https://github.com/slaclab/sc_linac_physics/pull/143),
  [`e93fb99`](https://github.com/slaclab/sc_linac_physics/commit/e93fb993de3d3045445f6d838acc21534a7c4dc6))


## v2.2.0 (2025-11-06)

### Features

- **cryo_signals**: Add linac-wide cryomodule monitoring display
  ([#141](https://github.com/slaclab/sc_linac_physics/pull/141),
  [`f90b754`](https://github.com/slaclab/sc_linac_physics/commit/f90b754fd1b46af8db171cc179c3320d7e64fa2b))


## v2.1.0 (2025-11-06)

### Bug Fixes

- **tests**: Correct plot widget attribute name in tests
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

### Code Style

- **displays**: Set window title for plot display
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

### Features

- Add Y-axis range control dialog ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

- **displays**: Add hierarchical PV time plot selector
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

- **displays**: Add hierarchical PV time plot utility
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

- **displays**: Implement multi-axis archiver plot with grouped PVs
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

### Refactoring

- **displays**: Improve action button placement
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))

### Testing

- **displays**: Add plot display and utils test suite
  ([#140](https://github.com/slaclab/sc_linac_physics/pull/140),
  [`33fbcf0`](https://github.com/slaclab/sc_linac_physics/commit/33fbcf0614b4918f487d350faeaa934bc9ad141e))


## v2.0.2 (2025-10-29)

### Bug Fixes

- Prevent PyDM connection errors in cavity display tests
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))

- **cavity-display**: Ignore Qt signal args in button handler
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))

- **test**: Disable PyDM data plugins to prevent connection errors
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))

- **tests**: Prevent module import side effects in cavity display test
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))

### Refactoring

- Reorganize CLI structure and improve testability
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))

### Testing

- Fix launcher tests to prevent PyDM widget instantiation
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))

- Improve CLI launcher test coverage and add integration tests
  ([#138](https://github.com/slaclab/sc_linac_physics/pull/138),
  [`5d55a24`](https://github.com/slaclab/sc_linac_physics/commit/5d55a243c93df418ea5cb7e06f77b4f737ab1037))


## v2.0.1 (2025-10-28)

### Refactoring

- Restructure CLI and improve watcher script management
  ([#137](https://github.com/slaclab/sc_linac_physics/pull/137),
  [`c870ac4`](https://github.com/slaclab/sc_linac_physics/commit/c870ac4516e8d4264a44307320b8dbdd396120cb))


## v2.0.0 (2025-10-24)

### Build System

- Configure package manifest and pre-commit hooks
  ([#135](https://github.com/slaclab/sc_linac_physics/pull/135),
  [`674569e`](https://github.com/slaclab/sc_linac_physics/commit/674569e68f7aa5dac490453435153ed71c8e09be))

### Continuous Integration

- Add package verification to release and CI workflows
  ([#135](https://github.com/slaclab/sc_linac_physics/pull/135),
  [`674569e`](https://github.com/slaclab/sc_linac_physics/commit/674569e68f7aa5dac490453435153ed71c8e09be))

- Add Python 3.14 as experimental test target
  ([#135](https://github.com/slaclab/sc_linac_physics/pull/135),
  [`674569e`](https://github.com/slaclab/sc_linac_physics/commit/674569e68f7aa5dac490453435153ed71c8e09be))

- Add Python 3.14 as experimental test target
  ([#134](https://github.com/slaclab/sc_linac_physics/pull/134),
  [`e066af6`](https://github.com/slaclab/sc_linac_physics/commit/e066af6b37655de22d814a0d35226f0f13d7c277))

### Features

- **cli**: Add hierarchical setup commands and streamline script names
  ([#136](https://github.com/slaclab/sc_linac_physics/pull/136),
  [`6f1f49c`](https://github.com/slaclab/sc_linac_physics/commit/6f1f49cc85715f3a96d9e7b29a8e46de99fe8130))

### Refactoring

- **sim**: Use CLI commands instead of direct script paths
  ([#136](https://github.com/slaclab/sc_linac_physics/pull/136),
  [`6f1f49c`](https://github.com/slaclab/sc_linac_physics/commit/6f1f49cc85715f3a96d9e7b29a8e46de99fe8130))

### Breaking Changes

- **cli**: Script names have changed from sc-linac-* to sc-* format. Update any automation or
  documentation that references the old command names."


## v1.4.4 (2025-10-22)

### Bug Fixes

- Include CSV files in package distribution
  ([#133](https://github.com/slaclab/sc_linac_physics/pull/133),
  [`c2228ee`](https://github.com/slaclab/sc_linac_physics/commit/c2228ee8715439d007688b9c926affee100c6088))

- Include nested display files in package data
  ([#133](https://github.com/slaclab/sc_linac_physics/pull/133),
  [`c2228ee`](https://github.com/slaclab/sc_linac_physics/commit/c2228ee8715439d007688b9c926affee100c6088))


## v1.4.3 (2025-10-22)

### Bug Fixes

- Include CSV files in package distribution
  ([#132](https://github.com/slaclab/sc_linac_physics/pull/132),
  [`f2dd422`](https://github.com/slaclab/sc_linac_physics/commit/f2dd422dbb2f81489d37bd95d1be63d674efc410))


## v1.4.2 (2025-10-22)

### Refactoring

- **cli**: Auto-discover launchers with decorators
  ([#131](https://github.com/slaclab/sc_linac_physics/pull/131),
  [`1057aca`](https://github.com/slaclab/sc_linac_physics/commit/1057aca637ab2f46d36d39cf6bbae7e12510f26c))

- **tests**: Improve CLI test structure and organization
  ([#131](https://github.com/slaclab/sc_linac_physics/pull/131),
  [`1057aca`](https://github.com/slaclab/sc_linac_physics/commit/1057aca637ab2f46d36d39cf6bbae7e12510f26c))


## v1.4.1 (2025-10-21)

### Refactoring

- Consolidate imports to use local linac_utils
  ([#130](https://github.com/slaclab/sc_linac_physics/pull/130),
  [`11ad3c8`](https://github.com/slaclab/sc_linac_physics/commit/11ad3c8a656f604425ef92b42e0063a175811b44))


## v1.4.0 (2025-10-20)

### Bug Fixes

- Use property setter for chirp frequency assignment
  ([#129](https://github.com/slaclab/sc_linac_physics/pull/129),
  [`1bc129f`](https://github.com/slaclab/sc_linac_physics/commit/1bc129fa2513cb1144973e39b463dacc592c9ce4))

### Chores

- Resolved linting errors from last push
  ([#129](https://github.com/slaclab/sc_linac_physics/pull/129),
  [`1bc129f`](https://github.com/slaclab/sc_linac_physics/commit/1bc129fa2513cb1144973e39b463dacc592c9ce4))

### Features

- Simplify cavity tuning with chirp preset button
  ([#129](https://github.com/slaclab/sc_linac_physics/pull/129),
  [`1bc129f`](https://github.com/slaclab/sc_linac_physics/commit/1bc129fa2513cb1144973e39b463dacc592c9ce4))


## v1.3.0 (2025-10-17)

### Code Style

- Apply black formatting ([#128](https://github.com/slaclab/sc_linac_physics/pull/128),
  [`2335d55`](https://github.com/slaclab/sc_linac_physics/commit/2335d555b76e02d4c753af65baf661eaab050615))

- Reformat with black line-length=80 ([#128](https://github.com/slaclab/sc_linac_physics/pull/128),
  [`2335d55`](https://github.com/slaclab/sc_linac_physics/commit/2335d555b76e02d4c753af65baf661eaab050615))

### Features

- **cli**: Add microphonics application launcher
  ([#127](https://github.com/slaclab/sc_linac_physics/pull/127),
  [`9da8e8e`](https://github.com/slaclab/sc_linac_physics/commit/9da8e8e2604b0fe6a9673eb79594b9568e5995b1))


## v1.2.0 (2025-10-16)

### Bug Fixes

- **microphonics**: Correct variable shadowing in config panel
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

### Documentation

- **readme**: Add CLI usage documentation and examples
  ([`027946f`](https://github.com/slaclab/sc_linac_physics/commit/027946f9ff80f21c73c885a0c957252664cd0467))

### Features

- **tests**: Add TimeSeriesPlot test suite with Python 3.13 compatibility
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

### Refactoring

- **microphonics**: Move application to src layout
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

### Testing

- **async**: Add AsyncDataManager test suite (49/49 passing)
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

- **microphonics**: Add DataAcquisitionManager test suite
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

- **microphonics**: Add file_parser unit tests
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

- **microphonics**: Add main window test coverage
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

- **plots**: Add comprehensive PlotPanel test suite (45/45 passing)
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))

- **plots**: Add comprehensive SpectrogramPlot test suite
  ([#126](https://github.com/slaclab/sc_linac_physics/pull/126),
  [`de18c2f`](https://github.com/slaclab/sc_linac_physics/commit/de18c2f4e11d4e9d90bb2583404255a4543e2316))


## v1.1.0 (2025-10-14)

### Features

- Add CLI launchers for PyDM displays and applications
  ([#125](https://github.com/slaclab/sc_linac_physics/pull/125),
  [`8afe31c`](https://github.com/slaclab/sc_linac_physics/commit/8afe31c3b5aab85d65e0cad6d7687bfcdb96599f))

### Testing

- **cli**: Add comprehensive test suite for CLI module
  ([#125](https://github.com/slaclab/sc_linac_physics/pull/125),
  [`8afe31c`](https://github.com/slaclab/sc_linac_physics/commit/8afe31c3b5aab85d65e0cad6d7687bfcdb96599f))


## v1.0.0 (2025-10-14)

### Bug Fixes

- Resolve flake8 linting error from last push
  ([`d0c3bfa`](https://github.com/slaclab/sc_linac_physics/commit/d0c3bfa2f59d370ec6d2e64626d7ce46820136aa))

- **auto-setup**: Improve abort handling in cavity characterization
  ([#121](https://github.com/slaclab/sc_linac_physics/pull/121),
  [`51cbafc`](https://github.com/slaclab/sc_linac_physics/commit/51cbafcae9d702f7a7228774608ccac1aadf7661))

### Build System

- Adding pytest-asyncio to toml ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Setup semantic-release with version tracking
  ([#124](https://github.com/slaclab/sc_linac_physics/pull/124),
  [`e512cc7`](https://github.com/slaclab/sc_linac_physics/commit/e512cc7c661d73d0f935a1b6bed422170952e130))

- Setup semantic-release with version tracking
  ([#123](https://github.com/slaclab/sc_linac_physics/pull/123),
  [`6ee82d4`](https://github.com/slaclab/sc_linac_physics/commit/6ee82d4fed5819777da19b2cf90efeaa3b5cea12))

- Setup semantic-release with version tracking
  ([#122](https://github.com/slaclab/sc_linac_physics/pull/122),
  [`eda506e`](https://github.com/slaclab/sc_linac_physics/commit/eda506ea0d0e0ccfbd09027773815c7a1fdda929))

- **release**: Configure semantic-release in pyproject and add GitHub Actions release workflow
  ([#116](https://github.com/slaclab/sc_linac_physics/pull/116),
  [`810f4a8`](https://github.com/slaclab/sc_linac_physics/commit/810f4a87b26832ec13e3fe036243f4b3d2bfe6a0))

### Chores

- Added a change to make_rainbow function in qt.py to prevent duplicate color
  ([`d0c3bfa`](https://github.com/slaclab/sc_linac_physics/commit/d0c3bfa2f59d370ec6d2e64626d7ce46820136aa))

- Added q0 gui tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Cleaning up q0 test file ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Fixing flake8 errors ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Fixing flake8 issues ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Patching sel cavity tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Patching tests that were leaking files
  ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Pushing changes to qt.py in utils file
  ([#120](https://github.com/slaclab/sc_linac_physics/pull/120),
  [`13a9b0c`](https://github.com/slaclab/sc_linac_physics/commit/13a9b0ca5a42e12a87f5422fb66335c5c1b39519))

- Refactored quench worker file ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Remove commit-parser flag from pyproject.toml
  ([`bb7d986`](https://github.com/slaclab/sc_linac_physics/commit/bb7d9862a3ed6227fcc06a2f69b0976a706d5eae))

- Remove unnecessary statement ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Trying to patch quench gui tests so that they pass locally
  ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

### Code Style

- **tuning_gui**: Update detune and cold labels to same color
  ([`d0c3bfa`](https://github.com/slaclab/sc_linac_physics/commit/d0c3bfa2f59d370ec6d2e64626d7ce46820136aa))

### Continuous Integration

- Configure git credentials for semantic-release
  ([`1c31bed`](https://github.com/slaclab/sc_linac_physics/commit/1c31bed66a289420d9f6580c73a7a9e551b112ec))

- Improve release workflow with debug output
  ([#124](https://github.com/slaclab/sc_linac_physics/pull/124),
  [`e512cc7`](https://github.com/slaclab/sc_linac_physics/commit/e512cc7c661d73d0f935a1b6bed422170952e130))

- Improve release workflow with debug output
  ([#123](https://github.com/slaclab/sc_linac_physics/pull/123),
  [`6ee82d4`](https://github.com/slaclab/sc_linac_physics/commit/6ee82d4fed5819777da19b2cf90efeaa3b5cea12))

- Patch semantic-release verbose flags and run tests only on pull requests
  ([#124](https://github.com/slaclab/sc_linac_physics/pull/124),
  [`e512cc7`](https://github.com/slaclab/sc_linac_physics/commit/e512cc7c661d73d0f935a1b6bed422170952e130))

- Remove invalid verbose flags from semantic-release
  ([`aafff28`](https://github.com/slaclab/sc_linac_physics/commit/aafff28aa035fd894223bf16d7d888c782bd8b2c))

- Run tests only on pull requests ([#124](https://github.com/slaclab/sc_linac_physics/pull/124),
  [`e512cc7`](https://github.com/slaclab/sc_linac_physics/commit/e512cc7c661d73d0f935a1b6bed422170952e130))

- Simplify semantic-release verbose flags
  ([#124](https://github.com/slaclab/sc_linac_physics/pull/124),
  [`e512cc7`](https://github.com/slaclab/sc_linac_physics/commit/e512cc7c661d73d0f935a1b6bed422170952e130))

- Use PAT for semantic-release to bypass branch protection
  ([`278e10d`](https://github.com/slaclab/sc_linac_physics/commit/278e10d9f34684d36907f21a1d93a57a04c24be4))

### Documentation

- Patching links in readme ([#116](https://github.com/slaclab/sc_linac_physics/pull/116),
  [`810f4a8`](https://github.com/slaclab/sc_linac_physics/commit/810f4a87b26832ec13e3fe036243f4b3d2bfe6a0))

- Reformatting badges in readme ([#116](https://github.com/slaclab/sc_linac_physics/pull/116),
  [`810f4a8`](https://github.com/slaclab/sc_linac_physics/commit/810f4a87b26832ec13e3fe036243f4b3d2bfe6a0))

- Update README ([#116](https://github.com/slaclab/sc_linac_physics/pull/116),
  [`810f4a8`](https://github.com/slaclab/sc_linac_physics/commit/810f4a87b26832ec13e3fe036243f4b3d2bfe6a0))

### Testing

- Adding another logic branch ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding auto setup service tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding cavity service tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding q0 rf measurement tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding q0_utils tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding q0cryomodule tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding sc linac physics service tests
  ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding tests for q0_gui_utils.py ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Adding tuner simulation tests ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Reintroducing minimum required test coverage
  ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Speeding up sc linac physics service tests
  ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- Trying to patch 'too many open files' error
  ([#117](https://github.com/slaclab/sc_linac_physics/pull/117),
  [`0010a39`](https://github.com/slaclab/sc_linac_physics/commit/0010a399fa6411ede364196c163fc42a066deb11))

- **abort**: Fix shut_down_with_running_status to verify skip behavior
  ([#121](https://github.com/slaclab/sc_linac_physics/pull/121),
  [`51cbafc`](https://github.com/slaclab/sc_linac_physics/commit/51cbafcae9d702f7a7228774608ccac1aadf7661))

- **auto-setup**: Align test assertions with actual cavity behavior
  ([#121](https://github.com/slaclab/sc_linac_physics/pull/121),
  [`51cbafc`](https://github.com/slaclab/sc_linac_physics/commit/51cbafcae9d702f7a7228774608ccac1aadf7661))


## v0.1.0 (2025-09-23)

- Initial Release
