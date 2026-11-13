# 5-minute demo script

**Setup (before you start):** app running with default settings (ElasticNet, all zones, 42-month horizon through
Dec 2027, base month Jun 2024). Open the *Compare runs* tab once to confirm there is a baseline. Browser zoom ~110 %
for the room. In *Results & export*, the "Forecast by year" table shows 2025-2027 for every zone.
If using the cloud URL, open it a few minutes early so it is awake.

All numbers below were produced by the app itself with the default settings.

| Time | What to show | What to say / point out |
|---|---|---|
| 0:00 - 0:40 | **Header and metric cards.** Predicted AQI **155.0**, category *Unhealthy*, model test R² 0.9636. | "This is a digital twin of 10 city zones built from 9 smart-city datasets. A trained model predicts AQI, and I can change city conditions and see the effect." |
| 0:40 - 1:20 | **Zones tab.** | Technology Park is *Hazardous* (observed 500, predicted ~457); the other nine zones sit between ~92 and ~134. "It skews the city average, so zone-level views matter." |
| 1:20 - 2:00 | **Forecast tab**, *Zoom to forecast* on. Drag **Traffic volume** to **-50 %**. | The scenario line drops below the dashed no-change line: Scenario AQI **153.3 (-1.8, -1.1 %)**. "Results update live. The effect is modest, which is realistic for a single lever." Click **Run Simulation** (saves Run 1 = traffic -50 %). |
| 2:00 - 3:00 | **Presets.** Pick *EV Push* → Run (Run 2: **-1.8**). Pick *Clean Energy* → Run (Run 3: **-3.4, -2.2 %**). Pick *Combined Green Policy* → Run (Run 4: **-3.1**). | "Clean Energy is the strongest lever in this model." Be candid that the combined policy (-3.1) is *not* better than Clean Energy alone: the model is not additive because some coefficients partly offset. |
| 3:00 - 3:45 | **Compare runs tab.** | Overlay of the pinned baseline and Runs 1-4 plus the comparison table. Toggle *Show observed history* to switch between the zoomed forecasts and full context. "This is how I judge which policy is most effective." |
| 3:45 - 4:25 | **Model sensitivity.** Click **Reset**, choose **Lasso**, set Traffic **-30 %** → yellow warning, change is 0.0. Then choose **Linear Regression**, set Traffic back to 0, expand *Sensor overrides* and set **PM2.5 -30 %** → **-4.6 (-2.9 %)**. | "Lasso, the best model by R², shrank the traffic coefficient to zero, so it cannot answer traffic questions; the app warns about that. Model choice matters." (With ElasticNet the same PM2.5 cut goes the wrong way, +0.6 - so use linear models for sensor what-ifs.) |
| 4:25 - 4:45 | **Validation and export.** Clear all zones → friendly error. Re-add them. *Results & export* tab → download CSV. Click **Reset**. | "Inputs are validated and everything exports to CSV." |
| 4:45 - 5:00 | **Close.** | Summarise: notebook twin → tested package → interactive UI → deployable (Docker, CI). |

## Likely questions and honest answers

- **Why is R² ≈ 0.9999?** AQI is computed from PM10, PM2.5, NO2, SO2, O3 and CO, which are also model inputs
  (plus AQI lags), so the model largely re-derives the formula. Predictive accuracy is real, but it is not evidence of
  causal what-if accuracy.
- **Why are the effects small?** A what-if changes one month's drivers while lags and rolling features stay fixed, and
  the models are statistical, not causal or physical. Treat results as relative, not absolute, impact.
- **Why ElasticNet by default?** It is what the notebook uses for what-if analysis and responds to the policy levers;
  Lasso is more accurate on the test set but ignores most of them.
- **Can the forecast show seasonality / what does 2027 look like?** Only weakly - the forecast varies month/sin/cos
  terms and holds the rest constant, so 2025-2027 are nearly flat (e.g. Downtown about 121 AQI every year).
  It extends the latest state; it is not a trend forecast (documented limitation).
- **How do you know the app matches the notebook?** Parity tests compare the extracted twin against the notebook's
  saved forecasts, policy results and the ElasticNet traffic table.
