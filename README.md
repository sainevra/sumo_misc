# 🚦 SUMO City-Scale Traffic and EV Charging Examples

This repository provides reproducible SUMO resources for city-scale traffic stress testing and electric-vehicle (EV) charging-station modelling. It accompanies the research workflow presented in **“A SUMO-Based Framework for City-Wide Traffic Modelling with Electric Vehicle Charging Infrastructure.”**

The repository includes:

- 🧩 a Python script that inserts lateral charging-station structures into an existing SUMO scenario;
- 🧪 a synthetic charging-station capacity experiment; and
- 🌆 a large-scale Seville traffic stress-test scenario.

> ⚠️ **Research prototype:** the included scenarios are designed for methodological and stress-testing purposes. The traffic demand is synthetic and should not be interpreted as a calibrated reproduction of real traffic conditions.

## 📬 Contact

For questions, issues or collaboration related to this repository, please contact:

**Juan Alberto Gallardo-Gómez**  
Universidad de Sevilla  
[jgallardo7@us.es](mailto:jgallardo7@us.es)

## 📦 Repository contents

```text
sumo_misc/
├── README.md
├── run_sumo_with_cs.py
├── cs_example/
│   ├── infrastructure.add.xml
│   ├── network.con.xml
│   ├── network.edg.xml
│   ├── network.net.xml
│   ├── network.netccfg
│   ├── network.nod.xml
│   ├── network.tll.xml
│   ├── routes.rou.xml
│   └── simulation.sumocfg
└── seville_simulation.zip
```

### 🧩 `run_sumo_with_cs.py`

The script inserts one or more charging stations into a SUMO network defined through plain XML files. For every selected road edge, it:

1. creates a timestamped working copy of the input scenario;
2. splits the original edge into two consecutive segments;
3. generates a lateral charging facility connected to the main road;
4. adds internal access, charging and return lanes;
5. creates reservable `parkingArea` elements and associated `chargingStation` elements;
6. rewrites routes that previously crossed the modified edge;
7. updates connection and traffic-light logic files;
8. rebuilds the network with `netconvert`; and
9. launches the resulting SUMO simulation.

The original input scenario is preserved because all modifications are applied inside a new folder under `runs/`.

### 🧪 `cs_example/`

This folder contains a complete synthetic charging-station capacity experiment. Its default configuration represents:

| Parameter | Value |
|---|---:|
| Charging-station size | 50 charging spaces |
| Charging blocks | 10 blocks × 5 spaces |
| Load factor | 3 |
| EV demand | 150 vehicles over one hour |
| Approximate charging duration | 20 minutes per EV |
| Teleporting | Disabled |
| Main outputs | `chargingevents.xml`, `vehroute.xml`, `stats.xml`, `edgedata.xml` |

The experiment is designed to evaluate whether the proposed station can absorb EV demand without blocking its entrance or the surrounding road network.

### 🌆 `seville_simulation.zip`

This archive contains the selected city-scale traffic stress-test scenario used for the Seville case study:

| Parameter | Value |
|---|---:|
| Traffic demand | 150,000 vehicles |
| Simulation period | 17 hours, from 06:00 to 23:00 |
| Periodic rerouting | Every 120 s |
| Time-to-teleport | 300 s |
| Purpose | Large-scale network robustness and performance test |

The scenario uses synthetic origin-destination demand and is intended as a reproducible stress test rather than a calibrated traffic model.

## ✅ Requirements

- Python 3
- Eclipse SUMO installed
- `sumo`, `sumo-gui`, and `netconvert` available in the system `PATH`

The charging-station generator uses only the Python standard library, so no additional Python packages are required.

Verify the SUMO installation with:

```bash
sumo --version
sumo-gui --version
netconvert --version
```

## 🚀 Installation

```bash
git clone https://github.com/sainevra/sumo_misc.git
cd sumo_misc
```

## ▶️ Running the charging-station example

The repository is already configured to use `cs_example/`, generate a station with 50 charging spaces on edge `e6`, rebuild the network, and open the simulation in `sumo-gui`.

Linux/macOS:

```bash
python3 run_sumo_with_cs.py
```

Windows:

```powershell
py run_sumo_with_cs.py
```

A timestamped directory is created under:

```text
runs/
```

For example:

```text
runs/YYMMDD-N_8816/
```

The generated network, updated routes and connections, configuration files, parameter summary, and SUMO outputs are stored in this run directory.

To run without the graphical interface, change:

```python
SUMO_BINARY = "sumo-gui"
```

to:

```python
SUMO_BINARY = "sumo"
```

## ⚙️ Script configuration

Edit the configuration block at the beginning of `run_sumo_with_cs.py`.

