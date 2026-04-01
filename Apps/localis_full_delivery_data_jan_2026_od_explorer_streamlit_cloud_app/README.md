# ✈️ Localis Sampledata — Passenger App

Hi team,

We've built an interactive data app for exploring Victoria passenger travel corridors. Your feedback is welcome before wider sharing.

**🔗 App:** [PASTE YOUR STREAMLIT CLOUD URL HERE]

---

## What is this app?

The **Localis Sampledata Passenger App** analyses origin–destination (OD) trip data across Victoria, sourced from Localis mobile movement data. It lets you explore which corridors carry the most demand, when people travel, and whether trips are commuter or leisure-driven — all interactively, no code required.

> Data covers Victoria LGA-level trips of ≥ 70 km, with weekday/weekend and peak-hour breakdowns.

---

## Pages & Features

| Page | What it shows |
|------|--------------|
| 🗺️ **Network Flow Map & Rankings** | Arc flow map of all corridors, ranked bar chart, tourism region heatmap, LGA OD matrix, 24-hour demand curve, corridor intensity, distance vs volume scatter |
| 🔍 **Single Corridor Deep Dive** | Pick any origin–destination pair — full corridor metrics + hourly weekday/weekend travel profile |
| 📋 **Browse Raw Trip Records** | Explore trip-level records, filter by LGA and date range, download filtered extracts |
| 🛣️ **Live Corridor Statistics** | Dynamic OD flow map, peak hour share, weekday vs weekend split, DoW × hour heatmap, OD matrix |

---

## How to Use

1. Open the link above — runs in your browser, no install needed
2. Select a page from the **left sidebar**
3. Use sidebar filters (Top N corridors, time period, origin/destination LGA, date range) to focus your analysis
4. **Hover** over any chart for details — all charts are fully interactive
5. Click the **ℹ** button next to any chart header to read what it shows and when to use it
6. Use **Download** buttons at the bottom of each page to export filtered CSVs

> **Note — pages 3 & 4 (Browse Trips / Live Statistics):**
> On first load these pages download the trip dataset from Google Drive (~755 MB).
> A progress indicator will show. Once downloaded it is cached for the session — subsequent visits are instant.

---

## Testing Checklist

- [ ] All 4 pages load without errors
- [ ] Sidebar filters update charts correctly
- [ ] ℹ info popovers display on every chart
- [ ] Download buttons produce correct CSVs
- [ ] Pages 3 & 4: download message appears → page loads after download completes

Please share any issues or feedback in [YOUR CHANNEL / EMAIL]. Screenshots of errors are very helpful.

---

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Place data files in `output/` before running locally.
