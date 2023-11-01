# GEDI Subsetter

## History
The GEDI Subsetter tool was developed in response to the release of GEDI data and the subsequent interest from the biomass group. The group expressed interest in studying an entire region, which required obtaining all granules that cover that area. Due to GEDI products being an orbit of the International Space Station (ISS), the challenge was to efficiently subset all granules passing through the area of interest. So while the existing methods would work for a small number of granules, the users were seeking a more streamlined approach that would allow them to efficiently gather their data points without the need to process each file separately.

## About GEDI
The Global Ecosystem Dynamics Investigation (GEDI) is a lidar instrument on the International Space Station that generates high-resolution laser ranging observations of the 3D features of the Earth. GEDI’s precise measurements of forest canopy height, canopy vertical structure, and surface elevation greatly advance our ability to characterize important carbon and water cycling processes, biodiversity, and habitat.

## The Subsetter
The Subsetter utilizes the Multi-Mission Algorithm and Analysis Platform’s (MAAP) async job queuing system that runs on AWS. The tool automatically handles authentication (AWS S3 direct access) and auto-refreshes tokens. Users are able to pass a number of inputs to the Subsetter’s job to refine the results. By querying NASA Common Metadata Repository (CMR) to gather all the granules that pass through a specified region, the Subsetter is able to parallelize the process to download the granules and then append the subsetted results to a single geopackage.

## Beyond
The Subsetter could be generalized to work with other datasets, pass back different data formats, directly read from S3, and more. The Subsetter is a great example of how MAAP can help users with their data processing needs.
