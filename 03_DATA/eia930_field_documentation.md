# EIA-930 documentation notes (verbatim quotations)

**Primary source:** U.S. EIA, "About the EIA-930 data", https://www.eia.gov/electricity/930-content/about.html. Retrieved 2026-10-22 with a direct HTTP GET (status 200); HTML tags were stripped locally. The page has no date or version stamp. Quotations below are copied verbatim from the retrieved text, except that HTML entities have been decoded (for example, `&mdash;` becomes an em dash) and line wraps have been joined. BibTeX key: `eia930about`.

**Secondary source:** U.S. EIA, "EIA-930 Hourly and Daily Balancing Authority Operations Report: Data Format and Transmittal Instructions" (OMB No. 1905-0129, expiration 07/31/2029), https://www.eia.gov/survey/form/eia_930/instructions.pdf. Quotations are transcribed from the rendered PDF pages. BibTeX key: `eia930instructions`.

## 1. Scope and reporting entities
> "Form EIA-930 data collection provides a centralized and comprehensive source for hourly operating data about the high-voltage bulk electric power grid in the Lower 48 states. We collect the data from the electricity balancing authorities (BAs) that operate the grid."

> "Historical data submissions are available via the API and the interactive webpage starting with January 1, 2019. For a longer time series, please find a downloadable flat files of submissions back to the beginning of the collection under the Download the Data tab on the main webpage."

> "Five BAs retired after July 1, 2015, the first date of EIA-930 data availability:"

The text says "Five", but the page lists seven retired BAs, including WACM and WAUW, both retired April 1, 2026. This internal inconsistency is on EIA's page. Neither retirement affects 2024 data.

> "We calculate regional and U.S. data by aggregating reported BA data into 13 regions and in total for the Lower 48 states."

> "Generation-only BAs consist of a power plant or group of power plants and do not directly serve retail customers. Therefore, they only report net generation and interchange and do not report demand or demand forecasts."

These BAs should be excluded from a demand benchmark.

## 2. Timestamps: hour-ending, local time, daylight saving time
> "BAs report all data as hourly integrated values, meaning they are time-weighted hourly averaged values. Hourly data are published using the hour ending time reporting convention. For example, the data for the hour ending 1:00 a.m. on August 1, 2019, is reported with a timestamp of August 1, 2019, 1:00 a.m."

> "We publish BA data using the local time zone chosen by each BA."

The page names BAs with unexpected time-zone choices: EPE, IPCO, LGEE, MISO, PNM and SEPA. For example:

> "Midcontinent Independent System Operator, Inc. (MISO) – Mostly located in the central time zone but reports in eastern standard time all year and does not observe daylight saving time when reporting"

> "For BAs that report using local time zones that observe daylight savings time, the March daylight savings transition day will have 23 hours of data while the November daylight savings transition day will have 25 hours of data."

> "Daylight saving time transition days are often misreported, with duplicate values reported for the same hour, a missing value for an hour, or incorrect timestamps for the daylight saving transition day. We monitor daylight saving time reporting issues and notify BAs to resubmit corrected data."

This is relevant to the timing-shift fault type and to the use of UTC indexing.

From the Form EIA-930 instructions (General Instructions):

> "Report all data as hourly integrated values in megawatts by hour ending time."

> "Report hourly date-time stamps using the Coordinated Universal Time (UTC) that correlates with the respondent's local time."

The 2024 BALANCE CSV files (local copy, header read only) contain both `Local Time at End of Hour` and `UTC Time at End of Hour`. Recommendation: index the benchmark on the UTC column to avoid DST duplicates and gaps.

## 3. Data element definitions
**Demand.**
> "Demand is a calculated value representing the amount of electricity load within a BA's electric system. A BA derives its demand value by taking the total metered net electricity generation within its electric system and subtracting the total metered net electricity interchange occurring between the BA and its neighboring BAs."

**Demand forecast.**
> "Each BA produces a day-ahead electricity demand forecast for every hour of the next day. These forecasts help BAs plan for and coordinate the reliable operation of their electric system."

**Net generation.**
> "Net generation represents the metered output of electric generating units in a BA's electric system. This generation only includes generating units that are managed by a BA or whose operations are visible to a BA."

