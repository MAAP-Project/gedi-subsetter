# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## Unreleased

### Added

- [#57](https://github.com/MAAP-Project/gedi-subsetter/issues/57) Users may
  choose to profile their jobs by specifying command-line options for the
  `scalene` profiling tool. See `docs/MAAP_USAGE.md` for more information.

## 0.6.2 (2023-12-05)

### Fixed

- Updated to use v3.1.3 of maap-py in environment-maappy.yml. Previous versions
  of maap-py were using the deprecated MAAP Query Service API endpoint.

## 0.6.1 (2023-09-28)

### Fixed

- [#49](https://github.com/MAAP-Project/gedi-subsetter/issues/49) Remove all API
  URLs that contain ops as they have now been retired (e.g.,
  api.ops.maap-project.org).

## 0.6.0 (2023-06-02)

### Fixed

- [#40](https://github.com/MAAP-Project/gedi-subsetter/issues/40) All geometries
  in an AOI (area of interest) file are now used for granule selection and
  subsetting.  Previously, only the first geometry was used, resulting in a much
  smaller subset than expected, in cases where the AOI contains multiple
  geometries.
- [#41](https://github.com/MAAP-Project/gedi-subsetter/issues/41) Granules
  without a download link in their metadata are now skipped.  Previously,
  encountering such granules would cause a job failure, due to being unable to
  download a file without having a download link.
- [#42](https://github.com/MAAP-Project/gedi-subsetter/issues/42) Granules with
  metadata containing multiple boundaries within the horizontal spatial domain
  are now supported.  In such cases, a single boundary is obtained by taking the
  union of the individual boundaries.  If the result intersects with the AOI,
  then the granule is included in the subset.  Previously, although rare, such
  granule metadata would cause a job failure.

### Changed

- Upgraded Python to version 3.11 to take advantage of the addition of
  [fine-grained error locations in tracebacks] to help with debugging errors.
- The `beam` column is no longer automatically included in the output file.  If
  you wish to include the `beam` column, you must specify it explicitly in the
  `columns` input.
- The default value for `limit` was reduced from 10000 to 1000.  The AOI for
  most subsetting operations are likely to incur a request for well under 1000
  granules for downloading, so a larger default value might only lead to longer
  CMR query times.

### Added

- [#38](https://github.com/MAAP-Project/gedi-subsetter/issues/38): Temporal
  filtering is now supported, such that specifying a temporal range will
  limit the granules downloaded from the CMR, pulling only granules obtained
  within the specified range.  See `docs/MAAP_USAGE.md` for more information.
- Added an input parameter named `output` to allow user to specify the name of
  the output file, rather than hard-code the name to `gedi-subset.gpkg`.  See
  `docs/MAAP_USAGE.md` for more information.

## 0.5.0 (2023-04-11)

### Changed

- [#36](https://github.com/MAAP-Project/gedi-subsetter/issues/36): All CMR
  queries now use the NASA CMR, because the MAAP CMR is being retired.  If you
  wish to query the MAAP CMR until it is taken down, you may still use an
  earlier version of this algorithm (ideally, 0.4.0).

## 0.4.0 (2022-11-14)

### Added

- [#6](https://github.com/MAAP-Project/gedi-subsetter/issues/6): Allow user to
  specify which BEAMs to subset

## 0.3.0 (2022-11-10)

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

## 0.2.7 (2022-10-18)

### Added

- Promoted the GEDI Subsetting algorithm to this repository from the
  [MAAP-Project/maap-documentation-examples] repository.  This `0.2.7` version
  replicates the `gedi-subset-0.2.7` version released from that repository.

[fine-grained error locations in tracebacks]:
  https://docs.python.org/3/whatsnew/3.11.html#whatsnew311-pep657
[Keep a Changelog]:
    https://keepachangelog.com/en/1.0.0/
[Semantic Versioning]:
    https://semver.org/spec/v2.0.0.html
[MAAP-Project/maap-documentation-examples]:
    https://github.com/MAAP-Project/maap-documentation-examples
