# CHANGELOG

<!-- version list -->

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
