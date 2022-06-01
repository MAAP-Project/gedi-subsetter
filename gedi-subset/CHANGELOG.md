# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to a
variation of [Semantic Versioning], with the following difference: each version
is prefixed with `gedi-subset-` (e.g., `gedi-subset-0.1.0`) to allow for
distinct lines of versioning of independent work in sibling directories.

## [0.1.0] - 2022-05-26

### Added

- Allow users to subset GEDI L4A data (HDF5) falling within an AOI (GeoJSON),
  producing a single output file (GPKG)

[Keep a Changelog]:
    https://keepachangelog.com/en/1.0.0/
[Semantic Versioning]:
    https://semver.org/spec/v2.0.0.html