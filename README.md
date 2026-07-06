# Stat Chat

**Data Cleaning · Normalization · Statistical Analysis · AI-Powered Iterative Adjustment · PDF Reports**

A Python tool with both a **GUI** (Tkinter) and **CLI** interface for analysing tabular data from CSV or Excel files. Powered by Claude API or a local LM Studio model for natural-language dataset adjustment and annotated-report parsing.

---

## Installation

```bash
pip install statchat-app
```

> Tkinter ships with standard Python on Windows/macOS. On Linux: `sudo apt install python3-tk`

> A standalone EXE file (~2.13 GB) is available at: https://www.mediafire.com/file/kec99bnwkjfwob0/statchat.exe/file for those without Python installed. (Windows only)

> A Windows Setup Wizard EXE file (~1.95 GB) is available at: https://www.mediafire.com/file/hrrewqdb45uwq55/StatChat_Setup_1.0.2.exe/file

---

## Launch

```bash
statchat              # GUI
statchat --cli --help # CLI
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
8. **✦ Adjust Data** — iteratively modify the dataset using plain English or annotated images (see below).

---

## AI-Powered Data Adjustment

The **✦ Adjust Data** tab lets you modify the dataset conversationally after analysis, without writing any code.

### Text instructions

Type any natural-language instruction and press **Send**:

> *"Add $1000 to each value in spend"*  
> *"Multiply income by 1.1"*  
> *"Clip spend between 0 and 5000"*  
> *"Remove rows where age < 18"*  
> *"Log-transform spend"*  
> *"Rename 'score' to 'risk_score'"*  
> *"Fill nulls in income with 0"*

Stat Chat sends the instruction to the configured LLM, parses the response into typed operations, shows you a **diff preview** (columns affected, mean before/after), and waits for you to **Accept** or **Discard** before applying the change.

### Annotated report images (vision)

Print or screenshot your PDF report, annotate it with handwritten or typed notes (e.g. circle a column and write *"× 1.05"*), then click **📷 Image** to upload the photo. A vision-capable model reads the annotations and proposes the matching operations — same Accept/Discard flow.

### Version history

Every accepted change is saved as a numbered version in the sidebar. You can:
- **Revert** to any prior version
- **Save** any version to file (in the original file format)
- **Generate a PDF report** for any specific version

The PDF report includes a full **Iterative Adjustment History** section showing every version, what changed, and a mean-evolution table across versions.

---

## LLM Backend Configuration

Click **⚙ Settings** in the top-right to choose your backend.

| Provider | Use case | Setup |
|---|---|---|
| **Claude API** (default) | Cloud, no local setup | API key injected automatically |
| **LM Studio — Text** | Local, privacy-first | Load any text model in LM Studio |
| **LM Studio — Vision** | Local + image annotations | Load a multimodal model (LLaVA, Moondream, etc.) |

**LM Studio setup:**
1. Download [LM Studio](https://lmstudio.ai)
2. Load a text model (e.g. Llama 3, Mistral) for chat adjustments
3. Load a vision model (e.g. LLaVA, BakLLaVA) for image annotation parsing
4. Developer tab → Enable Local Server → Start Server
5. In Stat Chat → ⚙ Settings → select LM Studio → click **↻ Fetch loaded models** → **Test Connection** → Save

---

## CLI Reference

```
statchat --cli --input FILE [options]

File I/O:
  --input,  -i PATH         Input CSV or Excel file (required)
  --output, -o PATH         Save processed data here
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

Adjustment (requires LLM backend):
  --adjust INSTRUCTION      Natural-language adjustment (repeatable)
  --adjust-image IMAGE_PATH Annotated report image (PNG/JPG)

LLM Backend:
  --backend                 claude | lmstudio | lmstudio_vision  (default: claude)
  --lmstudio-url URL        LM Studio server URL (default: http://localhost:1234)
  --lmstudio-model ID       LM Studio text model ID
  --lmstudio-vision-model ID LM Studio vision model ID
```

### Examples

**Full pipeline with text adjustments:**
```bash
statchat --cli \
  --input sales.csv \
  --drop-duplicates --fill-nulls mean \
  --normalize zscore \
  --central-tendency --dispersion --correlation \
  --adjust "Add 1000 to spend" \
  --adjust "Multiply income by 1.1" \
  --output adjusted_sales.xlsx \
  --output-format xlsx \
  --report report.pdf
```

**Parse an annotated report image with a local vision model:**
```bash
statchat --cli \
  --input data.csv \
  --adjust-image annotated_report.png \
  --backend lmstudio_vision \
  --lmstudio-url http://localhost:1234 \
  --lmstudio-vision-model llava-1.5-7b \
  --output adjusted.csv \
  --report report.pdf
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

---

## Project Structure

```
statchat/
├── __main__.py           Entry point (GUI or CLI)
├── icon.ico
├── assets/
├── core/
│   ├── loader.py         File I/O (CSV, Excel, JSON)
│   ├── cleaner.py        Cleaning & normalization
│   ├── analyzer.py       Statistical metrics
│   ├── adjuster.py       NL instruction parser & executor
│   ├── llm_backend.py    Claude API + LM Studio abstraction
│   └── reporter.py       PDF report generation
├── gui/
│   ├── app.py            Main Tkinter GUI
│   ├── chat_panel.py     Adjust Data tab (chat + version history)
│   └── settings_dialog.py LLM backend settings
└── cli/
    └── runner.py         CLI runner
```

---

## Requirements

```
pandas >= 2.0
numpy >= 1.24
scipy >= 1.10
scikit-learn >= 1.3
openpyxl >= 3.1
reportlab >= 4.0
matplotlib >= 3.7
Pillow >= 9.0
requests >= 2.28
```

Tkinter is required for the GUI and ships with standard Python. Linux users may need `sudo apt install python3-tk`.
