cwlVersion: v1.2
$graph:
- class: Workflow
  label: gedi-subset
  doc: Subset GEDI L1B, L2A, L2B, L4A, or L4C granules within an area of interest
    (AOI)
  id: gedi-subset
  inputs:
    aoi:
      doc: URL to a GeoJSON file representing your area of interest. This may contain
        multiple geometries, all of which will be used.
      label: Area of Interest
      type: string
    doi:
      doc: Digital Object Identifier (DOI) or Concept ID of the GEDI collection to
        subset, or a logical name representing such an ID.
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
        file. These names correspond to the datasets (which might also be referred
        to as variables or layers in the DOI documentation) within the data files,
        and vary from collection to collection.
      label: columns
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
  outputs:
    outputs_result:
      outputBinding:
        glob: ./output*
      type: Directory
s:author:
- class: s:Person
  s:name: MAAP
s:contributor:
- class: s:Person
  s:name: MAAP
s:citation: https://zenodo.org/records/15284245
s:codeRepository: https://github.com/MAAP-Project/gedi-subsetter.git
s:dateCreated: 2025-06-17
s:license: https://github.com/MAAP-Project/gedi-subsetter/blob/main/LICENSE
s:softwareVersion: 1.0.0
s:version: mlucas_ogc
s:releaseNotes: None
s:keywords: OGC, GEDI
$namespaces:
  s: https://schema.org/
$schemas:
- https://raw.githubusercontent.com/schemaorg/schemaorg/refs/heads/main/data/releases/9.0/schemaorg-current-http.rdf
