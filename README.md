# GEDI Subsetting

- [Algorithm Outline](#algorithm-outline)
- [Algorithm Inputs](#algorithm-inputs)
  - [Specifying an AOI](#specifying-an-aoi)
  - [Specifying a DOI](#specifying-a-doi)
    - [L1B](#l1b)
    - [L2A](#l2a)
    - [L2B](#l2b)
    - [L4A](#l4a)
- [Running a GEDI Subsetting DPS Job](#running-a-gedi-subsetting-dps-job)
  - [Submitting a DPS Job](#submitting-a-dps-job)
  - [Checking the DPS Job Status](#checking-the-dps-job-status)
  - [Getting the DPS Job Results](#getting-the-dps-job-results)
- [Getting the GeoJSON URL for a geoBoundary](#getting-the-geojson-url-for-a-geoboundary)
- [Contributing](#contributing)
  - [Development Setup](#development-setup)
  - [Creating an Algorithm Release](#creating-an-algorithm-release)
  - [Registering an Algorithm Release](#registering-an-algorithm-release)
- [Citations](#citations)

## Algorithm Outline

At a high level, the GEDI subsetting algorithm does the following:

- Queries the MAAP CMR for granules from a specified GEDI collection that
  intersect a specified Area of Interest (AOI) (as a GeoJSON file).  This is
  limited to GEDI collections granule data files are in HDF5 format, which are
  L1B, L2A, L2B, and L4A.
- For each granule within the specified AOI, downloads its HDF5 (`.h5`) file.
- Subsets each data file by selecting specified datasets within the file and
  limiting data to values that match a specified query condition.
- Combines all subset files into a single output file named `gedi_subset.gpkg`,
  in GeoPackage format, readable with `geopandas` as a `GeoDataFrame`.

## Algorithm Inputs

To run a GEDI subsetting DPS job, you must supply the following inputs (a value
must be supplied for every input):

- `aoi`: URL to a GeoJSON file representing your area of interest (see
  [Specifying an AOI](#specifying-an-aoi))

- `doi`: [Digital Object Identifier] (DOI) of the GEDI collection to subset, or
  a logical name representing such a DOI (see
  [Specifying a DOI](#specifying-a-doi))

  Since 0.3.0

- `temporal`: Temporal range to subset.  To use an unbounded temporal range, set
  this input to a dash (`-`).  Otherwise, you can specify either a closed range,
  with start and end dates, or a half-open range, with either a start date or an
  end date.  For full details on the valid formats, see the NASA CMR's
  documentation on
  [temporal range searches](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#temporal-range-searches).

  Since 0.6.0

- `lat`: Name of the dataset used for latitude.

  Since 0.3.0

- `lon`: Name of the dataset used for longitude.

  Since 0.3.0

- `beams`: Which beams to include in the subset. Must be `all`, `coverage`,
  `power`, _OR_ a comma-separated list of beam names, with or without the `BEAM`
  prefix (e.g., `BEAM0000,BEAM0001` or `0000,0001`)

  Since 0.4.0

- `columns`: Comma-separated list of column names to include in the output file.
  These names correspond to the variables (layers) within the data files, and
  vary from collection to collection.  Consult the documentation for a list of
  variables available per collection (see [Specifying a DOI](#specifying-a-doi)
  for documentation links).

  In addition to the specified columns, the output file will also include a
  `filename` (`str`) column that includes the name of the original `h5` file,
  and a `BEAM` (`str`) column with the 4-digit bit string suffix of the original
  `BEAM*` group name (e.g., `0000` representing the original `BEAM0000` name),
  both for traceability.

  **IMPORTANT:** To specify nested variables (i.e., variables _not_ at the top
  of a BEAM), you may use a path containing forward slashes (`/`) that is
  relative to the BEAM it appears within.  For example, if a BEAM contains a
  `geolocation` group, and within that group is a variable named
  `sensitivity_a2`, then you would refer to that nested variable as
  `geolocation/sensitivity_a2`.

- `query`: Query expression for subsetting the rows in the output file.  This
  expression selects rows of data for which the expression is true.  Again,
  names in the expression are variable (layer) names.  For example:
  `quality_flag == 1`.

  **NOTE:** If you do not wish to subset the rows of the data, set this input
  value to a dash (`-`) to indicate _no_ query.

  To combine multiple expressions, you may use the `and` and `or` boolean
  operators.

  Examples:

  ```plain
  quality_flag == 1 and sensitivity > 0.95
  (l2a_quality_flag == 1 or l2b_quality_flag == 1) and sensitivity > 0.95
  ```

  **IMPORTANT:** To specify nested variables (i.e., variables _not_ at the top
  of a BEAM), you may use a relative path, as described above for column names,
  but you must surround such nested path names with backticks.  For example:

  ```plain
  quality_flag == 1 and `geolocation/sensitivity_a2` > 0.95
  ```

  Alternatively, "dot" notation may be used in place of using slashes.  This
  eliminates the need to use backticks to surround a path.  Note, however, that
  the **corresponding columns in the output will still contain slashes in their
  names**:

  ```plain
  quality_flag == 1 and geolocation.sensitivity_a2 > 0.95
  ```

- `limit`: Maximum number of GEDI granule data files to download, among those
  that intersect the specified AOI, and fall within the specified temporal range
  (if supplied).  To leave unlimited, specify `0` (or any non-positive integer).

- `output`: Name to use for the output file.  This can also include a path,
  which will be relative to the standard DPS output directory for a job.

  The name does not need to include an extension, as a `.gpkg` extension will be
  added automatically.  If a `.gpkg` extension is supplied, it will remain
  unchanged.  If a different extension is supplied, a `.gpkg` extension will be
  added after the specified extension.

  Examples showing how the value specified for `output` is mapped to a final
  output file:

  - `myoutput` -> `myoutput.gpkg`
  - `myoutput.gpkg` -> `myoutput.gpkg`
  - `myoutput.h5` -> `myoutput.h5.gpkg`
  - `mypath/myoutput` -> `mypath/myoutput.gpkg`

  Since 0.6.0

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
~/my-public-bucket/path/to/aoi.geojson
^^^^^^^^^^^^^^^^^^
```

You would then supply the following URL as the `aoi` input value when running
this algorithm as a DPS job, where `<USERNAME>` is your ADE username:

```plain
https://maap-ops-workspace.s3.amazonaws.com/shared/<USERNAME>/path/to/aoi.geojson
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      Replace "~/my-public-bucket" with this URL prefix
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
   beams="all",
   columns=...,
   query=...,
   limit=0,
   temporal="-",
)
```

#### L2A

```python
inputs = dict(
   aoi=...,
   doi="L2A",  # or a specific DOI
   lat="lat_lowestmode",  # or "lat_highestreturn"
   lon="lon_lowestmode",  # or "lon_highestreturn"
   beams="all",
   columns="rh50,rh98",
   query="quality_flag == 1 and sensitivity > 0.95",
   limit=0,
   temporal="-",
)
```

#### L2B

```python
inputs = dict(
   aoi=...,
   doi="L2B",  # or a specific DOI
   lat="geolocation/lat_lowestmode", # or "geolocation/lat_highestreturn"
   lon="geolocation/lon_lowestmode", # or "geolocation/lon_highestreturn"
   beams="all",
   columns="rh100",
   query="l2a_quality_flag == 1 and l2b_quality_flag == 1 and sensitivity > 0.95",
   limit=0,
   temporal="-",
)
```

#### L4A

```python
inputs = dict(
   aoi=...,
   doi="L4A",  # or a specific DOI
   lat="lat_lowestmode",
   lon="lon_lowestmode",
   beams="all",
   columns="agbd, agbd_se, sensitivity, geolocation/sensitivity_a2",
   query="l2_quality_flag == 1 and l4_quality_flag == 1 and sensitivity > 0.95 and `geolocation/sensitivity_a2` > 0.95",
   limit=0,
   temporal="-",
)
```

## Running a GEDI Subsetting DPS Job

### Submitting a DPS Job

The GEDI Subsetting DPS Job is named `gedi-subset_ubuntu`, and may be executed
from your ADE Workspace by opening the **DPS/MAS Operations** menu, choosing
the **Execute DPS Job** menu option, and selecting `gedi-subset_ubuntu:<VERSION>`
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
   temporal="<RANGE>",  # or "-" for unlimited temporal range
)

result = maap.submitJob(
    identifier="<DESCRIPTION>",
    algo_id="gedi-subset_ubuntu",
    version="<VERSION>",
    queue="maap-dps-worker-32gb",
    username="<USERNAME>",  # Your Earthdata Login username
    **inputs
)

job_id = result["job_id"]
job_id or result
```

### Checking the DPS Job Status

To check the status of your job via the ADE UI, open the **DPS/MAS Operations**
menu, choose **Get DPS Job Status**, and enter the value of the `job_id` to
obtain the status, just as if you had submitted the job from the menu (rather
than programmatically).

Alternatively, to programmatically check the status of the submitted job, you
may run the following code.  If using a notebook, use a separate cell so you can
run it repeatedly until you get a status of either `'Succeeded'` or `'Failed'`:

```python
import re

# Should evaluate to 'Accepted', 'Running', 'Succeeded', or 'Failed'
re.search(
   r"Status>(?P<status>.+)</wps:Status>",
   maap.getJobStatus(job_id).text
).group('status')
```

### Getting the DPS Job Results

Once the job status is either **Succeeded** or **Failed**, you may obtain the
job results either via the UI.

To obtain the results programmatically, you can use the following to see the
details.  Note the use of `print`, which is necessary within a Jupyter notebook
because the output may contain multiple lines.  Without wrapping everything in a
call to `print`, the output might be very hard to read:

```python
print(
   re.search(
      r"Data>(?P<data>.+)</wps:Data>",
      maap.getJobResult(job_id).text,
      re.DOTALL
   ).group('data')
)
```

If the jobs status is **Failed**, the job results should show failure details.

If the job status is **Succeeded**, the job results should show 3 URLs, with the
first URL of the following form:

```plain
http://.../<USERNAME>/dps_output/gedi-subset_ubuntu/<VERSION>/<DATETIME_PATH>
```

Based upon this URL, the `gedi_subset.gpkg` file generated by the job should be
available at the following path within the ADE:

```plain
~/my-private-bucket/dps_output/gedi-subset_ubuntu/<VERSION>/<DATETIME_PATH>/gedi_subset.gpkg
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

## Contributing

### Development Setup

To contribute to this work, you must obtain access to the following:

1. [MAAP GEDI Subsetter hosted on GitHub]: For creating new versions
   (releases) of the algorithms implemented in the repository.
1. [MAAP GEDI Subsetter hosted on GitLab]: A copy of the GitHub
   repository, in order to enable registering new versions of the algorithms
   from within the ADE (which currently only supports GitLab repositories).
1. [NASA MAAP]: Where the ADE resides, and thus where algorithms can be
   registered (from GitLab repositories).

To prepare for contributing, do the following in an ADE workspace:

1. Clone this GitHub repository.
1. Change directory to the cloned repository.
1. Add the GitLab repository as another remote (named `ade` here, but you may
   specify a different name for the remote):

   ```bash
   git remote add --tags -f ade https://repo.ops.maap-project.org/data-team/gedi-subsetter.git
   ```

1. Create the `gedi_subset` virtual environment (**NOTE:** _you will need to
   repeat this step whenever your restart your ADE workspace_):

   ```bash
   ./build.sh --dev
   ```

1. Activate the `gedi_subset` virtual environment:

   ```bash
   conda activate gedi_subset
   ```

1. Install Git pre-commit hooks:

   ```bash
   pre-commit install --install-hooks
   ```

If you plan to do any development work outside of the ADE (such as on your local
workstation), perform the steps above in that location as well.  **NOTE:** _This
means that you must have `conda` installed (see [conda installation]) in your
desired development location outside of the ADE workspace._

During development, you will create PRs against the GitHub repository, as
explained below.

### Creating an Algorithm Release

1. Create a new branch based on an appropriate existing branch (typically based
   on `main`).
1. Add your desired code and/or configuration changes.
1. Update the value of `version` in `algorithm_config.yaml`
   according to the versioning convention referenced at the top of the
   [Changelog](./CHANGELOG.md).
1. Add appropriate entries to the [Changelog](./CHANGELOG.md), according to
   the [Keep a Changelog] convention.  In particular:
   - Add a new, second-level section of the following form:

      ```plain
      ## [VERSION] - YYYY-MM-DD
      ```

      where:
      - `VERSION` is the value of `version` specified in `algorithm_config.yaml`
      - `YYYY-MM-DD` is the date that you expect to create the release (see the
        following steps), which may or may not be the current date, depending
        upon when you expect your PR (next step) to be approved and merged.
   - Add appropriate third-level sections under the new version section (for
     additions, changes, and fixes).  Again, see [Keep a Changelog].
1. Submit a PR to the GitHub repository.
1. _Only when_ the PR is on a branch to be merged into the `main` branch _and_
   it has been approved and merged, create a new release in GitHub as follows:
   1. Go to
      <https://github.com/MAAP-Project/gedi-subsetter/releases/new>
   1. Click the **Choose a tag** dropdown.
   1. In the input box that appears, enter the _same_ value as the new value of
      `version` in `algorithm_config.yml`, and click the **Create a new tag**
      label that appears immediately below the input box.
   1. In the **Release title** input, also enter the _same_ value as the new
      value of `version` in `algorithm_config.yml`.
   1. In the description text box, copy and paste from the Changelog file only
      the _new version section_ you added earlier to the Changelog, including
      the new version heading.
   1. Click the **Publish release** button.

### Registering an Algorithm Release

Once a release is published in the GitHub repository (see above), the code from
the GitHub repository must be pushed to the GitLab repository in order to be
able to register the new version of the algorithm, as follows, within the ADE:

1. Open a Terminal tab (if necessary) and change directory to the repository.
1. Pull the latest code from GitHub (to obtain merged PR, if necessary):

   ```bash
   git checkout main
   git pull origin
   ```

1. Push the latest code to GitLab (replace `ade` with the appropriate remote
   name, if you didn't use `ade` earlier):

   ```bash
   git push --all ade
   git push --tags ade
   ```

   **NOTE:** On occassion, you might get a "server certificate verification
   failed" error attempting to push to GitLab.  If so, simply prefix the
   preceding commands with `GIT_SSL_NO_VERIFY=1`
1. In the ADE's File Browser, navigate to `gedi-subsetter`.
1. Right-click on `algorithm_config.yaml` and choose **Register as MAS
   Algorithm** from the context menu.
1. Confirm that the value of the **version** field matches the GitHub release
   version you created above.  If not, click **Cancel** and review earlier
   steps.  If so, click **Ok**, which will trigger a build job that will take
   about 30 minutes.
1. Check the build job status at
   <https://repo.ops.maap-project.org/root/register-job/-/jobs>.  If the job
   fails, you will need to correct the issue (and likely create a patch release,
   following the release steps again).  Otherwise, you should now be able to
   open the **DPS/MAS Operations** menu, choose **Execute DPS Job**, and find
   the new version of the algorithm in the dropdown list for confirmation.

## Citations

Country Boundaries from:

Runfola, D. et al. (2020) geoBoundaries: A global database of political
administrative boundaries.  PLoS ONE 15(4): e0231866.
<https://doi.org/10.1371/journal.pone.0231866>

[conda installation]:
   https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html
[Digital Object Identifier]:
   https://doi.org
[geoBoundaries]:
  https://www.geoboundaries.org
[geoBoundaries API]:
  https://www.geoboundaries.org/api.html
[Keep a Changelog]:
  https://keepachangelog.com/en/1.0.0/
[MAAP GEDI Subsetter hosted on GitHub]:
  https://github.com/MAAP-Project/gedi-subsetter.git
[MAAP GEDI Subsetter hosted on GitLab]:
  https://repo.ops.maap-project.org/data-team/gedi-subsetter.git
[NASA MAAP]:
  https://ops.maap-project.org/
