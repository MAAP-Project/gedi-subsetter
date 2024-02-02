# Contributing

- [Development Setup](#development-setup)
- [Managing Dependencies](#managing-dependencies)
- [Creating an Algorithm Release](#creating-an-algorithm-release)
- [Registering an Algorithm Release](#registering-an-algorithm-release)

## Development Setup

To contribute to this work, you must obtain access to the following:

1. [MAAP GEDI Subsetter repository]: For creating new versions (releases) of the
   algorithms implemented in the repository.
1. [NASA MAAP]: Where the Algorithm Development Environment (ADE) resides, and
   thus where algorithms can be registered.

On your development system (not necessarily the ADE), you must have the
following installed:

- `git`: [pre-installed in the ADE] On macOS, using Homebrew is highly
  recommended: `brew install git`.  Otherwise, see
  <https://git-scm.com/downloads>.
- `conda`: [pre-installed in the ADE] On macOS, using Homebrew to install
  Miniforge (containing `conda`) is highly recommended:
  `brew install --cask miniforge`.  Otherwise, see
  <https://github.com/conda-forge/miniforge>.
- `conda-lock`: On macOS, using Homebrew is highly recommended:
  `brew install conda-lock`.  Otherwise, see
  <https://github.com/conda/conda-lock>.
- `pre-commit`: On macOS, using Homebrew is highly recommended:
  `brew install pre-commit`.  Otherwise, see <https://pre-commit.com/>.

To prepare for contributing, do the following on your development system (again,
not necessarily the ADE):

1. Clone this GitHub repository.
1. Change directory to the cloned repository.
1. Create the `gedi_subset` virtual environment.

   **NOTE:** _If you're working in the ADE, use the `--prefix` option shown
   (excluding the square brackets), otherwise you will need to repeat this step
   whenever your restart your ADE workspace_.  Outside of the ADE, there's no
   such need to use the `--prefix` option, unless you prefer to use a
   non-default location:

   ```bash
   bin/build.sh [--prefix "${HOME}/envs/gedi_subset"]
   ```

   Note that you may also supply additional options, all of which are passed
   through to the `conda-lock install` command.  For a list of options, see
   <https://conda.github.io/conda-lock/cli/gen/#conda-lock-install>.

   **TROUBLESHOOTING:** If the command above fails with the error message
   `conda: command not found`, you must first run `conda activate base`, then
   rerun the command above.

1. Activate the `gedi_subset` virtual environment.

   If you did _not_ specify the `--prefix` option in the previous step, you can
   use the following command:

   ```bash
   conda activate gedi_subset
   ```

   Otherwise, you must instead use the following command (alter the value if you
   specified a different prefix in the previous step):

   ```bash
   conda activate "${HOME}/envs/gedi_subset"
   ```

1. Install Git pre-commit hooks:

   ```bash
   pre-commit install --install-hooks
   ```

During development, you will create PRs against the GitHub repository, as
explained below.

## Managing Dependencies

To minimize the time it takes to install dependencies on the Docker image
created during algorithm registration, we leverage `conda-lock` to pre-resolve
dependencies and generate a lock file, so that dependency resolution does not
take place during registration.  This means that we manage dependencies and
update the lock file as follows:

1. Dependencies required by the algorithm are specified in `environment.yml`.
   (These are the only dependencies that will be installed in DPS.)
1. Development dependencies (for testing, static code analysis, etc.) are
   specified in `environment-dev.yml`.
1. We use `conda-lock` to generate the lock file `conda-lock.yml` from the files
   above whenever we either make a change to one (or both) of the files, or wish
   to simply update dependencies (specified in those files) to their latest
   versions that satisfy the specified version constraints (see below).

Within `environment.yml` and `environment-dev.yml` we intentionally _avoid_
specifying _exact_ (`==`) versions to avoid resolution conflicts that would
prevent successful dependency resolution by giving the resolver enough
flexibility to satisfy all requirements.  When versions are specified, they are
only to ensure we use versions with necessary features or without known bugs we
want to avoid, and typically use the [compatible release operator] (`~=`) to
constrain only the _major_ version of a dependency.

The lock file, `conda-lock.yml`, was generated with the following command:

```plain
bin/generate-lock-file.sh
```

Whenever a dependency is added, removed, or has its version constraint changed
within either source file (`environment.yml` or `environment-dev.yml`), the same
command above should be performed, and all of the updated files should be
committed to Git.

If you simply want to update some (or all) packages to their latest versions
compatible with their version constraints, run the following command instead:

```plain
conda lock --update TEXT
```

where `TEXT` is one or more (comma-separated) packages specified in
`environment.yml` or `environment-dev.yml`.  To update _all_ of the packages to
their latest versions matching their constraints, specify empty quotes in place
of `TEXT` (either `''` or `""`), otherwise `conda-lock` will complain.

The lock file (`conda-lock.yml`) is a unified, multi-platform lock file, so it
can be used on various platforms (Linux, macOS, and Windows) to create (or
update) the `gedi_subset` conda environment, which is precisely what the
`build.sh` script does.

**IMPORTANT:** Whenever you regenerate or update the lock file, you must also
update your `gedi_subset` conda environment on your development workstation so
that all dependency changes are applied to it, because updating the lock file
does not apply the changes to your conda environment.  Therefore, you must
again run `bin/build.sh` command (with appropriate options).

Note, as indicated in a later section, the `bin/build-dps.sh` script is used to
install the dependencies from the lock file during algorithm registration.
Specifically, it calls `bin/build.sh` with options appropriate for the DPS
environment.

Using the conda lock file in both development and DPS environments is an
intentional consistency for dependency installation designed to eliminate
possible differences in dependencies that might otherwise allow development and
testing to succeed, but later result in a failure in DPS, either during
algorithm registration, or worse, during algorithm execution.

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
   1. Go to <https://github.com/MAAP-Project/gedi-subsetter/releases/new>
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
1. On the main registration page:
   1. Under Repository Information:
      - Enter the **Repository URL** as
         `https://github.com/MAAP-Project/gedi-subsetter.git`.
      - Enter the **Repository Branch** as the name of the release tag (e.g.,
        `1.0.0`).
      - Enter the **Run Command** as `gedi-subsetter/bin/subset.sh`.
      - Enter the **Build Command** as `gedi-subsetter/bin/build-dps.sh`.
   1. Under General Information:
      - Enter the **Algorithm Name** as `gedi-subset`.
      - Enter the **Algorithm Description** as
        `Subset GEDI L1B, L2A, L2B, or L4A granules within an area of interest (AOI)`.
      - Enter the **Disk Space** as `20`.
      - Enter the **Resource Allocation** as `maap-dps-worker-32gb`.
      - Enter the **Container URL** as
        `mas.maap-project.org/root/maap-workspaces/base_images/vanilla:v3.1.4`.
   1. Under Input Types, add the following Name, Description pairs:
      1. For File Inputs:
         - `aoi`: Area of Interest GeoJSON file
      1. For Positional Inputs:
         - `doi`: Digital Object Identifier (DOI) of the GEDI collection to
           subset, or a logical name representing such a DOI
         - `temporal`: (Default: `-`, which means the full temporal range):
           Temporal range to subset.
         - `lat`: Name of the dataset used for latitude.
         - `lon`: Name of the dataset used for longitude.
         - `beams`: (Default: `all`): `all`, `coverage`, or `power`, or a
           comma-separated list of specific beam names, with or without the
           `BEAM` prefix (e.g., `BEAM0000,BEAM0001` or `0000,0001`).
         - `columns`: One or more column names, separated by commas, to include
           in the output file.
         - `query`: (Default: no query): Query expression for subsetting the
           rows in the output file.
         - `limit`: (Default: 1_000): Maximum number of GEDI granule data files
           to download from the CMR
         - `output`: Name to use for the output file.
1. Once finished, click **Register Algorithm**
1. Check the build job status at
   <https://repo.maap-project.org/root/register-job-hysds-v4/-/jobs>.  If the
   job fails, you will need to correct the issue (and likely create a patch
   release, following the release steps again).  Otherwise, you should now be
   able to open the **Jobs** menu, choose **View & Submit Jobs**, and find the
   new version of the algorithm in the dropdown list of the **Submit** tab.

[compatible release operator]:
   https://peps.python.org/pep-0440/#compatible-release
[Keep a Changelog]:
  https://keepachangelog.com/en/1.0.0/
[MAAP GEDI Subsetter repository]:
  https://github.com/MAAP-Project/gedi-subsetter.git
[NASA MAAP]:
  https://maap-project.org/
