# Use Case: GEDI L4A Subset

Authors: Alex Mandel and Chuck Daniels

- [CMR Query](#cmr-query)
- [Download](#download)
- [Subset](#subset)
  - [Process](#process)
  - [Notes](#notes)
  - [Questions](#questions)
  - [Timing](#timing)
- [Combine](#combine)
  - [Process](#process-1)
  - [Timing](#timing-1)
  - [DPS Jobs](#dps-jobs)

## CMR Query

[setup.ipynb](setup.ipynb)

- 1009 granules matched a BBOX search of CMR (Initially discovered MAAP CMR had
  the collection BBOX for every granule, now fixed)
- Tried Polygon search but couldn't get it to work. Would be good to fix as some
  granules do not actually have data in the AOI polygon of Gabon, but BBOX of
  Gabon interesects with BBOX of Granule.
- `maap-py` has some performance issues. Returning search results for the 1009
  granules for Gabon:

  ```plain
  find_granules (/tmp/ipykernel_1703/2505500122.py:1):
    84.242 seconds
  ```

## Download

[setup.ipynb](setup.ipynb)

- Took 14.517 seconds to download a file of size 371,226,513 bytes (~25 MB/s)

## Subset

[subset.ipynb](subset.ipynb)

### Process

1. Open H5 file with python
2. Loop over the BEAM groups, extracting preselected attributes (keys)
3. Convert lists into Pandas dataframe
4. Convert Pandas into Geopandas
5. Apply spatial filter

### Notes

- GeoJSON files were very large, switched to FileGeoBuffer format. Ideally
  partial spatial subsets can be read from this format (has a spatial index),
  otherwise it applies some compression and is relatively fast to read back in
  GeoPandas.
- Need to skip writing granules with no matching data for the AOI
- Subsetting needs to also subset attributes to include, otherwise the files are
  extremely large still.
- TODO: Spatial filter applies before extracting data (2) could cut down on time
  and memory requirement significantly.
- Consider alternative read methods, Xarray, direct from S3 without download.

### Questions

1. For several attributes there is a numbered version that applies to each BEAM?
   Still trying to understand what these are and if we need to keep them. Seems
   there are several alogrithms `Predicted AGBD using algorithm setting N` are
   we ok with just the "optimal"?

   ```plain
   'agbd_a1'
   'agbd_a10'
   'agbd_a2'
   'agbd_a3'
   'agbd_a4'
   'agbd_a5'
   'agbd_a6'
   ```

### Timing

```plain
  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    46.730 seconds

Subset points (64209, 8)

  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    8.495 seconds

All points (1338484, 8)
Subset points (24866, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    27.611 seconds


  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    3.922 seconds

All points (609748, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    5.021 seconds

Subset points (0, 8)
All points (395012, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    13.178 seconds

Subset points (1846, 8)

  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    1.736 seconds

All points (1338733, 8)
Subset points (14567, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    33.706 seconds


  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    2.952 seconds

All points (1037928, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    33.965 seconds

Subset points (39284, 8)

  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    5.866 seconds

All points (515477, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    29.621 seconds

Subset points (37779, 8)

  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    5.283 seconds

All points (522780, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    22.457 seconds

Subset points (0, 8)
All points (1045559, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    15.608 seconds

Subset points (0, 8)
All points (912543, 8)
Subset points (66053, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    48.031 seconds


  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    9.183 seconds

All points (508165, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    46.880 seconds

Subset points (58430, 8)

  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    7.914 seconds

All points (1338521, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    33.797 seconds

Subset points (23275, 8)

  write_subset (/tmp/ipykernel_12978/815998746.py:82):
    3.834 seconds

All points (1054709, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    11.281 seconds

Subset points (0, 8)
All points (372346, 8)

  subset_gedi_granule (/tmp/ipykernel_12978/815998746.py:1):
    6.934 seconds

Subset points (0, 8)
```

## Combine

[combine.ipynb](combine.ipynb)

### Process

1. Find all FlatGeobuf files in a directory
1. Read and append FlatGeobuf files into single GeoDataFrame
1. Write combined result to new FlatGeobuf file

After all FlatGeobuf files were generated (467 of them), using the steps above
caused the ADE to crash, so instead, the following steps were taken:

1. Find all FlatGeobuf files in a directory
1. For each FlatGeobuf file, write/append it in `GPKG` format to a combined file

This resulted in a 2.5G output file.

### Timing

Combining 13 subsets resulted in a GeoDataFrame with 330309 rows.  Reading,
appending, and writing to combined FlatGeobuf file:

```plain
combine_subsets (/tmp/ipykernel_1618/2207665546.py:1):
  17.696 seconds
```

Combined file size: 82,798,032 bytes

Combining all 467 `.fgb` files into a single `.gpkg` file (2.5G) took 4360
seconds (~73 minutes).

### DPS Jobs

Running a DPS job to subset the entirety of Equatorial Guinea (GNQ_ADM0) using
the default queue took 9 hours, but only 2 CPUs were available.  The resulting
subset file is 1.1GB, combined from 266 granule files (~0.48 granule/min).

It is unclear what the "default" queue is, but it provides 8GB of memory.

- JobID: `bfb7e574-600a-4eaa-b5f6-3ab4bd477a5c`
- aoi: <https://maap-ops-workspace.s3.amazonaws.com/shared/dschuck/iso3/GNQ-ADM0.geojson>
- limit: 2000

```plain
machine_type          t3a.large
architecture          x86_64
machine_memory_size   7.70 GB
directory_size        85449449472
operating_system      CentOS
job_start_time        2022-04-16T02:12:03.110101Z
job_end_time          2022-04-16T11:12:38.705999Z
job_duration_seconds  32435.595898
```

Choosing the 32GB queue, provided 4 CPUs, so the execution time was half of the
above, at roughly 4.5 hours (~0.98 granule/min):

- JobID: `36f902ca-54fe-4ca1-a6d1-8ebb97e65021`
- aoi: <https://maap-ops-workspace.s3.amazonaws.com/shared/dschuck/iso3/GNQ-ADM0.geojson>
- limit: 2000

```plain
machine_type          r5a.xlarge
architecture          x86_64
machine_memory_size   31.00 GB
directory_size        85432406016
operating_system      CentOS
job_start_time        2022-04-18T21:42:35.633404Z
job_end_time          2022-04-19T02:12:05.678511Z
job_duration_seconds  16170.045107
```

Choosing the 8GB queue, provided 16 CPUs, reducing the execution time to a bit
under 1 hour (approx. 56m, or ~4.8 granules/min), which is _better_ than
linear scalability relative to the previous 2 jobs:

- JobID: `f75b5e3c-65f3-42a7-9cfb-a804fa25b827`
- aoi: <https://maap-ops-workspace.s3.amazonaws.com/shared/dschuck/iso3/GNQ-ADM0.geojson>
- limit: 2000

```plain
machine_type          c5.4xlarge
architecture          x86_64
machine_memory_size   30.36 GB
directory_size        1511387136
operating_system      CentOS
job_start_time        2022-04-26T01:31:15.609852Z
job_end_time          2022-04-26T02:27:35.695733Z
job_duration_seconds  3380.085881
```

This run indicated that 269 granule files were subsetted, not 266, indicating
that perhaps a few new granules have been ingested since the previous jobs were
executed.
