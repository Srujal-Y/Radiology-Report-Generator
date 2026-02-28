# Radiology-Report-Generator
# Radiology Report Studio

Radiology Report Studio is a Streamlit-based prototype for creating radiology reports from chest X-ray images, storing report metadata in SQLite, and generating downloadable PDF reports.

This repository currently contains two app variants:

- `radiology_report_studio.py`: enhanced workflow with multi-image upload, QR/hash-based PDF verification metadata, signatures, watermark, and AI-assisted impression text.
- `radiology_app_full.py`: earlier workflow with single-image processing, grammar correction support, recent report listing, and CSV export.

## Key Features

- Streamlit UI for patient, clinician, and exam information entry
- X-ray image preprocessing (resize, contrast, brightness, grayscale)
- PDF generation via ReportLab (structured sections, embedded images, signatures)
- SQLite persistence (`reports.db`) for report records
- Optional AI-assisted multi-label output for chest X-rays (`Pneumonia`, `COVID-19`, `Effusion`, `Nodule`, `Normal`)
- In-app PDF download link after report generation

## Tech Stack

- Python
- Streamlit
- Pillow (PIL)
- SQLite3
- ReportLab
- qrcode
- PyTorch + torchvision
- Optional: `language-tool-python` (used by `radiology_app_full.py` for grammar correction)

## Project Structure

- `radiology_report_studio.py`: advanced version
- `radiology_app_full.py`: legacy/full variant with sidebar report utilities
- `reports.db`: created at runtime for saved reports
- `report.pdf` / `report_<id>.pdf`: generated output files

## Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run one of the Streamlit apps.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install streamlit pillow reportlab qrcode torch torchvision language-tool-python
```

## Run

Enhanced app:

```powershell
streamlit run radiology_report_studio.py
```

Alternative app:

```powershell
streamlit run radiology_app_full.py
```

## Typical Workflow

1. Enter hospital, doctor, patient, and clinical details.
2. Upload one or more chest X-ray images.
3. Adjust preprocessing sliders (contrast, brightness).
4. Enter diagnosis and treatment (or allow impression auto-fill in studio variant).
5. Click generate/save.
6. Download the produced PDF.

## Important Notes

- The two scripts define different `reports` table schemas but share the same database file name (`reports.db`).
- To avoid schema conflicts, use one script per database file, or reset/migrate `reports.db` when switching variants.
- AI outputs in this project are prototype outputs and are not clinically validated for real-world medical decision-making.
- The `resnet50` model is created with a replaced final layer in code; no custom trained checkpoint is loaded in this repository.

## Troubleshooting

- If PyTorch model weights fail to download, verify internet access and retry.
- If grammar correction fails in `radiology_app_full.py`, ensure `language-tool-python` is installed.
- If inserts fail with SQLite column errors, remove or migrate `reports.db` and relaunch with a single app variant.

## Disclaimer

This project is for educational/prototype use only and is not a certified medical device.