> "Generators on the distribution system—both large-scale resources and small-scale distributed resources, such as rooftop solar photovoltaic (PV) systems—are typically not included."

**Interchange.**
> "Interchange is the net metered tie line flow from one BA to another directly interconnected BA. Total net interchange is the net sum of all interchange occurring between a BA and its directly interconnected neighboring BAs."

> "Negative interchange values indicate net inflows, and positive interchange values indicate net outflows."

**Energy balance identity.** This can serve as a physics-based consistency check.
> "System energy balance: BAs typically derive the value for demand each hour from total interchange and net generation, which are both aggregated metered values. Typically, demand equals net generation minus total interchange."

**Demand forecast caveat.**
> "So, the demand forecasts incorporate the effects of commercial arrangements such as dynamic scheduling and pseudo-ties. We have not asked respondents to produce a demand forecast consistent with a purely physical picture of their operations. This approach means that for some BAs, where a significant portion of their demand is outside their system or where other BAs control a significant amount of demand inside their system, the comparison between actual and forecast demand is not very meaningful."

The affected BAs are AVA, FPC, GVL, LGEE, PSEI, SEC, SPA and TEPC. Avoid forecast-residual features for these BAs.

From the instructions (Data Definitions):
> "DF = day-ahead demand forecast. This value should always be positive."

> "D = actual demand. This value should always be positive. This is reported on both the same-day and daily files."

## 4. Data are as reported by BAs; data-quality statements
> "We publish hourly operating data from individual BAs exactly as we received the data. Hourly U.S. and regional aggregations and all daily data aggregations incorporate procedures for handling anomalous values of some data elements. We advise caution when using these data."

> "BAs report data from internal systems that are subject to disruption or errors due to their near real-time collection. To provide some minimum level of data quality, we perform basic imputation procedures to fill in gaps or correct obvious errors. Notwithstanding the as-is nature of the collection, we expect respondents to correct anomalous values for the historical record."

> "We designed EIA-930 to balance timely reporting of electric system operating data with a reasonably accurate level of data quality. As a result, we collect the various data elements with different time lags, and we collect certain data elements multiple times. For example, we collect demand data in two ways: every hour after the operating hour is completed and again at 7:00 a.m. the next day for every hour of the previous day. The reported values may or not be the same, depending on the source of the data and intermittent revisions."

The phrase "may or not be the same" is reproduced exactly as it appears on EIA's page.

> "The data BAs report on the Form EIA-930 represent best values at the time of reporting, but various reporting issues may limit the quality of these data, including:"
> - "Limited metering data from voltage levels that vary by BAs"
> - "Revisions as a result of metering or telemetry issues from the immediate data read"
> - "Inability to read fuel consumption data on a real-time basis"
> - "Accounting discrepancies for transfers, pseudo-tied, and dynamically scheduled resources"

From the instructions (Data Quality):
> "Expected data revisions: When respondents cannot report finalized data by the due date and time, they should submit their best estimates on schedule and correct the data with a resubmission within 3 days or as soon as the actual data is available."

## 5. EIA imputation process (the "Imputed" values)
> "BAs occasionally report anomalous data values such as blank, zero, negative, and unreasonably high or low values. We perform a basic imputation process for several data elements."

> "We publish hourly BA data exactly as reported without imputation. Hourly U.S. and regional aggregations and all daily data aggregations incorporate our imputations."

**Demand.**
> "We impute for anomalous values for total demand if the value is missing or reported as negative, zero, or at least 1.5 times greater than the maximum of past total demand values reported by that BA."

> "When imputing demand, we use the following steps:"
> - "We use the demand forecast for that hour if the forecast exists, is not anomalous, and is not associated with BAs whose demand forecast values cannot be meaningfully compared with their demand values."
> - "If we do not use the demand forecast value, then we use the value for demand from the previous hour as long as that previous hour demand exists and is not anomalous."
> - "If we also do not use the previous hour demand, then we use the value for demand for the same hour of the previous day as long as that previous day's demand exists and is not anomalous."
> - "If the value for the previous day is also missing or anomalous, we flag the problem data value as needing imputation, but we do not assign an imputed value. We effectively treat the missing value as a zero when we calculate aggregations."

