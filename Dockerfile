FROM ghcr.io/prefix-dev/pixi:0.66.0

SHELL [ "/bin/bash", "-c" ]

# Simulate result of algorithm registration.  We first copy necessary files to
# mimic cloning the repository, but don't copy everything wholesale, because
# it's not necessary for our purposes here.  We just need enough to be able to
# run the build command in the next step.
WORKDIR /app/gedi-subsetter
COPY bin/build.sh ./bin/
COPY src/ ./src/
COPY pixi.lock pyproject.toml ./

# Run the build script, just like the alogorithm registration process does.
WORKDIR /app
RUN /app/gedi-subsetter/bin/build.sh

# During algorithm registration, the subset.sh script would land as part of the
# repository clone, but we've separated it out here simply for development
# convenience.  This avoids having to run the build script if we only make
# changes to the run command, so it just saves development time.
WORKDIR /app/gedi-subsetter
COPY bin/subset.sh ./bin/

WORKDIR /app
