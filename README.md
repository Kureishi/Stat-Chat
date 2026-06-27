# DataLyzer

**Data Cleaning · Normalization · Statistical Analysis · PDF Reports**

A Python tool with both a **GUI** (Tkinter) and **CLI** interface for analysing tabular data from CSV or Excel files.

---

## Installation

```bash
pip install -r requirements.txt
```

> Tkinter ships with standard Python on Windows/macOS. On Linux: `sudo apt install python3-tk`

---

## Launch

### GUI (default)
```bash
python main.py
```

### CLI
```bash
python main.py --cli --input data.csv [options]
```

---

## GUI Walkthrough

1. **Load CSV / Excel** — opens a file picker; the Data Preview tab fills instantly.
2. **Data Cleaning** — tick any combination of:
   - Drop duplicate rows
   - Drop rows with null values
   - Fill nulls (mean / median / mode / zero)
3. **Normalization** — choose one method:
   - **Z-score** — standardise with custom target mean & std (default 0, 1)
   - **Min-Max** — scale to [0, 1]
   - **Robust** — median/IQR scaling (outlier-resistant)
4. **Analysis Metrics** — tick any combination:
   - Measures of Central Tendency (mean, median, mode)
   - Measures of Dispersion (std dev, variance, IQR, range, CV)
   - Shape stats (skewness, kurtosis)
   - Percentile Statistics (P5–P95)
   - Normality Tests (Shapiro-Wilk)
   - Correlation Matrix (heatmap in PDF)
   - ROC-AUC (enter the binary target column name)
5. **Run Analysis** — results appear in the *Analysis Results* tab.
6. **Save Cleaned Data** — exports as CSV, Excel, or JSON.
7. **Export PDF Report** — full styled report with tables and charts.

---

## CLI Reference

```
python main.py --cli --input FILE [options]

File I/O:
  --input, -i PATH          Input CSV or Excel file (required)
  --output, -o PATH         Save cleaned data here
  --output-format           csv | xlsx | json  (default: csv)
  --report, -r PATH         Save PDF report here

Cleaning:
  --drop-duplicates         Remove duplicate rows
  --drop-nulls              Drop rows containing any null
  --fill-nulls STRATEGY     mean | median | mode | zero

Normalization:
  --normalize METHOD        zscore | minmax | robust
  --norm-mean FLOAT         Z-score target mean  (default 0.0)
  --norm-std  FLOAT         Z-score target std   (default 1.0)

Analysis:
  --central-tendency        Mean, median, mode
  --dispersion              Std dev, variance, IQR, range
  --shape                   Skewness & kurtosis
  --percentiles             P5–P95
  --correlation             Pearson correlation matrix
  --roc-auc TARGET_COL      ROC-AUC vs a binary target column
  --all-metrics             Enable all metrics above
```

### Example

```bash
python main.py --cli \
  --input sales.csv \
  --output cleaned_sales \
  --output-format xlsx \
  --drop-duplicates \
  --fill-nulls mean \
  --normalize zscore \
  --central-tendency \
  --dispersion \
  --shape \
  --correlation \
  --roc-auc churn \
  --report analysis_report.pdf
```

---

## Project Structure

```
datalyzer/
├── main.py               Entry point (GUI or CLI)
├── requirements.txt
├── core/
│   ├── loader.py         File I/O (CSV, Excel, JSON)
│   ├── cleaner.py        Cleaning & normalization
│   ├── analyzer.py       Statistical metrics
│   └── reporter.py       PDF report generation
├── gui/
│   └── app.py            Tkinter GUI
└── cli/
    └── runner.py         CLI runner
```

---

## Supported Metrics

| Category | Metrics |
|---|---|
| Central Tendency | Mean, Median, Mode, Count |
| Dispersion | Std Dev, Variance, Range, IQR, Min, Max, CV |
| Shape | Skewness, Kurtosis |
| Percentiles | P5, P10, P25, P50, P75, P90, P95 |
| Normality | Shapiro-Wilk statistic & p-value |
| Correlation | Pearson correlation matrix + heatmap |
| ROC-AUC | Per-feature AUC score + ROC curve plot |
