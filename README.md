# QGIS Map Automation

Standalone PyQGIS scripts that turn sugarcane **gap detection** results into
print-ready A1 maps (PDF/JPG) — no manual work in the QGIS layout designer.
Each script loads the source layers, applies the QML styles in [`qml/`](qml/),
builds the layout (main map, index map, legend, summary table) and exports one
map per PID, cluster or farm.

Two companies are supported, referred to in the code only by their aliases
`c1` and `c2`. Their real codes, names and data paths live in a local
`config.yaml` that is **not** committed — see [Configuration](#configuration).

## Map products

| Script | Level | Output |
|---|---|---|
| [`qgis-3.44.15/qgis3.44.15_layout_farm-level_c1.py`](qgis-3.44.15/qgis3.44.15_layout_farm-level_c1.py) | Farm (`c1`) | `<company>_Farm <n>_Crop Establishment Map.pdf` |
| [`qgis-3.44.15/qgis3.44.15_layout_farm-level_c2.py`](qgis-3.44.15/qgis3.44.15_layout_farm-level_c2.py) | Farm (`c2`) | `<company>_Farm <n>_Crop Establishment Map.pdf` |
| `qgis-4.0.3/qgis3.34.10_layout_pid_v0*_c*.py` | PID (paddock) | `<PID>_Gap Detection Map` |
| `qgis-3.34.10/qgis3.34.10_layout_cluster-planting*.py` | Cluster planting | `<cluster>_Gap Detection Map_<date>.pdf` |
| `qgis-3.34.10/qgis3.34.10_layout_pt*.py`, `..._monthly-update.py` | Company (PT) | Company-wide / monthly maps |

> The folder name is the QGIS version the scripts were last run with. The
> scripts in `qgis-3.34.10/` and `qgis-4.0.3/` still import `fiona`, which the
> QGIS 3.44.15 install does not ship (see [Troubleshooting](#troubleshooting)).

### Farm-level Crop Establishment Map

Two A1 landscape pages per farm, run for every farm that has commercial gap
detection results:

**Page 1 — Growth & Gap.** Commercial plantings coloured growth (green) / gap
(red), seed plantings (orange), planted-but-not-yet-analysed areas (Next
Target), roads, drainage, water bodies, paddock boundaries with PID labels and
the farm boundary (bold black). The table lists, per block:

| Column | Source |
|---|---|
| Total Area | CU + CP paddock area |
| Planted Area | CP paddock area (`c1`) · planting polygons (`c2`) |
| Growth / Gap Area | `cls = 'plant'` / `'gaps spot'` of commercial gap features |
| Growth % / Gap % | growth (gap) ÷ (growth + gap) — `-` if the block has no analysis |

**Page 2 — Growth Classification.** Growth % is computed per
`cluster_planting` (plant ÷ (plant + gap)) and each cluster is coloured by
class. The table gives the analysed area and share per class.

| Class | Colour |
|---|---|
| <60% | `#FFC526` |
| 60–80% | `#F37835` |
| 80–90% | `#00AEDB` |
| >90% | `#00B159` |

Classes and colours are defined once in `GROWTH_CLASSES`
([`lib/legend_img.py`](lib/legend_img.py)).

**`c1` vs `c2` differences**

| | `c1` | `c2` |
|---|---|---|
| Commercial vs seed | planting `Status`: `Commercial Plantation` / `Seed Production` | `COMMERCIAL_FILTER_MODE`: `'date'` (plant_date ≥ `COMMERCIAL_DATE_CUTOFF`, default) or `'status'` (`Commercial` / `Seed`) |
| Planted area / Next Target | paddock `LANDUSETYP = 'CP'` | planting polygons (mechanized + manual), dissolved — `c2` has no CP paddocks |
| Main map extent | farm boundary | the farm's gap detection features (commercial + seed) + 10% |
| Drainage category field | `TIPE` | `DRAIN_TIPE` (remapped automatically) |

## Repository layout

```
config.example.yaml  template for config.yaml (dummy values)
config.yaml          your local copy: paths per company, QGIS path (git-ignored)
lib/                 helpers: table/legend image rendering, planting loader
  tmp/               intermediate GeoPackages, rebuilt every run (git-ignored)
qml/                 QGIS layer styles
img/                 static legend images
qgis-<version>/      layout scripts (see Map products)
pid_error_logs/      per-run error logs, one file per day (git-ignored)
```

## Requirements

- **QGIS 3.44.15 LTR** (Windows, OSGeo4W build). Scripts run with its bundled
  Python: `C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat`
- Python packages, all bundled with that QGIS install: `geopandas`,
  `pyogrio`, `pandas`, `numpy`, `matplotlib`, `Pillow`, `PyYAML`

## Configuration

Everything machine- or data-specific lives in `config.yaml`, which is
git-ignored so company names and paths never reach the repository. Start from
the template:

```bat
copy config.example.yaml config.yaml
```

then fill in the real values. The keys used by the farm-level scripts:

```yaml
qgis_apps: C:/Program Files/QGIS 3.44.15/apps/qgis-ltr

companies_alias:
  c1: "COMPANY_A"        # key under `companies:`, also the output file prefix
  c2: "COMPANY_B"

companies:
  COMPANY_A:
    map_path                : C:/path/to/maps/COMPANY_A/
    landuse_path            : .../60_landuse.gdb          # Farm, Block, paddock
    infra_path              : .../50_infrastructure.gdb   # road, drainage
    planting_path           : .../20_planting.gdb         # mechanized, manual
    gpkg_gaps_planting_path : .../Gaps-Detection_Planting_AR.gpkg
  COMPANY_B:
    map_path                : C:/path/to/maps/COMPANY_B/
    landuse_path            : .../60_landuse.gdb
    infra_path              : .../50_infrastructure.gdb
    planting_gdb_path       : .../20_planting.gdb         # farm-level script
    planting_path           : .../planting.parquet        # PID scripts
    gpkg_gaps_planting_path : .../Gaps-Detection_Planting_AR.gpkg
```

When a new data delivery arrives (a new dated folder), point the `.gdb` paths
at it — the `.gdb` file names stay the same. The gap GeoPackage's **last
layer** is always used (layers are named by date).

All layers are expected in **EPSG:32754** (WGS 84 / UTM 54S).

## Running

From the repository root (or wrap this line in a `.bat` file to double-click):

```bat
"C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat" qgis-3.44.15\qgis3.44.15_layout_farm-level_c1.py
```

Farm-level PDFs are written to `<map_path>/farm_<YYYYMMDD>/`. Set
`EXPORT_FORMATS = ['pdf', 'jpg']` at the top of a script to also export JPG
(300 dpi, one file per page: `<name>.jpg`, `<name>_2.jpg`).

A farm (or PID) that fails is logged to
`pid_error_logs/farm_error_log_<YYYYMMDD>.txt` and the run continues with the next one.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'fiona'` | QGIS 3.44.15 ships `pyogrio`, not `fiona`. Replace `fiona.listlayers(path)` with `[l[0] for l in pyogrio.list_layers(path)]` (as the farm-level scripts do). |
| `... does not exist in the file system` | A path in `config.yaml` points to a drive/folder that isn't there (e.g. old `D:` paths). |
| `TopologyException: side location conflict` | Invalid polygons in the source data; repair with `.buffer(0)` before `dissolve` (done for `c2` planting). |
| Drainage not drawn | `drainageStyle.qml` categorizes on `TIPE`; the source uses a different field name. |

## License

[MIT](LICENSE)
