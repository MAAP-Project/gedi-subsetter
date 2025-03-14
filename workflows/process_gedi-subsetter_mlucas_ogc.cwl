cwlVersion: v1.2
$graph:
- class: Workflow
  label: gedi-subset
  doc: Subset GEDI L1B, L2A, L2B, L4A, or L4C granules within an area of interest
    (AOI)
  id: gedi-subset
  inputs:
    aoi:
      doc: URL of a file representing the Area of Interest (e.g., GeoJSON file)
      label: Area of Interest
      type: string
    doi:
      doc: 'Digital Object Identifier (DOI) of the GEDI collection to subset, or one
        of these logical names: L1B, L2A, L2B, L4A'
      label: Digital Object Identifier
      type: string
    lat:
      doc: Name of the dataset containing latitude values
      label: latitude
      type: string
    lon:
      doc: Name of the dataset containing longitude values
      label: longitude
      type: string
    columns:
      doc: One or more column names, separated by commas, to include in the output
        file
      label: columns
      type: string
    query:
      doc: Boolean query expression for subsetting the rows in the output file. If
        not provided, all rows are included.  See https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html.
      label: query
      type: string
    temporal:
      doc: Temporal range to subset, formatted as an ISO 8601 Time Interval. For example,
        2021-01-01T00:00:00Z/2021-12-31T23:59:59Z.  See https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.  If
        not provided, the entire temporal range of the GEDI collection is used.
      label: temporal
      type: string
    beams:
      doc: 'Which beams to include: all, coverage, power, or a comma-separated list
        of specific beam names, with or without the BEAM prefix (e.g., BEAM0000,BEAM0001
        or 0000,0001)'
      label: beams
      type: string
    limit:
      doc: Maximum number of GEDI granules to subset, regardless of the number of
        granules within the spatio-temporal range.
      label: limit
      type: string
    output:
      doc: Name of the output file produced by the algorithm.  Defaults to using the
        AOI file name (without the extension) with the suffix "_subset.gpkg".
      label: output
      type: string
    fsspec_kwargs:
      doc: JSON object representing keyword arguments to pass to the fsspec.core.url_to_fs
        function when reading granule data files.  See https://filesystem-spec.readthedocs.io/en/latest/api.html#fsspec.core.url_to_fs.
      label: fsspec_kwargs
      type: string
    processes:
      doc: Number of processes to use for parallel processing.  If not provided, defaults
        to the number of available CPUs.
      label: processes
      type: string
    scalene_args:
      doc: Arguments to pass to Scalene for memory and CPU profiling.  If not provided,
        Scalene will not be used.
      label: scalene_args
      type: string
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
        fsspec_kwargs: fsspec_kwargs
        processes: processes
        scalene_args: scalene_args
      out:
      - outputs_result
- class: CommandLineTool
  id: main
  requirements:
    DockerRequirement:
      dockerPull: ghcr.io/maap-project/gedi-subsetter:mlucas_ogc
    NetworkAccess:
      networkAccess: true
    ResourceRequirement:
      ramMin: 5
      coresMin: 1
      outdirMax: 20
  baseCommand: /app/gedi-subsetter/bin/subset.sh
  inputs:
    aoi:
      type: string
      inputBinding:
        position: 1
        prefix: --aoi
    doi:
      type: string
      inputBinding:
        position: 2
        prefix: --doi
    lat:
      type: string
      inputBinding:
        position: 3
        prefix: --lat
    lon:
      type: string
      inputBinding:
        position: 4
        prefix: --lon
    columns:
      type: string
      inputBinding:
        position: 5
        prefix: --columns
    query:
      type: string
      inputBinding:
        position: 6
        prefix: --query
    temporal:
      type: string
      inputBinding:
        position: 7
        prefix: --temporal
    beams:
      type: string
      inputBinding:
        position: 8
        prefix: --beams
    limit:
      type: string
      inputBinding:
        position: 9
        prefix: --limit
    output:
      type: string
      inputBinding:
        position: 10
        prefix: --output
    fsspec_kwargs:
      type: string
      inputBinding:
        position: 11
        prefix: --fsspec_kwargs
    processes:
      type: string
      inputBinding:
        position: 12
        prefix: --processes
    scalene_args:
      type: string
      inputBinding:
        position: 13
        prefix: --scalene_args
  outputs:
    outputs_result:
      outputBinding:
        glob: ./output*
      type: Directory
s:author:
- class: s:Person
  s:name: maap
s:contributor:
- class: s:Person
  s:name: maap
s:citation: https://github.com/MAAP-Project/gedi-subsetter.git
s:codeRepository: https://github.com/MAAP-Project/gedi-subsetter.git
s:dateCreated: 2025-03-14
s:license: https://github.com/MAAP-Project/gedi-subsetter/blob/main/LICENSE
s:softwareVersion: 1.0.0
s:version: mlucas/ogc
s:releaseNotes: None
s:keywords: ogc, gedi
$namespaces:
  s: https://schema.org/
$schemas:
- http://schema.org/version/9.0/schemaorg-current-http.rdf
