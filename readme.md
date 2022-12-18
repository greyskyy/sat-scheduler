# Satellite coverage

This repository is still under construction and should be considered in an *alpha* state.

TODO remaining before MVP:
* [] compute orbit rev boundaries and evaluate duty-cycle per rev, rather than total interval
* [] add sun-elevation constraint at payload boresight point (nadir point for pushbroom)

Additional, non-MVP remaining tasks:
* [] generate coverage report in CZML and in csv
* [] adjust score to prefer non-covered areas, penalizing repeating coverage

## tl;dr

Build and activate the conda environment from the `environment.yaml`

```bash
mamba env create -f environment.yaml
mamba activate sat-scheduler
python src --help

python src [tool] --help
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

Preprocess the AOIs, propagating ephemeris, and compute time intervals when each AOI is within each sensor's FOV footprint.

This tool performs the following steps:

1. steps 1-3 from [list-aois](#list-aois), above.
2. propagate ephemeris, computing payload field-of-view intervals for each aoi.
3. generate output csvs and czml files

### pushbroom

Schedule payload activities for each AOI, according to payload constraints and priority, generating a payload schedule for each payload. This scheduler assumes a fixed-attitude (nadir-pointing) payload that doesn't articulate.

This tool performs the following steps

1. load aois as in steps from [list-aois](#list-aois), above
2. compute in-view intervals, as described in step 2 from [preprocess](#preprocess) above
3. score each AOI, according to aoi priority and the score equation
4. generate a schedule for each aoi
5. generate output csvs, reports, and czml files

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