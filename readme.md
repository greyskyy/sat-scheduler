# Satellite coverage

## tl;dr

Build and activate the conda environment from the `environment.yaml`

```bash
mamba env create -f environment.yaml --name sat-scheduler
mamba activate sat-scheduler
python src/satscheduler
```

## Tools

This scheduler provides several tools which provide insight to the scheduling process.  These tools are described here:

### list-aois

Load and process the AOIs, rendering them into outputs.  Use this tool to visualize the AOIs, ensuring the input areas of interest
are correctly loaded. Note that by default only HTML output is generated.  Use the `--czml` option to generate CZML output.

This tool performs the following steps:

1. load the aoi data
2. pad the boundary by the specified buffer
3. simplify any edges
4. generate html and czml output

To view the czml output, simply navigate a browser to a [czml viewer](https://cesium.com/cesiumjs/cesium-viewer/) and drag the 
czml output file into the display. The viewer will automatically load and and display the file.

### preprocess

## Configuration

Scheduler configuration is primarily accomplished through the use of a yml configuration file. By
default, this file is `config.yaml` in the current working directory. It can be explictly set by using
the `--config` option.

This config file contains the AOIs to load, the satellite orbit(s), and payload definitions.  See the [example file](config.yaml).

### Sections

#### run

#### aois

```yml
aois:
  url: https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip
  buffer: "20km"
  color: '#FF0000'
  labels: true
  font: "11pt Lucida Console"
```

* *url* - the URL to any file loading by geopandas. Currently it must provide the following data colums:
    * CONTINENT
    * ADMIN
    * ISO_A2
    * ISO_A3
    * geometry (obviously)
* *buffer* - The amount to buffer the provided AOI boundaries. Must not be negative, unitless numbers are parsed as meters.
* *color* - The RGB hex string for the color to use when generating czml
* *labels* - Flag indicating whether the labels should be included in the czml output
* *font* - Label font to use in the czml output

#### satellites

#### earth

#### control

## Developers

Recreate the `environment.yaml` as follows:

```bash
mamba env export --from-history | grep -vi '^prefix:' > environment.yaml
```