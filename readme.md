# Satellite coverage

## tl;dr

Build and activate the conda environment from the `environment.yaml`

```bash
mamba env create -f environment.yaml --name sat-scheduler
mamba activate sat-scheduler
python src/satscheduler
```

## Developers

Recreate the `environment.yaml` as follows:

```bash
mamba env export --from-history | grep -vi '^prefix:' > environment.yaml
```