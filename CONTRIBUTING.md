# Contributing

- [Development Setup](#development-setup)
  - [Create the conda environment](#create-the-conda-environment)
  - [Activate the conda environment](#activate-the-conda-environment)
  - [Install Git pre-commit hooks](#install-git-pre-commit-hooks)
- [Managing Dependencies](#managing-dependencies)
- [Development Process](#development-process)
- [Registering a Version of the Algorithm](#registering-a-version-of-the-algorithm)
- [Creating a Release](#creating-a-release)

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
1. Create the `gedi_subset` conda environment (see below).
1. Activate the `gedi_subset` conda environment (see below).
1. Install Git pre-commit hooks (see below).

### Create the conda environment

Once you have cloned this repository and changed directory to the clone, you
must create the `gedi_subset` conda environment.  To do so, you'll use the
script `bin/build.sh`, as instructed below, which is a script that serves
double-duty as the script that also builds the DPS environment for executing the
algorithm, by ensuring that all necessary Python packages are installed.

**IMPORTANT:** If you're working in the ADE, the default location for conda
environments is ephemeral, meaning that whenever your ADE workspace is
restarted, all of the conda environments in the default location are lost.  This
requires you to recreate any such conda environments that you wish to use after
a workspace restart.  To prevent this from occurring, you must provide a
location that persists across restarts via the `--prefix` option with the
`bin/build.sh` script, as described below.  _However_, taking this approach
means that creation of the conda environment may take significantly more time
(possibly 10s of minutes) because the persistent location is an AWS S3 bucket.

If you're not working in the ADE, or you are, but aren't bothered by having to
rerun the following command every time you want to use the `gedi_subset` after
a workspace restart, you may create the conda environment simply as follows:

```bash
bin/build.sh
```

_Alternatively_, if you _are_ using the ADE, and you _do_ want the `gedi_subset`
conda environment to persist across workspace restarts, use the following
command instead:

```bash
bin/build.sh --prefix "${HOME}/envs/gedi_subset"
```

Note that you may supply additional options, all of which are passed through to
the `conda-lock install` command (see
[Managing Dependencies](#managing-dependencies)).  For a list of options, see
[conda-lock install](https://conda.github.io/conda-lock/cli/gen/#conda-lock-install).
By default, all _development_ dependencies will be installed along with all of
the main dependencies (i.e., the `--dev` option is implicit).

**TROUBLESHOOTING:** If the command above fails with an error that includes the
message `conda: command not found`, it is likely due to `conda` initialization
being skipped when your terminal window is initialized.  Here are 2 options for
resolving this issue (do one, not both):

**Option 1:** Edit your `${HOME}/.bash_profile` file by adding the following
line at the top of the file:

```bash
source "${HOME}/.bashrc"
```

**Option 2:** Move the conda initialization block from `${HOME}/.bashrc` to
`${HOME}/.bash_profile`.  The conda initialization block is the block of lines
that looks like the following:

```plain
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
... (contents elided) ...
# <<< conda initialize <<<
```

Move that block in it's entirety (_including_ the leading and trailing comment
lines) from `${HOME}/.bashrc` to `${HOME}/.bash_profile`.

### Activate the conda environment

If you did _not_ specify the `--prefix` option to `bin/build.sh`, you can use
the following command:

```bash
conda activate gedi_subset
```

Otherwise, you must instead use the following command (alter the value if you
specified a different prefix with the `bin/build.sh` command earlier):

```bash
conda activate "${HOME}/envs/gedi_subset"
```

### Install Git pre-commit hooks

We leverage `pre-commit` to help with some housekeeping tasks.  To enable the
configured hooks, run the following from the root of the repository:

```bash
pre-commit install --install-hooks
```

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
intentional consistency for dependency installation designed to greatly reduce,
if not eliminate, possible differences in dependencies that might otherwise
allow development and testing to succeed, but later result in a failure in DPS,
either during algorithm registration, or worse, during algorithm execution.

## Development Process

To work on a feature or bug fix, you'll generally want to follow these steps:

1. Create a branch from the `main` branch.
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

To register a new version of the algorithm, you must do so within the ADE in
order to obtain automatic authorization.  If you have not been using the ADE for
development, be sure to clone and/or pull the latest code from the branch from
which you want to register the algorithm.

Then, simply run the following to register the algorithm described in
`algorithm_config.yaml`:

```plain
bin/register-algorithm.sh
```

When on the `main` branch (typically only after creating a release of the
algorithm, as described in the next section), and the current commit (`HEAD`) is
tagged, the script will check whether or not the value of `algorithm_version` in
the YAML file matches the value of the git tag.  If so, the YAML file will be
registered as-is.  If not, the script will report the version-tag mismatch.  A
match is expected when registering from the `main` branch, as that's where
tagging/releasing should take place.

However, you will likely want to register a version of the algorithm from
another branch when test your changes on the branch, before opening a Pull
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
    "job_web_url": "https://repo.maap-project.org/root/register-job-hysds-v4/-/jobs/XXXXX",
    "job_log_url": "https://repo.maap-project.org/root/register-job-hysds-v4/-/jobs/XXXXX/raw"
  }
}
```

This indicates that the registration succeeded (code 200), and that the image
for the algorithm is being built.  To see the progress of the build, open a
browser to the `"job_web_url"` value shown in your output.  Note that although
registration succeeded, the image build process may fail, so it is important to
make sure the build succeeds.  If it does, then the new version of the algorithm
should be visible in the **Algorithm** list on the form shown in the ADE after
choosing **Jobs > Submit Jobs** menu item.

If registration fails, or it succeeds, but the image build fails, analyze the
error message from the failed registration or failed build.  If it does not
provide the information you need to correct the problem, reach out to the
platform team for assistance.

Once the registration build succeeds, you may submit jobs against the algorithm.

For unreleased versions, once you're satisified that your unreleased version of
the algorithm works properly, you should delete it as follows:

```bash
bin/delete-algorithm.sh
```

Then create a Pull Request against the `main` branch.  If you need to make
adjustments to your branch, you can rerun registration to replace your
unreleased version of the algorithm as often as necessary until you're
satisfied.

## Creating a Release

After one or more Pull Requests have landed on the `main` branch to constitute
a new release:

1. Checkout the latest changes to the `main` branch.
1. Create a new branch named `release/VERSION`, where `VERSION` is an
   appropriate version number, according to [Semantic Versioning].
1. In `algorithm_config.yaml` change the value of `algorithm_version` to the
   same value as `VERSION` from the previous step.
1. In the [Changelog](./CHANGELOG.md), change the `Unreleased` heading to the
   same value as `VERSION` from the previous step, and then, above the new
   version heading, add a new `Unreleased` section, for future changes.
1. Commit the changes, and open a Pull Request to `main`.
1. Once the PR is approved and merged, go to
   <https://github.com/MAAP-Project/gedi-subsetter/releases/new>
1. Click the **Choose a tag** dropdown.
1. In the input box that appears, enter the _same_ value as the value of
   `VERSION` from previous steps, and click the **Create a new tag** label that
   appears immediately below the input box.
1. In the **Release title** input, also enter the _same_ value as the value of
   `VERSION` in the previous step.
1. In the description text box, copy and paste the content of only the _new
   version section_ you added earlier to the Changelog, **excluding** the new
   version heading.
1. Click the **Publish release** button.
1. Checkout and pull the `main` branch in order to pull down the new tag created
   by the release process.
1. Register the new release of the algorithm as described in the previous
   section.

[compatible release operator]:
   https://peps.python.org/pep-0440/#compatible-release
[Keep a Changelog]:
  https://keepachangelog.com/en/1.0.0/
[MAAP GEDI Subsetter repository]:
  https://github.com/MAAP-Project/gedi-subsetter.git
[NASA MAAP]:
  https://maap-project.org/
[Semantic Versioning]:
    https://semver.org/spec/v2.0.0.html
