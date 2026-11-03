# tuf2000-hub

DuPont hub PCB (78 x 50 mm, 2-layer) connecting an ESP32, a 5V→12V boost converter,
a TUF-2000M ultrasonic flow meter over RS485, and two DS18B20 temperature sensors
(each on its own GPIO with a 4.7k pull-up).

- `gen.py` — generates Gerbers, drill files, BOM and CPL into `out/`
- `drc.py` — clearance, connectivity and netlist check: `python3 drc.py out/geometry.json`
- `out/tuf2000-hub-gerbers.zip` — upload to the fab; `out/hub-BOM.csv` + `out/hub-CPL.csv` for assembly

ESP32 pins (match the ESPHome `heating-temperature-sensor` config): IO18 TX → DI, IO19 RX ← RO,
IO23 → DE+RE, IO17 → temp outlet (J8), IO15 → temp inlet (J9).

Requires: `pip install shapely Hershey-Fonts gerbonara`
