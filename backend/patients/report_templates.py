from copy import deepcopy
from django.utils import timezone


REPORT_TEMPLATE_CATALOG = [
    {
        "key": "CBC",
        "name": "Complete Blood Count",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["CBC", "Complete Blood Count"],
        "tests": [
            {"name": "HAEMOGLOBIN", "unit": "gm/dl", "refRange": "12–16", "status": "Normal"},
            {"name": "TLC (Total Leucocyte Count)", "unit": "/cumm", "refRange": "4000–11000", "status": "Normal"},
            {"name": "POLYMORPHS", "unit": "%", "refRange": "40–75", "status": "Normal"},
            {"name": "LYMPHOCYTE", "unit": "%", "refRange": "20–40", "status": "Normal"},
            {"name": "EOSINOPHIL", "unit": "%", "refRange": "01–06", "status": "Normal"},
            {"name": "MONOCYTE", "unit": "%", "refRange": "00–08", "status": "Normal"},
            {"name": "BASOPHIL", "unit": "%", "refRange": "00–00", "status": "Normal"},
            {"name": "PCV", "unit": "%", "refRange": "34–45", "status": "Normal"},
            {"name": "MCV (Mean Corp Volume)", "unit": "Fl/dl", "refRange": "76–96", "status": "Normal"},
            {"name": "MCH (Mean Corp Hb)", "unit": "Pg/dl", "refRange": "27–32", "status": "Normal"},
            {"name": "MCHC (Mean Corp Hb Conc)", "unit": "gm/dl", "refRange": "31–38", "status": "Normal"},
            {"name": "RBC (Red Blood Cell Count)", "unit": "mill/cumm", "refRange": "3.5–5.5", "status": "Normal"},
            {"name": "PLATELET COUNT", "unit": "Lacs/cumm", "refRange": "1.5–4.5", "status": "Normal"},
            {"name": "ESR (Wintrobe)", "unit": "mm", "refRange": "M: 0–10, F: 0–20", "status": "Normal"},
        ],
    },
    {
        "key": "KFT",
        "name": "Kidney Function Test",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["KFT", "Kidney Function Test"],
        "tests": [
            {"name": "BLOOD UREA", "unit": "mg/dl", "refRange": "13–45", "status": "Normal"},
            {"name": "SERUM CREATININE", "unit": "mg/dl", "refRange": "0.7–1.4", "status": "Normal"},
            {"name": "S.URIC ACID", "unit": "mg/dl", "refRange": "3.2–7.2", "status": "Normal"},
            {"name": "SODIUM", "unit": "mmol/L", "refRange": "135–145", "status": "Normal"},
            {"name": "POTASSIUM", "unit": "mmol/L", "refRange": "3.6–5.0", "status": "Normal"},
            {"name": "CALCIUM", "unit": "mg/dl", "refRange": "8.2–10.5", "status": "Normal"},
        ],
    },
    {
        "key": "LFT",
        "name": "Liver Function Test",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["LFT", "Liver Function Test"],
        "tests": [
            {"name": "SERUM BILIRUBIN (TOTAL)", "unit": "mg/dl", "refRange": "0.2–1.3", "status": "Normal"},
            {"name": "CONJUGATED (D BILIRUBIN)", "unit": "mg/dl", "refRange": "0.0–0.3", "status": "Normal"},
            {"name": "UNCONJUGATED (I.D BILIRUBIN)", "unit": "mg/dl", "refRange": "0.2–1.1", "status": "Normal"},
            {"name": "SGOT/AST", "unit": "U/L", "refRange": "00–55", "status": "Normal"},
            {"name": "SGPT/ALT", "unit": "U/L", "refRange": "00–40", "status": "Normal"},
            {"name": "TOTAL PROTEIN", "unit": "gm/dl", "refRange": "6.3–8.2", "status": "Normal"},
            {"name": "ALBUMIN", "unit": "gm/dl", "refRange": "3.5–5.0", "status": "Normal"},
            {"name": "GLOBULINE", "unit": "gm/dl", "refRange": "2.5–5.6", "status": "Normal"},
            {"name": "ALKALINE PHOSPHATASE", "unit": "IU/L", "refRange": "20–130", "status": "Normal"},
        ],
    },
    {
        "key": "LIPID",
        "name": "Lipid Profile",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Lipid Profile"],
        "tests": [
            {"name": "CHOLESTEROL TOTAL", "unit": "mg/dl", "refRange": "125–200", "status": "Normal"},
            {"name": "TRIGLYCERIDE", "unit": "mg/dl", "refRange": "25–200", "status": "Normal"},
            {"name": "CHOLESTEROL HDL", "unit": "mg/dl", "refRange": "35–80", "status": "Normal"},
            {"name": "CHOLESTEROL VLDL", "unit": "mg/dl", "refRange": "5–40", "status": "Normal"},
            {"name": "CHOLESTEROL LDL", "unit": "mg/dl", "refRange": "85–130", "status": "Normal"},
            {"name": "LDL / HDL RATIO", "unit": "", "refRange": "1.5–3.5", "status": "Normal"},
        ],
    },
    {
        "key": "BLOODGAS",
        "name": "Blood Gas Analysis",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood Gas Analysis"],
        "tests": [
            {"name": "pH", "unit": "", "refRange": "7.35–7.45", "status": "Normal"},
            {"name": "pCO2", "unit": "mmHg", "refRange": "35–40", "status": "Normal"},
            {"name": "pO2", "unit": "mmHg", "refRange": "80–95", "status": "Normal"},
            {"name": "TCO2", "unit": "mmol/L", "refRange": "23–27", "status": "Normal"},
            {"name": "HCO3", "unit": "mmol/L", "refRange": "22–26", "status": "Normal"},
            {"name": "BE", "unit": "mmol/L", "refRange": "-2 to +2", "status": "Normal"},
            {"name": "%SO2C", "unit": "%", "refRange": "96–97", "status": "Normal"},
            {"name": "Na+", "unit": "mmol/L", "refRange": "134–146", "status": "Normal"},
            {"name": "K+", "unit": "mmol/L", "refRange": "3.4–5.0", "status": "Normal"},
            {"name": "Ca++", "unit": "mmol/L", "refRange": "1.15–1.33", "status": "Normal"},
            {"name": "GLU", "unit": "mg/dl", "refRange": "74–100", "status": "Normal"},
            {"name": "THbc", "unit": "%", "refRange": "12–16", "status": "Normal"},
            {"name": "HCT", "unit": "mmol/L", "refRange": "38–51", "status": "Normal"},
        ],
    },
    {
        "key": "GLUCOSE",
        "name": "Blood Glucose",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood Glucose"],
        "tests": [
            {"name": "BLOOD GLUCOSE RANDOM", "unit": "mg/dl", "refRange": "100–150", "status": "Normal"},
            {"name": "BLOOD GLUCOSE FASTING", "unit": "mg/dl", "refRange": "70–110", "status": "Normal"},
            {"name": "BLOOD GLUCOSE PP", "unit": "mg/dl", "refRange": "<140", "status": "Normal"},
            {"name": "HbA1c (Glycosylated Haemoglobin)", "unit": "%", "refRange": "4.30–6.40", "status": "Normal"},
        ],
    },
    {
        "key": "CRP",
        "name": "CRP / Procalcitonin",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["CRP / Procalcitonin"],
        "tests": [
            {"name": "CRP (Qualitative)", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
            {"name": "CRP (Quantitative)", "unit": "mg/L", "refRange": "<6.0", "status": "Normal"},
            {"name": "SERUM PROCALCITONIN", "unit": "pg/ml", "refRange": "0.0–500", "status": "Normal"},
        ],
    },
    {
        "key": "WIDAL",
        "name": "Widal Test (Slide Method)",
        "report_type": "Immunology – Serology",
        "report_category": "IMMUNOLOGY – SEROLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Widal Test (Slide Method)"],
        "tests": [
            {"name": "TO (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "TH (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "AH (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "BH (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "RESULT", "unit": "", "refRange": "POSITIVE / NEGATIVE", "status": "Normal"},
        ],
        "remarks": "Interpretation: Antibody titer of 1:80 or higher suggests infection. Clinical correlation advised.",
    },
    {
        "key": "MALARIA",
        "name": "Malaria Antigen Test",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Malaria Antigen Test"],
        "tests": [
            {"name": "PLASMODIUM P. VIVAX", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "PLASMODIUM FALCIPARUM", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
        ],
        "remarks": "Diagnosis should be correlated with smear findings and clinical picture.",
    },
    {
        "key": "TYPHIDOT",
        "name": "Typhi Dot (IgG & IgM)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Typhi Dot (IgG & IgM)"],
        "tests": [
            {"name": "THYPIDOT TEST FOR S.TYPHI IgM", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "THYPIDOT TEST FOR S.TYPHI IgG", "unit": "", "refRange": "", "status": "Normal"},
        ],
        "remarks": "Clinical correlation is advised.",
    },
    {
        "key": "DENGUE",
        "name": "Dengue Panel",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Dengue Panel"],
        "tests": [
            {"name": "DENGUE IgM ANTIBODIES", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
            {"name": "DENGUE IgG ANTIBODIES", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
            {"name": "DENGUE NS1 ANTIGEN", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
        ],
    },
    {
        "key": "VIRAL",
        "name": "Viral Markers",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Viral Markers"],
        "tests": [
            {"name": "HIV I & II", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "HEPATITIS B (HBsAg)", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "HCV", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "COVID-19 (Ag)", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
        ],
    },
    {
        "key": "URINE_RM",
        "name": "Urine Examination (R/M)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Urine Examination (R/M)"],
        "tests": [
            {"name": "COLOUR", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "VOLUME", "unit": "ml", "refRange": "", "status": "Normal"},
            {"name": "SPECIFIC GRAVITY", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "REACTION", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "ALBUMIN", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "SUGAR", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "PH", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "PUS CELLS", "unit": "/HPF", "refRange": "", "status": "Normal"},
            {"name": "EPITHELIAL CELLS", "unit": "/HPF", "refRange": "", "status": "Normal"},
            {"name": "RBC'S", "unit": "/HPF", "refRange": "", "status": "Normal"},
            {"name": "CASTS", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CRYSTALS", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "BACTERIA", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "OTHERS", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    {
        "key": "URINE_CS",
        "name": "Urine C/S (Culture & Sensitivity)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Urine C/S (Culture & Sensitivity)"],
        "tests": [
            {"name": "SPECIMEN SOURCE", "unit": "", "refRange": "URINE C/S", "status": "Normal"},
            {"name": "DATE RECEIVED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "DATE REPORTED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CULTURE RESULT", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "ANTIBIOTIC SENSITIVITY", "unit": "", "refRange": "Sensitive / Resistant", "status": "Normal"},
        ],
    },
    {
        "key": "BLOOD_CS",
        "name": "Blood C/S (Culture & Sensitivity)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood C/S (Culture & Sensitivity)"],
        "tests": [
            {"name": "SPECIMEN SOURCE", "unit": "", "refRange": "BLOOD C/S", "status": "Normal"},
            {"name": "DATE RECEIVED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "DATE REPORTED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CULTURE RESULT", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    {
        "key": "RAD_GENERIC",
        "name": "Radiology Report",
        "report_type": "X-Ray",
        "report_category": "RADIOLOGY",
        "bill_category": "RADIOLOGY",
        "aliases": ["Radiology Report", "X-Ray", "CT", "MRI", "USG", "Ultrasound", "Echo"],
        "findings": "",
        "impression": "",
        "remarks": "",
        "tests": [],
    },
]


def get_template_by_label(label):
    normalized = str(label or "").strip().lower()
    for template in REPORT_TEMPLATE_CATALOG:
        aliases = [template["name"], *template.get("aliases", [])]
        if any(normalized == str(alias).strip().lower() for alias in aliases):
            return template
    return None


def parse_investigation_labels(value):
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def build_report_from_template(template, patient=None, admission=None, ordered_by=""):
    report = {
        "id": f"template-{template['key']}",
        "reportName": template["name"],
        "reportType": template["report_type"],
        "reportCategory": template["report_category"],
        "billCategory": template.get("bill_category", "PATHOLOGY"),
        "date": timezone.localdate().isoformat(),
        "orderedBy": ordered_by or "",
        "amount": 0,
        "remarks": template.get("remarks", ""),
        "modalityDetails": deepcopy(template.get("modality_details", {})),
        "findings": template.get("findings", ""),
        "impression": template.get("impression", ""),
        "tests": [
            {
                "id": index + 1,
                "name": row.get("name", ""),
                "value": row.get("value", ""),
                "unit": row.get("unit", ""),
                "refRange": row.get("refRange", ""),
                "status": row.get("status", "Normal"),
            }
            for index, row in enumerate(deepcopy(template.get("tests", [])))
        ],
    }
    if patient:
        report["patientUhid"] = patient.uhid
        report["patientName"] = patient.patientName
    if admission:
        report["admNo"] = admission.admNo
    return report


def build_suggested_reports_for_admission(patient, admission):
    medical_history = getattr(admission, "medicalHistory", None)
    labels = parse_investigation_labels(getattr(medical_history, "investigations", ""))
    ordered_by = getattr(medical_history, "treatingDoctor", "") if medical_history else ""

    reports = []
    seen_keys = set()
    for label in labels:
        template = get_template_by_label(label)
        if not template:
            continue
        if template["key"] in seen_keys:
            continue
        seen_keys.add(template["key"])
        reports.append(build_report_from_template(template, patient=patient, admission=admission, ordered_by=ordered_by))
    return reports
