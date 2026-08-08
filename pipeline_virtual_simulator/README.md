# Virtual Pipeline Leak Simulator

## Install and run on Windows

Open Command Prompt inside this folder:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:

- Simulator: `http://127.0.0.1:5001`
- Live JSON API: `http://127.0.0.1:5001/api/latest`

You can also double-click `RUN_SIMULATOR.bat`.

## Recommended demo sequence

1. Select **Normal — No leak** and press **Start simulation**.
2. Explain that inlet/outlet pressure and flow are nearly balanced.
3. Select **Leak in Zone 3** and set severity to 60%.
4. Show the destination pressure and flow dropping.
5. Show Zone 3 turning red, confidence, severity and probability map.
6. Turn the pump OFF briefly to show that pump context prevents a false alarm.
7. Turn the pump ON and finish with Zone 3.

## Connect Monika's dashboard

Read live values from:

```text
GET http://127.0.0.1:5001/api/latest
```

Example JavaScript:

```javascript
async function loadData() {
  const response = await fetch('http://127.0.0.1:5001/api/latest');
  const data = await response.json();
  console.log(data);
}
setInterval(loadData, 1000);
```

For another laptop on the same hotspot, run `ipconfig`, find this laptop's IPv4 address, and replace `127.0.0.1` with that address. Allow Python through the Windows private-network firewall if prompted.

## Honest judge statement

“This is a virtual proof of concept. It generates controlled synthetic readings to validate our end-to-end data flow, feature extraction, zone prediction and dashboard integration. Final accuracy will be measured only after collecting real sensor data from the physical pipeline prototype.”
