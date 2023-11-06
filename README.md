# GEDI Subsetter

## History

The GEDI Subsetter tool was developed in response to the release of [Global Ecosystem Dynamics Investigation](https://www.earthdata.nasa.gov/sensors/gedi) (GEDI) data and the subsequent interest from the [University of Maryland biomass group](https://geog.umd.edu/). The group expressed interest in studying various regions, which requires obtaining all granules that intersect any given region. Due to GEDI products being an orbit of the International Space Station (ISS), the challenge was to efficiently subset all granules passing through the area of interest. So while the existing methods would work for a small number of granules, the users were seeking a highly scalable, automated approach that would allow them to efficiently gather their data points without the need to process each file separately.

## About GEDI

GEDI is a [LIDAR](https://www.earthdata.nasa.gov/technology/lidar) instrument on the International Space Station that generates high-resolution laser ranging observations of the 3D features of the Earth. GEDI’s precise measurements of forest canopy height, canopy vertical structure, and surface elevation greatly advance our ability to characterize important carbon and water cycling processes, biodiversity, and habitat.

## The Subsetter

The Subsetter utilizes the Multi-Mission Algorithm and Analysis Platform’s (MAAP) async job queuing system that runs on AWS. The tool automatically handles authentication (AWS S3 direct access) and auto-refreshes tokens. Users are able to pass a number of inputs to the Subsetter’s job to refine the results. By querying NASA's Common Metadata Repository (CMR) to gather all the granules that pass through a specified region, the Subsetter is able to parallelize the process to download the granules and then append the subsetted results to a single [GeoPackage](https://www.geopackage.org/) (GPKG) file.

To read more about its specifications and usage in MAAP, please see the [MAAP Usage Guide](src/gedi_subset/MAAP_USAGE.md).

For contributing to the Subsetter, please see the [Contributing Guide](./CONTRIBUTING.md).

## Beyond

The Subsetter could be generalized to work with other datasets, pass back different data formats, directly read from S3, and more. The Subsetter is a great example of how MAAP can help users with their data processing needs. Future examples could demonstrate its usage outside of MAAP.
