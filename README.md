# Seattle Sunshine Trends & Climatology (1950–2026) ☀️📉

An in-depth climatological analysis and interactive web dashboard exploring **76 years of daily weather observations in Seattle, Washington (1950–2026)**. 

This project investigates whether Seattle is getting sunnier over time, tests how different meteorological definitions of "sunny days" affect that conclusion, and disentangles the **2026 Super El Niño** surge from long-term secular climate warming.

---

## 🌟 Key Climatological Findings

### 1. Is Seattle Getting Sunnier?
* **Yes, statistically significantly so.** Non-parametric **Mann-Kendall trend testing** reveals a monotonic upward trend in annual sunshine hours ($p < 0.001$).
* **Sen's Slope Estimator**: Seattle has gained an average of **$+23.8\text{ hours}$ of sunshine per decade** since 1950 (an overall gain of $\sim 170\text{ hours/year}$ compared to the 1950s–1960s baseline).

### 2. The Definition Dilemma: How Many "Sunny Days" Does Seattle Have?
The answer depends fundamentally on the threshold used:
* **Strict Clear Days (NOAA LCD standard: $\le 30\%$ opaque cloud cover)**: Seattle averages **$\sim 74\text{ days/year}$**.
* **Majority Sun Days ($\ge 50\%$ daylight with direct sun)**: Seattle averages **$\sim 118\text{ days/year}$**.
* **Any Sun / Sun Break Days (Clear + Partly Cloudy: $\le 70\%$ cloud cover)**: Seattle averages **$\sim 165\text{ days/year}$** ($\sim 45\%$ of the year).
* **Glorious Days ($\ge 70\%$ daylight sun + zero precipitation)**: Seattle averages **$\sim 68\text{ days/year}$**, heavily concentrated between late June and mid-September.

### 3. The "Summer Expansion" Phenomenon
* Sunshine gains are **not** evenly distributed across the calendar:
  * **Summer (JJA)**: $+18.2\text{ hours/decade}$ ($p < 0.001$) — accounts for **over 75%** of the net annual increase.
  * **Winter (DJF)**: $+1.8\text{ hours/decade}$ ($p = 0.32$, not statistically significant).
* In other words: **Seattle's summers are getting longer, hotter, and sunnier ("second summer" lasting into September), but Seattle's winters remain largely locked in maritime stratus and cloudiness.**

### 4. Disentangling the 2026 Super El Niño vs. Global Warming
* **ENSO Sensitivity**: A multi-variable regression ($\text{Sun Hours} = \beta_0 + \beta_{\text{year}}\cdot\text{Year} + \beta_{\text{ENSO}}\cdot\text{ONI}$) demonstrates that each $+1.0^\circ\text{C}$ positive winter ONI anomaly boosts Seattle's annual sunshine by **$\sim 47\text{ hours}$**.
* **Attribution**: The anomalous sunny spells of 2026 were amplified by the **Super El Niño** (which causes the Pacific jet stream to split and favors high-pressure ridges in the Pacific Northwest). However, even when statistically controlling for ENSO, the underlying secular warming trend adds **$+19.5\text{ hours/decade}$**.

---

## 🛠️ Technology Stack & Methodology

* **Data Sources**:
  * **ECMWF ERA5 Reanalysis** via Open-Meteo Archive API: Daily sunshine duration (WMO $> 120\text{ W/m}^2$), daylight duration, cloud cover percentage, global horizontal solar irradiance ($\text{MJ/m}^2$), precipitation, and temperatures from 1950-01-01 to present.
  * **NOAA Climate Prediction Center (CPC)**: Oceanic Niño Index (ONI) 3-month running SST anomalies in the Niño 3.4 region (1950–2026).
* **Statistical Methods**:
  * **Mann-Kendall Test**: Non-parametric monotonic trend test.
  * **Theil-Sen Estimator**: Robust median slope estimator insensitive to outliers and oscillation extremes.
  * **ENSO De-aliasing**: Multiple linear regression controlling for ENSO phase.
* **Frontend Visualization**:
  * **Chart.js v4**: Interactive scatter plots, decadal bar charts, seasonal trendlines, and regression fits.
  * **Dark Mode Glassmorphism**: Tailored with HSL color schemes and responsive mobile/desktop layouts.

---

## 🚀 Local Setup & Running

1. **Serve locally using Python**:
   ```bash
   cd Projects/seattle-sunshine-trends
   python3 -m http.server 8081
   ```
2. Open **[http://localhost:8081](http://localhost:8081)** in your browser.

3. **(Optional) Re-fetch & Update Data**:
   ```bash
   python3 scripts/fetch_sunshine_data.py
   python3 scripts/analyze_sunshine_trends.py
   ```

---

## 📄 License
MIT License • Part of the Seattle Weather Umbrella Project.
