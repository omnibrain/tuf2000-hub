# tuf2000-hub

DuPont hub PCB (78 x 50 mm, 2-layer) connecting an ESP32, a 5V→12V boost converter,
a TUF-2000M ultrasonic flow meter over RS485, and two DS18B20 temperature sensors
(each on its own GPIO with a 4.7k pull-up).

- `gen.py` — generates Gerbers, drill files, BOM and CPL into `out/`
- `drc.py` — clearance, connectivity and netlist check: `python3 drc.py out/geometry.json`
- `out/tuf2000-hub-gerbers.zip` — upload to the fab; `out/hub-BOM.csv` + `out/hub-CPL.csv` for assembly

ESP32 pins: IO17 TX2 → DI, IO16 RX2 ← RO, IO4 → DE+RE, IO27 → temp 1, IO26 → temp 2.

Requires: `pip install shapely Hershey-Fonts gerbonara`
