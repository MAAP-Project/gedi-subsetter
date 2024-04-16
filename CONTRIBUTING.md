# Contributing

- [Development Setup](#development-setup)
- [Managing Dependencies](#managing-dependencies)
- [Testing](#testing)
  - [Testing CMR Queries](#testing-cmr-queries)
  - [Linting and Running Unit Tests](#linting-and-running-unit-tests)
  - [Locally Running GitHub Actions Workflows](#locally-running-github-actions-workflows)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Registering a Version of the Algorithm](#registering-a-version-of-the-algorithm)
- [Creating a Release](#creating-a-release)

## Development Setup

To contribute to this work, you must obtain access to the [NASA MAAP], where the
Algorithm Development Environment (ADE) resides, and thus where algorithms can
be registered and launched.

If you wish to conduct development work outside of the ADE, you'll need to have
the following installed in your environment (the ADE has these pre-installed):

- `git`: On macOS, using Homebrew is highly recommended: `brew install git`.
  Otherwise, see <https://git-scm.com/downloads>.
- `conda`: On macOS, using Homebrew to install Miniforge (containing `conda`) is
  highly recommended: `brew install --cask miniforge`.  Otherwise, see
  <https://github.com/conda-forge/miniforge>.

You must also have `make` installed.  On macOS, `make` should already be
installed.  On Linux, if not already installed, you must locate installation
instructions appropriate for your system package manager.

**In the ADE**, `make` is not installed by default (at least not yet; see
[Install `make` in all ADE images](https://github.com/MAAP-Project/Community/issues/943)),
and must be installed as follows:

```plain
apt-get update && apt-get install make -y
```

To prepare for contributing, do the following on your development system (either
within the ADE or wherever else you're conducting development):

1. Clone this GitHub repository.
1. Change directory to the cloned working directory.
1. Create the `gedi_subset` conda environment: `make build`
1. Install (and run) Git pre-commit hooks: `make lint`
1. If desired, activate the `gedi_subset` conda environment:
   `conda activate gedi_subset` (**NOTE:** This is not necessary for running
   any of the `make` commands, which automatically use the `gedi_subset`
   environment even when the environment is not activated.)

## Managing Dependencies

To minimize the time it takes to install dependencies on the Docker image
created during algorithm registration, we leverage `conda-lock` to pre-resolve
dependencies and generate a lock file, to avoid dependency resolution during
registration.  This means that we manage dependencies and update the lock file
as follows:

1. Dependencies required by the algorithm are specified in `environment.yml`.
   (These are the only dependencies that will be installed in DPS.)
1. Development dependencies (for testing, static code analysis, notebooks, etc.)
   are specified in `environment-dev.yml`.
1. We use `conda-lock` to generate the lock file `conda-lock.yml` from the files
   above, whenever we make a change to at least one of the files.

Within `environment.yml` and `environment-dev.yml` we intentionally _avoid_
specifying _exact_ (`==`) versions to avoid resolution conflicts that might
prevent successful dependency resolution by giving the resolver enough
flexibility to satisfy all requirements.  When versions are specified, they are
only to ensure we use versions with necessary features or bug fixes, and
typically use the [compatible release operator] (`~=`) to constrain only the
_major_ version of a dependency.

**IMPORTANT:** Whenever you make changes to either `environment.yml` or
`environment-dev.yml`, you must regenerate `conda-lock.yml` and install the
updated dependencies into the `gedi_subset` conda environment on your
development workstation.  This is done automatically by running `make build`,
which will also update the `gedi_subset` environment as necessary.

## Testing

Successfully running linting and testing locally should ensure that the GitHub
Actions workflow triggered by your PR will succeed.

### Testing CMR Queries

We leverage the `vcrpy` library to record responses to HTTP/S requests.  When
running _existing_ tests, these recordings (_cassettes_ in `vcrp` parlance) are
replayed so that repeated test executions do _not_ make repeated requests.
Therefore, if you are not adding or modifying such tests, there is no need to
have a network connection, nor any need to run the tests within the ADE.

However, since we currently use the `maap-py` library for CMR queries, adding
new tests that make CMR queries (or modifying existing ones) will not only
require a network connection in order to record live responses, but will also
require that you obtain such recordings by running the new/modified tests within
the ADE in order to have the necessary auth in play.  Otherwise, the CMR queries
will either fail, or produce incorrect responses.

### Linting and Running Unit Tests

Linting runs a number of checks on various files, such as making sure your code
adheres to coding conventions and that the conda lock file is in sync with the
conda environment files, among other things.  To "lint" the files in the repo,
as well as run unit tests, run the following:

```plain
make lint typecheck test
```

If you see any errors, address them and repeat the process until there are no
errors.

### Locally Running GitHub Actions Workflows

Optionally, you may wish to locally test that the build for your future PR will
succeed.  To do so, you can use [act](https://nektosact.com/) to locally run
GitHub Actions workflows.  After installing `act`, run the following command
from the root of the repo:

```plain
act pull_request
```

**NOTE:** `act` uses a Docker container, so this will _NOT_ work within the ADE.
You must use `act` in an environment where Docker is installed.

The command above will initially take several minutes, but subsequent runs will
execute more quickly because only the first run must pull the `act` Docker
image.

## Submitting a Pull Request

To work on a feature or bug fix, you'll generally want to follow these steps:

1. Checkout and pull the lastest changes from the `main` branch.
1. Create a new branch from the `main` branch.
1. Add your desired code and/or configuration changes.
1. Add appropriate entries to the [Changelog](./CHANGELOG.md), according to the
   [Keep a Changelog] convention.  See existing sections in the Changelog for
   guidance on structure and format.  In general, you should add entries under
   the `Unreleased` section at the top.  A release manager will relable the
   `Unreleased` section to the appropriate release number upon the next release.
1. Register a version of the algorithm (see next section).
1. Test your registered version, and repeat as necessary.
1. Once you're satsified with your changes, delete your registered version.
1. Submit a PR to the GitHub repository, targeting the `main` branch.

## Registering a Version of the Algorithm

To register a new version of the algorithm, you must do so within the ADE, in
order to obtain automatic authorization.  If you have not been using the ADE for
development, but want to register the algorithm, within the ADE you must clone
and/or pull the latest code from the branch from which you want to register the
algorithm.

Then (again, within the ADE), simply run the following to register the algorithm
configured in `algorithm_config.yaml`:

```plain
bin/algo/register
```

When on the `main` branch (typically only after creating a release of the
algorithm, as described in the next section), and the current commit (`HEAD`) is
tagged, the script will check whether or not the value of `algorithm_version` in
the YAML file matches the value of the git tag.  If so, the YAML file will be
registered as-is.  If not, the script will report the version-tag mismatch.  A
match is expected when registering from the `main` branch, as that's where
tagging/releasing should take place.

However, you will likely want to register a version of the algorithm from
another branch when testing your changes on the branch, before opening a Pull
Request.  In this case, when registering from another branch, the script ignores
the value of `algorithm_version` in the YAML file, and the script will instead
use the name of the current branch as the algorithm version during registration
(the YAML file is _not_ modified).

Upon successful registration, you should see output similar to the following
(abridged):

```plain
{
  "code": 200,
  "message": {
    "id": "...",
    ...,
    "title": "Registering algorithm: gedi-subset",
    "message": "Registering algorithm: gedi-subset",
    ...,
    "status": "created",
    ...,
    "job_web_url": "https://repo.maap-project.org/root/register-job-hysds-v4/-/jobs/*****",
    "job_log_url": "https://repo.maap-project.org/root/register-job-hysds-v4/-/jobs/*****/raw"
  }
}
```

This indicates that the registration succeeded (code 200), and that the image
for the algorithm is being built.  To see the progress of the build, open a
browser to the `"job_web_url"` value shown in your output.  Note that although
you may see a "success" response (as shown above), that simply indicates that
registration was successfully _initiated_, meaning that an image _build_ was
successfully triggered.  The image build process may fail, so it is important to
make sure the build succeeds.  If it does, then the new version of the algorithm
should be visible in the **Algorithm** list on the form shown in the ADE after
choosing **Jobs > Submit Jobs** menu item.

If the corresponding output shown above shows an error, or it succeeds, but the
image _build_ fails, analyze the error message from the failed registration or
failed build.  If the output does not provide the information you need to
correct the problem, reach out to the platform team for assistance.

Once the registration _build_ succeeds, you may submit jobs against the
algorithm.

For unreleased versions, once you're satisified that your unreleased version of
the algorithm works properly, you should delete it as follows:

```bash
bin/algo/delete
```

Then create a Pull Request against the `main` branch.  If you need to make
adjustments to your branch, you can rerun registration to replace your
unreleased version of the algorithm as often as necessary until you're
satisfied.

## Creating a Release

After one or more Pull Requests have landed on the `main` branch to constitute
a new release:

1. Checkout the latest changes to the `main` branch.
1. Create a new branch named `release-<VERSION>`, where `<VERSION>` is an
   appropriate version number for the changes being made, according to
   [Semantic Versioning].
1. In `algorithm_config.yaml` change the value of `algorithm_version` to the
   same value as `<VERSION>` from the previous step.
1. In the [Changelog](./CHANGELOG.md), immediately below the `Unreleased`
   heading add a new heading (at the same level) using the format
   `<VERSION> (<YYYY-MM-DD>)`, where `<VERSION>` is as above, and `<YYYY-MM-DD>`
   is the _expected_ release date (which might not be the _actual_ release date,
   depending on the PR approval process).
1. Commit the changes, and open a Pull Request to `main`.
1. Once the PR is approved and merged, go to
   <https://github.com/MAAP-Project/gedi-subsetter/releases/new>
1. Click the **Choose a tag** dropdown.
1. In the input box that appears, enter the _same_ value as the value of
   `<VERSION>` from previous steps, and click the **Create a new tag** label that
   appears immediately below the input box.
1. In the **Release title** input, also enter the _same_ value as the value of
   `<VERSION>` in the previous step.
1. In the description text box, copy and paste the content of only the _new
   version section_ you added earlier to the Changelog, **excluding** the new
   version heading (since it would be redundant with the release title).
1. Click the **Publish release** button.
1. Checkout and pull the `main` branch in order to pull down the new tag created
   by the release process.
1. Register the new release of the algorithm as described in the previous
   section.

[compatible release operator]:
  https://peps.python.org/pep-0440/#compatible-release
[Keep a Changelog]:
  https://keepachangelog.com/en/1.0.0/
[NASA MAAP]:
  https://maap-project.org/
[Semantic Versioning]:
  https://semver.org/spec/v2.0.0.html