| Variable | Description |
|---|---|
| `SUMO_BINARY` | SUMO executable: `sumo` or `sumo-gui` |
| `NETCONVERT_BINARY` | `netconvert` executable |
| `INPUT_FOLDER` | Folder containing the source SUMO scenario |
| `CONFIG_FILE_NAME` | SUMO configuration file |
| `NODES_FILE_NAME` | Plain node file |
| `EDGES_FILE_NAME` | Plain edge file |
| `CON_FILE_NAME` | Plain connection file |
| `TLL_FILE_NAME` | Traffic-light logic file, when available |
| `ADDITIONAL_FILE_NAME` | Additional infrastructure file |
| `NETWORK_FILE_NAME` | Generated SUMO network |
| `ROUTES_FILE_NAME` | Route or trip file to update |
| `CS_LIST` | Edge IDs where charging stations will be inserted |
| `CS_SIZE` | Total number of charging spaces per generated station |
| `CS_POWER` | Charging-station power configuration; the current generator uses the first value as power in watts |
| `RUN_PORT` | Identifier appended to the run directory |

Example:

```python
SUMO_BINARY = "sumo-gui"
INPUT_FOLDER = "cs_example/"

CS_LIST = [
    "e6",
]

CS_SIZE = 50
CS_POWER = [150000, 1.0]
```

The current charging-block design provides five spaces per block. Therefore, `CS_SIZE` should normally be a multiple of five.

## 🛠️ Applying the generator to another SUMO scenario

The script expects a scenario represented by SUMO plain files. If only a `.net.xml` file is available, the corresponding plain files can be exported with `netconvert` before running the generator.

The input folder should contain, or be configured to reference:

```text
*.nod.xml       nodes
*.edg.xml       edges
*.con.xml       connections
*.tll.xml       traffic-light logic, when applicable
*.add.xml       additional elements
*.rou.xml       routes or trips
*.sumocfg       simulation configuration
```

Then:

1. update the file names in the configuration block;
2. add the target edge IDs to `CS_LIST`;
3. choose a `CS_SIZE`;
4. select `sumo` or `sumo-gui`; and
5. run the script.

After generation, the resulting network should be visually inspected with `netedit` or `sumo-gui`, particularly when charging stations are inserted into complex urban roads, junctions, roundabouts, or short edges.

## 🗺️ Running the Seville stress-test scenario

Extract the archive:

```bash
unzip seville_simulation.zip -d seville_simulation
```

Enter the extracted scenario directory and run the included SUMO configuration:

```bash
sumo-gui -c simulation.sumocfg
```

For headless execution:

```bash
sumo -c simulation.sumocfg
```

The large scenario may require substantial CPU time and memory depending on the SUMO version, hardware, enabled outputs, and graphical rendering.

## 🔌 Charging-station design

The generated facility is placed laterally with respect to the selected road edge so that charging vehicles do not stop directly on the main traffic lane. The layout includes:

- a Y-shaped access and exit structure;
- independent charging blocks;
- three forward lanes per charging block;
- dedicated return and interconnection lanes;
- reservable parking areas;
- charging stations associated with those parking areas; and
- route and connection updates that preserve through traffic on the original road corridor.

Each charging block currently contains five charging spaces. The parking length is calculated using an assumed vehicle length of 5 m and a 2 m separation between consecutive vehicles:

```text
5 vehicles × 5 m + 4 gaps × 2 m = 33 m
```

## 📊 Main outputs of the charging experiment

The provided configuration produces:

- `chargingevents.xml`: charging start/end times and delivered energy;
- `vehroute.xml`: vehicle routes, rerouting events, stops, departures and arrivals;
- `stats.xml`: aggregate simulation and vehicle statistics; and
- `edgedata.xml`: edge-level traffic, waiting-time and speed indicators.

These outputs can be used to calculate metrics such as:

- travel time excluding the fixed charging duration;
- mean and 95th-percentile delay;
- accumulated waiting time at the station entrance;
- vehicles served per hour;
- charger utilisation; and
- internal rerouting and queue formation.

## ⚠️ Limitations

- The provided demand is synthetic.
- Charging-station geometry is generated algorithmically and should be checked for each target edge.
- Very large charging stations may become limited by entrance and internal-circulation capacity rather than by the number of chargers.
- The current architecture assumes blocks of five charging spaces.
- Results may vary across SUMO versions and operating systems.
- Calibration and validation against observed traffic and charging data are outside the scope of the included examples.

## 📚 Citation

If you use this repository in academic work, please cite the associated paper when its final reference becomes available:

> J. A. Gallardo-Gómez et al., “A SUMO-Based Framework for City-Wide Traffic Modelling with Electric Vehicle Charging Infrastructure,” forthcoming.

SUMO should also be cited according to the recommendations of the Eclipse SUMO project.

## 🙏 Acknowledgements

This work is part of the projects **SAINEVRA** (`PID2023-151065OB-I00`) and **ATopEH** (`PID2023-147795NA-I00`), funded by the Spanish Ministerio de Ciencia, Innovación y Universidades and Agencia Estatal de Investigación (`MCIN/AEI/10.13039/501100011033`).

## 📄 License

`run_sumo_with_cs.py` declares the **Eclipse Public License 2.0 (EPL-2.0)** in its source header. See the source file for details.
