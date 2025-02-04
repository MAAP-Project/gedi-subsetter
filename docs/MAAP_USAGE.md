# GEDI Subsetting

- [Algorithm Outline](#algorithm-outline)
- [Algorithm Inputs](#algorithm-inputs)
  - [Specifying an AOI](#specifying-an-aoi)
  - [Specifying a DOI](#specifying-a-doi)
    - [L1B](#l1b)
    - [L2A](#l2a)
    - [L2B](#l2b)
    - [L4A](#l4a)
    - [L4C](#l4c)
- [Running a GEDI Subsetting DPS Job](#running-a-gedi-subsetting-dps-job)
  - [Submitting a DPS Job](#submitting-a-dps-job)
  - [Checking the DPS Job Status](#checking-the-dps-job-status)
  - [Getting the DPS Job Results](#getting-the-dps-job-results)
- [Getting the GeoJSON URL for a geoBoundary](#getting-the-geojson-url-for-a-geoboundary)
- [Citations](#citations)

## Algorithm Outline

At a high level, the GEDI subsetting algorithm does the following:

- Queries the MAAP CMR for granules from a specified GEDI collection that
  intersect a specified Area of Interest (AOI) (as a GeoJSON file).  This is
  limited to GEDI collections granule data files are in HDF5 format, which are
  L1B, L2A, L2B, L4A, and L4C.
- For each granule within the specified AOI, downloads its HDF5 (`.h5`) file.
- Subsets each data file by selecting specified datasets within the file and
  limiting data to values that match a specified query condition.
- Combines all subset files into a single output file named `gedi_subset.gpkg`,
  in GeoPackage format, readable with `geopandas` as a `GeoDataFrame`.

## Algorithm Inputs

To run a GEDI subsetting DPS job, there are a few required inputs and several
optional inputs:

- `aoi` (_required_): URL to a GeoJSON file representing your area of interest
  (see [Specifying an AOI](#specifying-an-aoi)).  This may contain multiple
  geometries, all of which will be used.

- `columns` (_required_): One or more column names, separated by commas, to
  include in the output file.  These names correspond to the _datasets_ (which
  might also be referred to as _variables_ or _layers_ in the DOI documentation)
  within the data files, and vary from collection to collection.  Consult the
  documentation for each collection for a list of datasets available per
  collection (see [Specifying a DOI](#specifying-a-doi) for documentation
  links).

  In addition to the specified columns, the output file will also include a
  `filename` (`str`) column that includes the name of the original `h5` file.

  **IMPORTANT:** To specify nested datasets (i.e., datasets _not_ at the top of
  a BEAM), you may use a path containing forward slashes (`/`) that is relative
  to the BEAM it appears within.  For example, if a BEAM contains a
  `geolocation` group, and within that group is a dataset named
  `sensitivity_a2`, then you would refer to that nested dataset as
  `geolocation/sensitivity_a2`.

  > _Changed in version 0.6.0_: The `beam` column is no longer automatically
  > included.  If you wish to include the `beam` column, you must specify it
  > explicitly in this `columns` value.

- `query` (_optional_; default: no query, select all rows): Query expression for
  subsetting the rows in the output file.  This expression selects rows of data
  for which the expression is true.  Again, names in the expression are dataset
  (variable/layer) names.  For example: `quality_flag == 1`.

  **NOTE:** To combine multiple expressions, you may use the `and` and `or`
  boolean operators.

  Examples:

  ```plain
  quality_flag == 1 and sensitivity > 0.95
  (l2a_quality_flag == 1 or l2b_quality_flag == 1) and sensitivity > 0.95
  ```

  **IMPORTANT:** To specify nested datasets (i.e., datasets _not_ at the top of
  a BEAM), you may use a relative path, as described above for column names, but
  you must surround such nested path names with _backticks_ (`` ` ``).  For
  example:

  ```plain
  quality_flag == 1 and `geolocation/sensitivity_a2` > 0.95
  ```

- `limit` (_optional_; default: 100000): Maximum number of GEDI granule data
  files to subset, among those that intersect the specified AOI's bounding box,
  and fall within the specified temporal range (if supplied).  If there are more
  granules within the spatio-temporal range, only the first `limit` number of
  granules obtained from the corresponding CMR search are used.

  > _Changed in version 0.6.0_: The default value was reduced from 10000 to 1000.
  > The AOI for most subsetting operations are likely to incur a request for well
  > under 1000 granules for downloading, so a larger default value might only lead
  > to longer CMR query times.

  > _Changed in version 0.8.0_: The default value was increased from 1000 to
  > 100000 to avoid confusion in cases where a user does _not_ specify a limit,
  > expecting to subset _all_ granules within the specified spatio-temporal
  > range, but instead subsetting no more than the default limit of 1000, thus
  > obtaining an unexpectedly incomplete result.  This new limit should
  > effectively behave as if it were unlimited because all supported GEDI
  > collections have fewer granules than this default limit.

- `doi` (_required_): [Digital Object Identifier] (DOI) of the GEDI collection
  to subset, or a logical name representing such a DOI (see
  [Specifying a DOI](#specifying-a-doi))

  > _Added in version 0.3.0_

- `lat` (_required_): _Name_ of the dataset used for latitude values.

  > _Added in version 0.3.0_

- `lon` (_required_): _Name_ of the dataset used for longitude values.

  > _Added in version 0.3.0_

- `beams` (_optional_; default: `all`): Which beams to include in the subset.
  If supplied, must be one of logical names `all`, `coverage`, or `power`, _OR_
  a comma-separated list of specific beam names, with or without the `BEAM`
  prefix (e.g., `BEAM0000,BEAM0001` or `0000,0001`)

  > _Added in version 0.4.0_

- `temporal` (_optional_; default: full temporal range available): Temporal
  range to subset.  You may specify either a closed range, with start and end
  dates, or a half-open range, with either a start date or an end date.  For
  full details on the valid formats, see the NASA CMR's documentation on
  [temporal range searches](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#temporal-range-searches).

  > _Added in version 0.6.0_

- `output` (_optional_): Name to use for the output file.  This may include a
  path, which will be relative to the standard DPS output directory for a job.
  **Default:** when a value is not supplied, the output file will be named the
  same as the name of the AOI file, but with a suffix of `"_subset.gpkg"`
  (GeoPackage format).

  When a value is supplied, it must include a file extension in order to infer
  the output format.  Supported formats inferred from file extensions are as
  follows:

  - GPKG (GeoPackage): `.gpkg`
  - (Geo)Parquet: `.parquet`
  - FlatGeobuf: `.fgb`

  > _Added in version 0.6.0_

  > _Changed in version 0.10.0_: Output formats other than GeoPackage (`.gpkg`)
  are now supported.

- `fsspec_kwargs` (_optional_; default:
  `'{"default_cache_type": "all", "default_block_size": 8388608`): JSON object
  representing keyword arguments to pass to the [fsspec.url_to_fs] function when
  reading granule files.  **ADVANCED:** Normal usage should leave this input
  blank, meaning that the default value will be used, which prioritizes
  algorithm speed over minimizing data transfer volume.

  > _Added in version 0.8.0_

- `processes` (_optional_; default: number of available CPUs): Number of
  processes to use for parallel processing.  **ADVANCED:** Normal usage should
  leave this input blank, meaning that the algorithm will use all available
  CPUs.  This input is intended only for performance profiling purposes.

  > _Added in version 0.8.0_

- `scalene_args` (_optional_; default: none): Arguments to pass to [Scalene] for
  performance profiling.  **ADVANCED:** Normal usage should leave this argument
  blank, meaning that Scalene will _not_ be used.  This input is intended only
  for performance profiling purposes.

  When this input is supplied, the algorithm will be run via the `scalene`
  command for collecting performance metrics (i.e.  CPU and RAM usage), and the
  value of this input will be passed as arguments to the command.  For a list of
  available command-line options, see
  <https://github.com/plasma-umass/scalene?tab=readme-ov-file#scalene>.

  By default, the name of the profile output file is `profile.html` (placed in
  your job's output folder).  If you specify the `--json` flag, it will be named
  `profile.json`.  If you specify the `--cli` flag, it will be named
  `profile.txt`.

  If you want to use all of Scalene's default values (i.e.  not specify any
  override values), you cannot leave this input blank, otherwise Scalene will
  not be used at all (as mentioned above).  In this case, you must supply _some_
  value for this input, so the simplest valid Scalene option is `--on`.

  **Note:** Since no browser is available in DPS, when any value is supplied for
  this input, the `--no-browser` option will be included to prevent Scalene from
  attempting to open a browser.

  > _Added in version 0.7.0_

  > _Changed in version 0.8.0_: Specifying the `--json` flag changes the name of
  > the profile output file to `profile.json` and specifying `--cli` changes it
  > to `profile.txt`.

### Specifying an AOI

If your AOI is a publicly available geoBoundary, see
[Getting the GeoJSON URL for a geoBoundary](#getting-the-geojson-url-for-a-geoboundary)
for details on obtaining it's URL.  In this case, that is the URL you must
supply for the `aoi` input.

Alternatively, you can make your own GeoJSON file for your AOI and place it
within your public bucket within the ADE.  Based upon where you place your
GeoJSON file, you can construct a URL to specify for a job's `aoi` input.

Specifically, you should place your GeoJSON file at a location of the following
form within the ADE (where `path/to/aio.geojson` can be any path and filename
for your AOI):

```plain
/projects/my-public-bucket/path/to/aoi.geojson
--------------------------
```

You would then supply the following URL as the `aoi` input value when running
this algorithm as a DPS job, where `<USERNAME>` is your ADE username:

```plain
https://maap-ops-workspace.s3.amazonaws.com/shared/<USERNAME>/path/to/aoi.geojson
-------------------------------------------------------------
  |
  +-- Replace "/projects/my-public-bucket" with this URL prefix
```

### Specifying a DOI

To avoid the need to remember or lookup a DOI for a GEDI collection, you may
supply one of the following "logical" names as the value of the `doi` input
(case is ignored):

|Logical name|Corresponding DOI
|:-----------|:----------------
|L1B         |[10.5067/GEDI/GEDI01_B.002](https://doi.org/10.5067/GEDI/GEDI01_B.002)
|L2A         |[10.5067/GEDI/GEDI02_A.002](https://doi.org/10.5067/GEDI/GEDI02_A.002)
|L2B         |[10.5067/GEDI/GEDI02_B.002](https://doi.org/10.5067/GEDI/GEDI02_B.002)
|L4A         |[10.3334/ORNLDAAC/2056](https://doi.org/10.3334/ORNLDAAC/2056)
|L4C (_Added in version 0.9.0_) |[10.3334/ORNLDAAC/2338](https://doi.org/10.3334/ORNLDAAC/2338)

If, however, a new version of a collection is published, the new version will
have a different DOI assigned, and the old version of the collection will likely
be removed from the CMR.  In this case, the job will fail because it will be
unable to obtain the collection data via the CMR.

Therefore, to avoid being blocked by this, you may specify a DOI name as the
value for the `doi` input field until this algorithm is updated to associate the
new DOI with the logical name.

When supplying a DOI name (rather than a logical name), the job will fail for
any of the following reasons:

- There is no collection in the MAAP CMR corresponding to the DOI
- There is such a collection in the MAAP CMR, but it is not a GEDI collection
- The collection is a GEDI collection, but its data format is not HDF5

Here are some _example_ input values per DOI, where ellipses should be replaced
with appropriate values:

#### L1B

```python
inputs = dict(
   aoi=...,
   doi="L1B",  # or a specific DOI
   lat="geolocation/latitude_bin0",
   lon="geolocation/longitude_bin0",
   columns=...,
   query=...,
)
```

#### L2A

```python
inputs = dict(
   aoi=...,
   doi="L2A",  # or a specific DOI
   lat="lat_lowestmode",  # or "lat_highestreturn"
   lon="lon_lowestmode",  # or "lon_highestreturn"
   columns="rh50,rh98",
   query="quality_flag == 1 and sensitivity > 0.95",
)
```

#### L2B

```python
inputs = dict(
   aoi=...,
   doi="L2B",  # or a specific DOI
   lat="geolocation/lat_lowestmode", # or "geolocation/lat_highestreturn"
   lon="geolocation/lon_lowestmode", # or "geolocation/lon_highestreturn"
   columns="rh100",
   query="l2a_quality_flag == 1 and l2b_quality_flag == 1 and sensitivity > 0.95",
)
```

#### L4A

```python
inputs = dict(
   aoi=...,
   doi="L4A",  # or a specific DOI
   lat="lat_lowestmode",
   lon="lon_lowestmode",
   columns="agbd, agbd_se, sensitivity, geolocation/sensitivity_a2",
   query="l2_quality_flag == 1 and l4_quality_flag == 1 and sensitivity > 0.95 and `geolocation/sensitivity_a2` > 0.95",
)
```

#### L4C

> _Added in version 0.9.0_

```python
inputs = dict(
   aoi=...,
   doi="L4C",  # or a specific DOI
   lat="lat_lowestmode",
   lon="lon_lowestmode",
   columns="wsci, sensitivity, geolocation/sensitivity_a2",
   query="l2_quality_flag == 1 and wsci_quality_flag == 1 and sensitivity > 0.95 and `geolocation/sensitivity_a2` > 0.95",
)
```

## Running a GEDI Subsetting DPS Job

### Submitting a DPS Job

The GEDI Subsetting DPS Job is named `gedi-subset`, and may be executed
from your ADE Workspace by opening the **Jobs** menu, choosing
the **View & Submit Jobs** menu option, and selecting `gedi-subset:<VERSION>`
from the dropdown.  You will be prompted for the inputs as described in the
previous section.

Alternatively, for greater control of your job configuration, you may use the
MAAP API from a Notebook (or a Python script), as follows:

```python
from maap.maap import MAAP

maap = MAAP(maap_host='api.maap-project.org')

# See "Algorithm Inputs" section as well as "Specifying a DOI"
inputs = dict(
   aoi="<AOI GeoJSON URL>"
   doi="<DOI>",
   lat="<LATITUDE>",
   lon="<LONGITUDE>",
   beams="<BEAMS>",
   columns="<COLUMNS>",
   query="<QUERY>",
   limit=0,  # 0 implies no limit to the number of granules downloaded
   temporal="<RANGE>",  # or exclude this input for unlimited temporal range
   output="<OUTPUT FILE>",
)

result = maap.submitJob(
    identifier="<DESCRIPTION>",
    algo_id="gedi-subset",
    version="<VERSION>",
    queue="maap-dps-worker-32gb",
    username="<USERNAME>",  # Your Earthdata Login username
    **inputs
)

job_id = result["job_id"]
job_id or result
```

### Checking the DPS Job Status

To check the status of your job via the ADE UI, open the **Jobs**
menu, choose **View & Submit Jobs**, and view the list of running jobs to see
their statuses.

Alternatively, to programmatically check the status of the submitted job, you
may run the following code.  If using a notebook, use a separate cell so you can
run it repeatedly until you get a status of either `'Succeeded'` or `'Failed'`:

```python
# Should evaluate to 'Accepted', 'Running', 'Succeeded', or 'Failed'
from maap.maap import MAAP
maap = MAAP(maap_host='api.maap-project.org')

maap.getJobStatus(job_id)
```

### Getting the DPS Job Results

Once the job status is either **Succeeded** or **Failed**, you may obtain the
job results either via the **View & Submit Jobs** page within the ADE or program-
matically via the MAAP API.

To obtain the results programmatically, you can use the following to see the
details.  Note the use of `print`, which is necessary within a Jupyter notebook
because the output may contain multiple lines.  Without wrapping everything in a
call to `print`, the output might be very hard to read:

```python
from maap.maap import MAAP
maap = MAAP(maap_host='api.maap-project.org')

maap.getJobResult(job_id)
```

If the jobs status is **Failed**, the job results should show failure details.

If the job status is **Succeeded**, the job results should show 2 URLs, with the
first URL of the following form:

```plain
http://.../<USERNAME>/dps_output/gedi-subset/<VERSION>/<DATETIME_PATH>
```

Based upon this URL, the `gedi_subset.gpkg` file generated by the job should be
available at the following path within the ADE:

```plain
~/my-private-bucket/dps_output/gedi-subset/<VERSION>/<DATETIME_PATH>/gedi_subset.gpkg
```

## Getting the GeoJSON URL for a geoBoundary

If your AOI is a geoBoundary (such as a country), you may obtain the URL for its
GeoJSON file from the [geoBoundaries] website, rather than constructing a custom
GeoJSON file.  To obtain the URL for the GeoJSON of an AOI, obtain the ISO3 code
and level for the AOI's geoBoundary from the website.

Once you know the ISO3 code and level, construct a [geoBoundaries API] URL
(this is _not_ the GeoJSON URL) of the following form, replacing `<ISO3>` and
`<LEVEL>` with appropriate values:

```plain
https://www.geoboundaries.org/api/current/gbOpen/<ISO3>/<LEVEL>/
```

For example, the ISO3 code for Gabon is GAB.  Therefore, the geoBoundaries API
URL for Gabon level 0 is
<https://www.geoboundaries.org/api/current/gbOpen/GAB/ADM0/>.

You may use the geoBoundaries API URL in various ways to obtain your AOI's
GeoJSON URL, such as one of the following:

- Use a browser to navigate to the API URL.  If your browser directly displays
  the result, locate the value of `"gjDownloadURL"`.  If your browser forces
  you to download the result, do so, and locate the value of `"gjDownloadURL"`
  within the downloaded file.  In either case, the value associated with
  `"gjDownloadURL"` is your AOI's GeoJSON URL.

- Alternatively, open a terminal window and run the following command,
  replacing `<API_URL>` appropriately.  The output should be the GeoJSON URL:

  ```sh
  curl -s <API_URL> | tr ',' '\n' | grep "gjDownloadURL.*gbOpen" | sed -E 's/.*"(https.+)"/\1/'
  ```

Continuing with the Gabon example, entering the geoBoundaries API URL for Gabon
(shown above) in a browser should result in the following (abridged) output
(either in the browser, or within a downloaded file):

```plain
{
  "boundaryID": "GAB-ADM0-25889322",
  "boundaryName": "Gabon",
  "boundaryISO": "GAB",
  ...
  "gjDownloadURL": "https://github.com/wmgeolab/geoBoundaries/raw/9f8c9e0f3aa13c5d07efaf10a829e3be024973fa/releaseData/gbOpen/GAB/ADM0/geoBoundaries-GAB-ADM0.geojson",
  ...
  "gbHumanitarian": {
    ...
  }
}
```

Alternatively, using `curl` from the terminal should also yield the same GeoJSON URL:

```bash
$ curl -s https://www.geoboundaries.org/api/current/gbOpen/GAB/ADM0/ | tr ',' '\n' | grep "gjDownloadURL.*gbOpen" | sed -E 's/.*"(https.+)"/\1/'
https://github.com/wmgeolab/geoBoundaries/raw/9f8c9e0f3aa13c5d07efaf10a829e3be024973fa/releaseData/gbOpen/GAB/ADM0/geoBoundaries-GAB-ADM0.geojson
```

You may use this GeoJSON URL for the `aoi` input when running the GEDI
subsetting DPS job.

## Citations

Country Boundaries from:

Runfola, D. et al. (2020) geoBoundaries: A global database of political
administrative boundaries.  PLoS ONE 15(4): e0231866.
<https://doi.org/10.1371/journal.pone.0231866>

[Digital Object Identifier]:
   https://doi.org
[fsspec.url_to_fs]:
  https://filesystem-spec.readthedocs.io/en/latest/api.html#fsspec.core.url_to_fs."
[geoBoundaries]:
  https://www.geoboundaries.org
[geoBoundaries API]:
  https://www.geoboundaries.org/api.html
[Scalene]:
  https://github.com/plasma-umass/scalene
