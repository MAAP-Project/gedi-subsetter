# Contributing

## Development Setup

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

## Creating an Algorithm Release

1. Create a new branch based on an appropriate existing branch (typically based
   on `main`).
1. Add your desired code and/or configuration changes.
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

## Registering an Algorithm Release

Once a release is published in the GitHub repository (see above), the algorithm
must be registered in the ADE.  To do so, follow these steps:
1. Within an ADE workspace, open a **New Launcher** tab and underneath the
   **MAAP Extensions** section, select **Register Algorithm**.
   **Terminal** launcher.
1. On the main registration page:
   1. Under Repository Information:
      - Enter the **Repository URL** as
         `https://github.com/MAAP-Project/gedi-subsetter.git`.
      - Enter the **Repository Branch** as the name of the release tag (e.g., `1.0.0`).
      - Enter the **Run Command** as `gedi-subsetter/subset.sh`.
      - Enter the **Build Command** as `gedi-subsetter/build.sh`.
   1. Under General Information:
      - Enter the **Algorithm Name** as `gedi-subsetter`.
      - Enter the **Algorithm Description** as `Subset GEDI L1B, L2A, L2B, or L4A granules within an area of interest (AOI)`.
      - Enter the **Disk Space** as `20GB`.
      - Enter the **Resource Allocation** as `maap-dps-worker-32gb`.
      - Enter the **Container URL** as `mas.dit.maap-project.org/root/maap-workspaces/base_images/r:dit`.
   1. Under Input Types, add the following Name, Description pairs:
      1. For File Inputs:
         - `aoi`: Area of Interest GeoJSON file
      1. For Positional Inputs:
         - `doi`: Digital Object Identifier (DOI) of the GEDI collection to subset, or a logical name representing such a DOI
         - `temporal`: (Default: full temporal range): Temporal range to subset.
         - `lat`: Name of the dataset used for latitude.
         - `lon`: Name of the dataset used for longitude.
         - `beams`: (Default: `all`): `all`, `coverage`, or `power`, or a comma-separated list of specific beam names, with or without the `BEAM` prefix (e.g., `BEAM0000,BEAM0001` or `0000,0001`).
         - `columns`: One or more column names, separated by commas, to include in the output file.
         - `query`: (Default: no query): Query expression for subsetting the rows in the output file.
         - `limit`: (Default: 1_000): Maximum number of GEDI granule data files to download from the CMR
         - `output`: Name to use for the output file.
1. Once finished, click **Register Algorithm**
1. Check the build job status at
   <https://repo.maap-project.org/root/register-job-hysds-v4/-/jobs>.  If the job
   fails, you will need to correct the issue (and likely create a patch release,
   following the release steps again).  Otherwise, you should now be able to
   open the **Jobs** menu, choose **View & Submit Jobs**, and find
   the new version of the algorithm in the dropdown list of the **Submit** tab.