**Net generation.**
> "We impute for anomalous values for total net generation and net generation by energy source if the value is missing or reported as negative, zero, or at least 1.5 times greater than the maximum of past total net generation values reported by that BA, except when:"

The exceptions cover generation-only BAs and similar entities, pumped storage, and battery charging. The imputation steps are previous hour, then same hour of the previous day, then flag.

**Total interchange.**
> "We impute for anomalous values for total interchange if the value is as at least 1.5 times greater than the maximum of past positive total interchange values reported by that BA or at least 1.5 times less than the minimum of past negative total interchange values reported by that BA."

> "We impute anomalous values of total interchange with a value of 0."

**Implication for the benchmark.** EIA's screening rule catches only missing, non-positive or extreme (≥1.5× historical maximum) values. Spikes below that bound, level shifts, drifts, flatlines and timing shifts pass EIA's rule by construction. This is the gap the benchmark targets. The statement should be phrased carefully as an inference from the quoted rule.

## 6. "Imputed" and "Adjusted" columns in the BALANCE files
The 2024 six-month BALANCE CSV header (local file `03_DATA/raw/EIA930_BALANCE_2024_Jan_Jun.csv`, header line only) contains these columns: `Demand Forecast (MW)`, `Demand (MW)`, `Net Generation (MW)`, `Total Interchange (MW)`, `Sum(Valid DIBAs) (MW)`, `Demand (MW) (Imputed)`, `Net Generation (MW) (Imputed)`, `Total Interchange (MW) (Imputed)`, `Demand (MW) (Adjusted)`, `Net Generation (MW) (Adjusted)` and `Total Interchange (MW) (Adjusted)`, plus by-fuel equivalents. It also has `Local Time at End of Hour` and `UTC Time at End of Hour`.

**The "About the EIA-930 data" page does not define the "(Imputed)" or "(Adjusted)" columns**, and it does not use the word "adjusted" for these fields. The page says only that (a) BA-level hourly data are published as reported, and (b) imputation (Section 5) applies to aggregations. In the first data row (AECI, 2024-01-01 hour 1), the "(Imputed)" cells are blank and the "(Adjusted)" cells equal the raw values. That pattern is consistent with "Imputed" holding only EIA-imputed replacements and "Adjusted" being the series after imputation, but **this reading is not documented on the page and should not be stated as EIA's definition**. In the paper, describe the raw `Demand (MW)` column as "as reported by the BA" and either cite EIA's imputation rules for the derived columns or avoid them. No EIA page defining these columns was located; check the Grid Monitor's download dialog or EIA's API documentation if a definition is needed.

## 7. Data-quality or anomaly documentation pages
- The **"Data quality"**, **"Daylight saving time reporting"**, **"Data relationships"** and **"Imputation"** sections are all on the about page itself (https://www.eia.gov/electricity/930-content/about.html). No separate EIA web page dedicated to EIA-930 data quality, anomalies or known issues was found.
- **Hourly Electric Grid Monitor:** https://www.eia.gov/electricity/gridmonitor/. It returned HTTP 200 with the page title "Real-time Operating Grid - U.S. Energy Information Administration (EIA)". It is a JavaScript application, and its HTML contained no data-quality or known-issues links. The URL `/electricity/gridmonitor/about` also returns HTTP 200 with the same title (an app route).
- **EIA-930 reference tables:** https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx (HTTP 200). It holds BA and region codes and time zones.
- **Form EIA-930 instructions:** https://www.eia.gov/survey/form/eia_930/instructions.pdf (HTTP 200). It contains a "DATA QUALITY" section on expected revisions (quoted above).
- The about page's own footnote cites de Chalendar, Taggart & Benson, PNAS 2019, for its MRIO emissions method (`dechalendar2019tracking`).

## 8. Data timeliness (context)
> "Demand for today is typically available one hour after the end of the operating hour."

> "Day-ahead demand forecast for each hour of today (in the BA's reporting time zone) is typically available by 11:00 a.m. eastern time today."
