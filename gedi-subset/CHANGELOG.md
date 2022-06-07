# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to a
variation of [Semantic Versioning], with the following difference: each version
is prefixed with `gedi-subset-` (e.g., `gedi-subset-0.1.0`) to allow for
distinct lines of versioning of independent work in sibling directories.

## [gedi-subset-0.2.1] - 2022-06-07

Hotfix replacement for `gedi-subset-0.2.0`.

### Fixed

- Resolved the following runtime error during DPS job execution that occurs with
  version `gedi-subset-0.2.0`:

  ```plain
  ImportError: Missing optional dependency 'pyarrow.parquet'.
  ```

  This appears to be due to a recent release of one or more unpinned transitive
  dependencies.  This was resolved with a `conda` lock file.

## [gedi-subset-0.2.0] - 2022-06-01 [YANKED]

## Added

- Added inputs `columns` and `query` to refine filtering/subsetting.  See
  `gedi-subset/README.md` for details.

## Changed

- Improved performance of subsetting/filtering logic, resulting in ~5x speedup.

## [gedi-subset-0.1.0] - 2022-06-01

### Added

- Allow users to subset GEDI L4A data (HDF5) falling within an AOI (GeoJSON),
  producing a single output file (GPKG)

[Keep a Changelog]:
    https://keepachangelog.com/en/1.0.0/
[Semantic Versioning]:
    https://semver.org/spec/v2.0.0.html
