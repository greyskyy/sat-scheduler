# Satellite coverage

## tl;dr

Build and activate the conda environment from the `environment.yaml`

```bash
conda env create -f environment.yaml --name <your env name>
conda active <your env name>
python src/main/python3/main.py
```

## Developers

Recreate the `environment.yaml` as follows:

```bash
conda env export --from-history | grep -vi '^prefix:' > environment.yaml
```