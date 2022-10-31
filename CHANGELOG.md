# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [0.3.0] - 2022-10-31

### Fixed

- [#5](https://github.com/MAAP-Project/gedi-subsetter/issues/5): Nested
  variables must now be specified by path relative to each BEAM group.  This not
  only avoids ambiguity for variables of the same name (but different paths),
  but also makes a variable's location explicit.
- [#17](https://github.com/MAAP-Project/gedi-subsetter/issues/17): Granule files
  that cannot be successfully read are skipped, rather than causing job failure.
  Offending files are retained to facilitate analysis.

### Added

- [#1](https://github.com/MAAP-Project/gedi-subsetter/issues/1) User must
  specify values for `lat` and `lon` as inputs, allowing the user to choose
  which lat/lon datasets are used.
- [#2](https://github.com/MAAP-Project/gedi-subsetter/issues/2): User must
  specify `doi` as an input, now allowing subsetting of L2A as well as L4A data.
- [#7](https://github.com/MAAP-Project/gedi-subsetter/issues/7): Columns from 2D
  variables can be selected.
- [#8](https://github.com/MAAP-Project/gedi-subsetter/issues/8): Specifying a
  query is now optional, to allow selecting all rows for specified columns.

## [0.2.7] - 2022-10-18

### Added

- Promoted the GEDI Subsetting algorithm to this repository from the
  [MAAP-Project/maap-documentation-examples] repository.  This `0.2.7` version
  replicates the `gedi-subset-0.2.7` version released from that repository.

[Keep a Changelog]:
    https://keepachangelog.com/en/1.0.0/
[Semantic Versioning]:
    https://semver.org/spec/v2.0.0.html
[MAAP-Project/maap-documentation-examples]:
    https://github.com/MAAP-Project/maap-documentation-examples
