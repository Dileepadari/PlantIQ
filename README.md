<p align="center">
  <img src="src/static/images/logo-mark.png" alt="" width="96" />
</p>

# PlantIQ

A plant health monitor for an experimental farm. Six sensors on an ESP32 watch a
plant's air, soil and light; PlantIQ reads them back, compares every value
against the safe range for that plant species, and raises an alert when one
drifts out.

The point is early warning. A plant under pathogen attack changes the volatile
organic compounds it releases into the air before it looks unwell, so a VOC
sensor read alongside temperature, humidity, soil moisture, light and CO2
catches trouble while there is still time to act.

Building or changing the code? See [DEVDOC.md](./DEVDOC.md).

---

## What it measures

| Sensor | Reads | How it works |
|---|---|---|
| DHT11 | Temperature, humidity | A humidity-sensitive polymer and a thermistor, both read as resistance changes |
| Capacitive probe | Soil moisture | Dielectric permittivity of soil rises with water content |
| SGP30 | CO2, VOC | A metal-oxide film changes conductivity in the presence of the target gases |
| LDR | Light intensity | Photoconductivity: resistance falls as incident light rises |

## Getting in

Register with an email, a password and the plant you are growing, or sign in
with the demo account shown on the login page to look around without creating
anything.

Your account carries two settings that shape what you see: the **plant** being
monitored, which decides the safe ranges every reading is judged against, and
the **number of readings** to chart, which sets how far back the graphs go.

## The pages

### Dashboard
Every sensor's current value as a tile, with a bar showing where the reading
sits in its range, and the VOC trend below. A threshold table shows each sensor
against the safe range for your plant, and the newest alerts sit beside it.

Tiles refresh on their own every 30 seconds. If the device has not reported
recently the page says so plainly and labels the readings as the most recent on
the channel rather than live ones - a monitoring page that quietly shows stale
numbers is worse than one that shows none.

### Statistics
One chart per sensor over your chosen window. Hover any chart to read the exact
value and time at that point.

### Analysis
Each of the six readings against the safe range stored for your plant, marked
**Healthy** or **Out of range**, with a count of each at the top. If your plant
has no threshold profile in the database, the page says which plants do.

### History
Pick a start and end date and load every reading the device recorded in
between. The table scrolls, missing sensor readings show as `--` rather than
zero, and the whole range exports as CSV.

If the range you picked is empty, PlantIQ tells you the date of the most recent
reading on the channel and offers to jump to it.

### Alerts
Threshold breaches the firmware reported, newest first, colour-coded by
severity. Dismiss them one at a time or clear the lot. The sidebar carries a
count of what is still open.

### Circuit
What each sensor is, how it connects to the ESP32, and the system diagram
showing the path from breadboard to dashboard.

### Settings
Change your display name, the plant being monitored and how many readings the
charts cover. The plant field suggests the species that actually have threshold
profiles, and refuses one that does not.

### About
What the project is, what each page does, and who built it.

## Theme

Light and dark both ship. The toggle sits in the top bar and your choice is
remembered on that browser; with no choice made, PlantIQ follows the operating
system setting.

## Alerts from the device

The ESP32 does the threshold comparison itself and posts an alert when a value
crosses. PlantIQ stores it, skips it if the same alert is already open, and
shows it on the Alerts page and in the sidebar count.

## Credits

Built by Adari Dileep Kumar, Gajawada Bharath, Chaganti Venkata Karthikeya and
Sallepalle Naga Revanth Reddy at IIIT Hyderabad, under Aakashavani.

Presentation decks are in [`ppts/`](./ppts). The OM2M middlenode used for the
IoT layer is vendored as a submodule in `OM2M_ESW/`.
