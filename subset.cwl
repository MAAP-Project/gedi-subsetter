cwlVersion: v1.2

$namespaces:
  s: https://schema.org/
$schemas:
  - https://raw.githubusercontent.com/schemaorg/schemaorg/refs/heads/main/data/releases/9.0/schemaorg-current-http.rdf

s:author:
  - class: s:Person
    s:name: MAAP
s:citation: https://zenodo.org/doi/10.5281/zenodo.10019412
s:codeRepository: https://github.com/MAAP-Project/gedi-subsetter.git
s:commitHash: 399237b5e0dd7dc8c3ea680b170de31457b4aab0
s:contributor:
  - class: s:Person
    s:name: MAAP
s:dateCreated: 2026-03-16
s:keywords: [GEDI]
s:license: Apache-2.0
s:releaseNotes: None
s:softwareVersion: 0.13.0
s:version: 0.13.0

$graph:
  - class: Workflow
    id: gedi-subsetter
    label: GEDI Subsetter
    doc: |
      Subset GEDI L1B, L2A, L2B, L4A, or L4C granules within an area of interest (AOI)

    inputs:

      aoi:
        label: Area of Interest (AOI)
        type: File
        doc: >-
          URL of a file representing the Area of Interest (e.g., a GeoJSON file).

      doi:
        label: Collection Identifier
        type: string
        doc: >-
          Either the Digital Object Identifier (DOI) or the Concept ID of the
          GEDI collection to subset.  For convenience, one of these logical
          names may be specified instead: L1B, L2A, L2B, L4A, L4C.

      lat:
        label: Latitude Variable
        type: string?
        default: lat_lowestmode
        doc: >-
          Name of the variable (dataset) containing latitude values.

      lon:
        label: Longitude Variable
        type: string?
        default: lon_lowestmode
        doc: >-
          Name of the variable (dataset) containing longitude values.

      columns:
        label: Columns
        type: string
        doc: >-
          One or more column names, separated by commas, to include in the
          output file, each naming a variable (dataset) from the collection.

      query:
        label: Query Expression
        type: string?
        doc: >-
          Boolean query expression for subsetting the rows of data.  If not
          provided, all rows are included.  For details on query syntax, see
          https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html.

      temporal:
        label: Temporal Range
        type: string?
        doc: >-
          Temporal range to subset, formatted as an ISO 8601 Time Interval.
          For example, 2021-01-01T00:00:00Z/2021-12-31T23:59:59Z.  See
          https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.  If not provided,
          the entire temporal range of the GEDI collection is used.

      beams:
        label: Beams
        type: string?
        default: "all"
        doc: >-
          Which beams to include: all, coverage, power, or a comma-separated
          list of specific beam names, with or without the BEAM prefix (e.g.,
          BEAM0000,BEAM0001 or 0000,0001).

      limit:
        label: Limit
        type: int?
        default: 100_000
        doc: >-
          Maximum number of GEDI granules to subset, regardless of the number
          of granules within the spatio-temporal range.

      output:
        label: Output Filename
        type: string?
        doc: >-
          Name of the output file produced by the algorithm.  Defaults to using
          the AOI filename (without the extension) with the suffix `_subset`
          and the extension `.gpkg`, resulting in a GeoPackage file format.

          For example, if the AOI were `https://host/path/to/my_aoi.geojson`,
          the default output filename would be `my_aoi_subset.gpkg`.

          When a filename is supplied, it must include a file extension in order
          to infer the output format.  Supported formats inferred from file
          extensions are as follows:

            - FlatGeobuf: `.fgb`
            - GPKG (GeoPackage): `.gpkg`
            - (Geo)Parquet: `.parquet`

          For example, if you prefer a Parquet file as output, you would specify
          a value such as `my_aoi.parquet` (where `my_aoi` can be whatever name
          you prefer).

      tolerated_failure_percentage:
        label: Tolerated Failure Percentage
        type: int?
        default: 0
        doc: >-
          Integral percentage of individual granule subset failures tolerated
          before causing job failure.  For example, a value of 0 indicates that
          no individual granule failures are tolerated.  Thus, if an error is
          encountered during subsetting of any individual granule, the entire
          job will fail.

          Conversely, a value of 100 indicates that even if an error is
          encountered for every granule, the job will still succeed, resulting
          in an empty output file.

      fsspec_kwargs:
        label: "[Advanced] Keyword Arguments for fsspec configuration"
        type: string?
        default: "{}"
        doc: >-
          JSON object representing keyword arguments to pass to the
          fsspec.core.url_to_fs function when reading granule data files.  See
          https://filesystem-spec.readthedocs.io/en/latest/api.html#fsspec.core.url_to_fs.

      processes:
        label: "[Advanced] Number of Processes"
        type: int?
        default: 0
        doc: >-
          Number of processes to use for parallel processing.  If not provided, or
          a value less than 1 is provided, defaults to the number of available CPUs
          available on the provisioned instance.

      scalene_args:
        label: "[Advanced] Scalene Arguments"
        type: string?
        default: ""
        doc: >-
          Space-separated list of arguments to pass to Scalene for memory and CPU
          profiling.  If not provided, Scalene will not be used.

    outputs:
      out:
        type: Directory
        outputSource: process/outputs_result

    steps:
      process:
        run: '#main'
        in:
          aoi: aoi
          doi: doi
          lat: lat
          lon: lon
          columns: columns
          query: query
          temporal: temporal
          beams: beams
          limit: limit
          output: output
          tolerated_failure_percentage: tolerated_failure_percentage
        out:
          - outputs_result

  - class: CommandLineTool
    id: main

    requirements:
      DockerRequirement:
        dockerPull: gedi-subset:latest
      NetworkAccess:
        networkAccess: true
      ResourceRequirement:
        ramMin: 16
        coresMin: 4
        outdirMax: 20

    baseCommand: /app/gedi-subsetter/bin/subset.sh
    successCodes: [0]

    inputs:
      aoi:
        type: File
        inputBinding:
          position: 1
          prefix: --aoi
      doi:
        type: string
        inputBinding:
          position: 2
          prefix: --doi
      lat:
        type: string?
        default: lat_lowestmode
        inputBinding:
          position: 3
          prefix: --lat
      lon:
        type: string?
        default: lon_lowestmode
        inputBinding:
          prefix: --lon
          position: 4
      columns:
        type: string
        inputBinding:
          prefix: --columns
          position: 5
      query:
        type: string?
        inputBinding:
          prefix: --query
          position: 6
      temporal:
        type: string?
        inputBinding:
          prefix: --temporal
          position: 7
      beams:
        type: string?
        inputBinding:
          prefix: --beams
          position: 8
      limit:
        type: int?
        default: 100_000
        inputBinding:
          prefix: --limit
          position: 9
      output:
        type: string?
        default: ""
        inputBinding:
          prefix: --output
          position: 10
      tolerated_failure_percentage:
        type: int?
        default: 0
        inputBinding:
          prefix: --tolerated-failure-percentage
          position: 11
      fsspec_kwargs:
        type: string?
        default: "{}"
        inputBinding:
          prefix: --fsspec-kwargs
          position: 12
      processes:
        type: int?
        default: 0
        inputBinding:
          prefix: --processes
          position: 13
      scalene_args:
        type: string?
        default: ""
        inputBinding:
          prefix: --scalene
          position: 14

    outputs:
      outputs_result:
        type: Directory
        outputBinding:
          glob: ./output*
