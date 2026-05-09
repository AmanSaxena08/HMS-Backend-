from copy import deepcopy
from django.utils import timezone


REPORT_TEMPLATE_CATALOG = [
    # ─────────────────────────────────────────────────────────────
    # 1. Complete Blood Count (CBC)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "CBC",
        "name": "Complete Blood Count (CBC)",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["CBC", "Complete Blood Count (CBC)", "Complete Blood Count"],
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
    # ─────────────────────────────────────────────────────────────
    # 2. Kidney Function Test (KFT)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "KFT",
        "name": "Kidney Function Test (KFT)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["KFT", "Kidney Function Test (KFT)", "Kidney Function Test"],
        "tests": [
            {"name": "BLOOD UREA", "unit": "mg/dl", "refRange": "13–45", "status": "Normal"},
            {"name": "SERUM CREATININE", "unit": "mg/dl", "refRange": "0.7–1.4", "status": "Normal"},
            {"name": "S.URIC ACID", "unit": "mg/dl", "refRange": "3.2–7.2", "status": "Normal"},
            {"name": "SODIUM", "unit": "mmol/L", "refRange": "135–145", "status": "Normal"},
            {"name": "POTASSIUM", "unit": "mmol/L", "refRange": "3.6–5.0", "status": "Normal"},
            {"name": "CALCIUM", "unit": "mg/dl", "refRange": "8.2–10.5", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 3. Liver Function Test (LFT)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "LFT",
        "name": "Liver Function Test (LFT)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["LFT", "Liver Function Test (LFT)", "Liver Function Test"],
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
    # ─────────────────────────────────────────────────────────────
    # 4. Lipid Profile
    # ─────────────────────────────────────────────────────────────
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
    # ─────────────────────────────────────────────────────────────
    # 5. Blood Gas Analysis
    # ─────────────────────────────────────────────────────────────
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
    # ─────────────────────────────────────────────────────────────
    # 6. CRP (Qualitative)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "CRP",
        "name": "CRP (Qualitative)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["CRP (Qualitative)", "CRP"],
        "tests": [
            {"name": "CRP (Qualitative)", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 7. Blood Glucose (Random)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "GLUCOSE_RANDOM",
        "name": "Blood Glucose (Random)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood Glucose (Random)", "Blood Glucose Random"],
        "tests": [
            {"name": "BLOOD GLUCOSE RANDOM", "unit": "mg/dl", "refRange": "100–150", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 8. Blood Glucose (Fasting)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "GLUCOSE_FASTING",
        "name": "Blood Glucose (Fasting)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood Glucose (Fasting)", "Blood Glucose Fasting"],
        "tests": [
            {"name": "BLOOD GLUCOSE FASTING", "unit": "mg/dl", "refRange": "70–110", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 9. Widal Test (Slide Method)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "WIDAL",
        "name": "Widal Test (Slide Method)",
        "report_type": "Immunology – Serology",
        "report_category": "IMMUNOLOGY – SEROLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Widal Test (Slide Method)", "Widal Test"],
        "tests": [
            {"name": "TO (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "TH (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "AH (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "BH (1:20 / 1:40 / 1:80 / 1:160 / 1:320)", "unit": "", "refRange": "Pattern", "status": "Normal"},
            {"name": "RESULT", "unit": "", "refRange": "POSITIVE / NEGATIVE", "status": "Normal"},
        ],
        "remarks": "Interpretation: Antibody titer of 1:80 or higher suggests infection. Clinical correlation advised.",
    },
    # ─────────────────────────────────────────────────────────────
    # 10. Malaria Antigen Test
    # ─────────────────────────────────────────────────────────────
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
    # ─────────────────────────────────────────────────────────────
    # 11. Typhi Dot (IgG & IgM)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "TYPHIDOT",
        "name": "Typhi Dot (IgG & IgM)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Typhi Dot (IgG & IgM)", "Typhi Dot"],
        "tests": [
            {"name": "THYPIDOT TEST FOR S.TYPHI IgM", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "THYPIDOT TEST FOR S.TYPHI IgG", "unit": "", "refRange": "", "status": "Normal"},
        ],
        "remarks": "Clinical correlation is advised.",
    },
    # ─────────────────────────────────────────────────────────────
    # 12. Dengue (IgM & IgG)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "DENGUE_IGMG",
        "name": "Dengue (IgM & IgG)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Dengue (IgM & IgG)", "Dengue IgM & IgG"],
        "tests": [
            {"name": "DENGUE IgM ANTIBODIES", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
            {"name": "DENGUE IgG ANTIBODIES", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
        ],
        "remarks": "IgM antibodies appear around 5th day of infection and last 60–90 days. IgG antibodies may be detected for life.",
    },
    # ─────────────────────────────────────────────────────────────
    # 13. Dengue NS1 Antigen Test
    # ─────────────────────────────────────────────────────────────
    {
        "key": "DENGUE_NS1",
        "name": "Dengue NS1 Antigen Test",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": [
            "Dengue NS1 Antigen Test",
            "Dengue NS1",
            "DENGUE NS1 ANTIGEN TEST",
            "Dengue NS1 Antigen",
        ],
        "tests": [
            {"name": "DENGUE NS1 ANTIGEN", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
        ],
        "remarks": "NS1 antigen is detectable from day 1 up to 9 days after onset of fever.",
    },
    # ─────────────────────────────────────────────────────────────
    # 14. Viral Markers (HIV, HBsAg, HCV)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "VIRAL",
        "name": "Viral Markers (HIV, HBsAg, HCV)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Viral Markers (HIV, HBsAg, HCV)", "Viral Markers"],
        "tests": [
            {"name": "HIV I & II", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "HEPATITIS B (HBsAg)", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "HCV", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 15. COVID-19 Rapid Antigen
    # ─────────────────────────────────────────────────────────────
    {
        "key": "COVID19",
        "name": "COVID-19 Rapid Antigen",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": [
            "COVID-19 Rapid Antigen",
            "COVID-19",
            "COVID-19 RAPID ANTIGEN",
            "COVID-19(Ag)",
            "COVID_AG",
        ],
        "tests": [
            {"name": "COVID-19 (Ag)", "unit": "", "refRange": "NON-REACTIVE", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 16. Urine Examination (Routine)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "URINE_RM",
        "name": "Urine Examination (Routine)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Urine Examination (Routine)", "Urine Examination (R/M)", "Urine R/M"],
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
    # ─────────────────────────────────────────────────────────────
    # 17. Urine Gram Stain
    # ─────────────────────────────────────────────────────────────
    {
        "key": "URINE_GRAM",
        "name": "Urine Gram Stain",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Urine Gram Stain"],
        "tests": [
            {"name": "SPECIMEN SOURCE", "unit": "", "refRange": "URINE", "status": "Normal"},
            {"name": "GRAM STAIN RESULT", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 18. Aerobic Culture & Sensitivity
    # ─────────────────────────────────────────────────────────────
    {
        "key": "CULTURE_CS",
        "name": "Aerobic Culture & Sensitivity",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Aerobic Culture & Sensitivity", "Culture & Sensitivity", "C/S"],
        "tests": [
            {"name": "SPECIMEN SOURCE", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "DATE RECEIVED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "DATE REPORTED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CULTURE RESULT", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "ANTIBIOTIC SENSITIVITY", "unit": "", "refRange": "Sensitive / Resistant", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 19. Serum Procalcitonin
    # ─────────────────────────────────────────────────────────────
    {
        "key": "PROCALCITONIN",
        "name": "Serum Procalcitonin",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Serum Procalcitonin", "Procalcitonin"],
        "tests": [
            {"name": "SERUM PROCALCITONIN", "unit": "pg/ml", "refRange": "0.0–500", "status": "Normal"},
        ],
        "remarks": (
            "< 500 pg/ml: Severe systemic infection not likely. "
            "500–2000: Systemic infection possible. "
            "2000–10000: Sepsis likely. "
            "> 10000: Severe sepsis / septic shock almost certain."
        ),
    },
    # ─────────────────────────────────────────────────────────────
    # 20. Sputum for AFB
    # ─────────────────────────────────────────────────────────────
    {
        "key": "SPUTUM_AFB",
        "name": "Sputum for AFB",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Sputum for AFB", "Sputum AFB"],
        "tests": [
            {"name": "SPUTUM FOR AFB", "unit": "", "refRange": "NO ACID FAST BACILLI SEEN", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 21. Sputum Gram Stain
    # ─────────────────────────────────────────────────────────────
    {
        "key": "SPUTUM_GRAM",
        "name": "Sputum Gram Stain",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Sputum Gram Stain"],
        "tests": [
            {"name": "SPUTUM GRAM STAIN RESULT", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 22. Cardiac Markers (Trop-T, Trop-I, CPK)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "CARDIAC",
        "name": "Cardiac Markers (Trop-T, Trop-I, CPK)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Cardiac Markers (Trop-T, Trop-I, CPK)", "Cardiac Markers"],
        "tests": [
            {"name": "TROPONIN-T", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "TROPONIN-I", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "CPK-MB", "unit": "IU/L", "refRange": "Upto 24", "status": "Normal"},
            {"name": "CPK", "unit": "U/L", "refRange": "22–198", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 23. Total Thyroid Profile
    # ─────────────────────────────────────────────────────────────
    {
        "key": "THYROID",
        "name": "Total Thyroid Profile",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Total Thyroid Profile", "Thyroid Profile"],
        "tests": [
            {"name": "T3 (Triiodothyronine)", "unit": "pmol/L", "refRange": "0.9–2.5", "status": "Normal"},
            {"name": "Free Thyroxine (FT4)", "unit": "pmol/L", "refRange": "60–135", "status": "Normal"},
            {"name": "Thyroid Stimulating Hormone (TSH)", "unit": "pmol/L", "refRange": "0.25–5.0", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 24. Vitamin B-12 (Cyanocobalamin)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "VIT_B12",
        "name": "Vitamin B-12 (Cyanocobalamin)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Vitamin B-12 (Cyanocobalamin)", "Vitamin B12", "Vitamin B-12"],
        "tests": [
            {"name": "VITAMIN B-12 (CYANOCOBALAMIN)", "unit": "pg/ml", "refRange": "211–911", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 25. 25 OH Vitamin D3
    # ─────────────────────────────────────────────────────────────
    {
        "key": "VIT_D3",
        "name": "25 OH Vitamin D3",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["25 OH Vitamin D3", "Vitamin D3", "Vitamin D"],
        "tests": [
            {"name": "25 OH VITAMIN D3", "unit": "ng/ml", "refRange": "30–100", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 26. Stool Examination
    # ─────────────────────────────────────────────────────────────
    {
        "key": "STOOL",
        "name": "Stool Examination",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Stool Examination", "Stool R/M"],
        "tests": [
            {"name": "COLOUR", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CONSISTANCY", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "MUCOUS", "unit": "", "refRange": "NIL", "status": "Normal"},
            {"name": "PH", "unit": "", "refRange": "7.0–7.8", "status": "Normal"},
            {"name": "REACTION", "unit": "", "refRange": "ACIDIC / ALKALINE", "status": "Normal"},
            {"name": "PUS CELLS", "unit": "/HPF", "refRange": "0–1", "status": "Normal"},
            {"name": "RED BLOOD CELLS", "unit": "/HPF", "refRange": "NIL", "status": "Normal"},
            {"name": "OVA", "unit": "", "refRange": "NIL", "status": "Normal"},
            {"name": "CYST", "unit": "", "refRange": "NIL", "status": "Normal"},
            {"name": "BACTERIA", "unit": "", "refRange": "NIL", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 27. Blood Group & Rh Factor
    # ─────────────────────────────────────────────────────────────
    {
        "key": "BLOOD_GROUP",
        "name": "Blood Group & Rh Factor",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood Group & Rh Factor", "Blood Group"],
        "tests": [
            {"name": "BLOOD GROUP", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "Rh FACTOR", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 28. HbA1c (Glycosylated Hemoglobin)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "HBA1C",
        "name": "HbA1c (Glycosylated Hemoglobin)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["HbA1c (Glycosylated Hemoglobin)", "HbA1c", "Glycosylated Haemoglobin"],
        "tests": [
            {"name": "HbA1c (GLYCOSYLATED HEMOGLOBIN)", "unit": "%", "refRange": "4.30–6.40", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 29. Urine Ketone
    # ─────────────────────────────────────────────────────────────
    {
        "key": "URINE_KETONE",
        "name": "Urine Ketone",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Urine Ketone"],
        "tests": [
            {"name": "URINE KETONE", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 30. D-Dimer
    # ─────────────────────────────────────────────────────────────
    {
        "key": "DDIMER",
        "name": "D-Dimer",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["D-Dimer"],
        "tests": [
            {"name": "D-DIMER", "unit": "µgFEU/mL", "refRange": "<0.5", "status": "Normal"},
        ],
        "remarks": (
            "D-dimer is elevated whenever the coagulation system has been activated. "
            "A negative test essentially rules out thrombosis. A positive test requires further workup."
        ),
    },
    # ─────────────────────────────────────────────────────────────
    # 31. Serum Amylase & Lipase
    # ─────────────────────────────────────────────────────────────
    {
        "key": "AMYLASE_LIPASE",
        "name": "Serum Amylase & Lipase",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Serum Amylase & Lipase", "Amylase & Lipase"],
        "tests": [
            {"name": "S. AMYLASE", "unit": "U/L", "refRange": "30.0–220.0", "status": "Normal"},
            {"name": "S. LIPASE", "unit": "U/L", "refRange": "Upto 190.0", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 32. Homocysteine (Quantitative)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "HOMOCYSTEINE",
        "name": "Homocysteine (Quantitative)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Homocysteine (Quantitative)", "Homocysteine"],
        "tests": [
            {"name": "HOMOCYSTEINE", "unit": "umol/L", "refRange": "5.45–16.20", "status": "Normal"},
        ],
        "remarks": "CVD patients with homocysteine > 15 umol/L belong to a high risk group.",
    },
    # ─────────────────────────────────────────────────────────────
    # 33. PSA (Prostate Specific Antigen)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "PSA",
        "name": "PSA (Prostate Specific Antigen)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["PSA (Prostate Specific Antigen)", "PSA"],
        "tests": [
            {"name": "PSA TOTAL, SERUM", "unit": "ng/mL", "refRange": "<4.00", "status": "Normal"},
        ],
        "remarks": "PSA values should be correlated with clinical findings and other investigations.",
    },
    # ─────────────────────────────────────────────────────────────
    # 34. Prothrombin Time (PT)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "PT",
        "name": "Prothrombin Time (PT)",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Prothrombin Time (PT)", "PT", "Prothrombin Time"],
        "tests": [
            {"name": "PATIENT TIME (PT)", "unit": "Sec", "refRange": "10.0–14.0", "status": "Normal"},
            {"name": "CONTROL TIME (PT)", "unit": "Sec", "refRange": "", "status": "Normal"},
            {"name": "INR (International Normalized Ratio)", "unit": "", "refRange": "0.8–1.2", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 35. Activated Partial Thromboplastin Time (APTT)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "APTT",
        "name": "Activated Partial Thromboplastin Time (APTT)",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Activated Partial Thromboplastin Time (APTT)", "APTT"],
        "tests": [
            {"name": "PATIENT TIME (APTT)", "unit": "Sec", "refRange": "26.0–40.0", "status": "Normal"},
            {"name": "CONTROL TIME (APTT)", "unit": "Sec", "refRange": "", "status": "Normal"},
            {"name": "RATIO (APTT)", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 36. Adenosine Deaminase (ADA)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "ADA",
        "name": "Adenosine Deaminase (ADA)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Adenosine Deaminase (ADA)", "ADA"],
        "tests": [
            {"name": "ADENOSINE DEAMINASE (ADA)", "unit": "U/L", "refRange": "Normal <30", "status": "Normal"},
        ],
        "remarks": (
            "Normal <30 U/L | Suspect: 30–40 U/L | Strong Suspect: 41–60 U/L | Positive >60 U/L. "
            "Increased ADA is found in Tuberculosis and various other infections. "
            "Result should be read in adjunct with clinical findings."
        ),
    },
    # ─────────────────────────────────────────────────────────────
    # 37. Body Fluid For Cytology
    # ─────────────────────────────────────────────────────────────
    {
        "key": "BODY_FLUID_CYTO",
        "name": "Body Fluid For Cytology",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Body Fluid For Cytology", "Body Fluid Cytology"],
        "tests": [
            {"name": "SPECIMEN TYPE", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CLINICAL NOTE", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "MICROSCOPIC EXAMINATION", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "IMPRESSION", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "ADVICE", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 38. Body Fluid Routine Analysis
    # ─────────────────────────────────────────────────────────────
    {
        "key": "BODY_FLUID_ROUTINE",
        "name": "Body Fluid Routine Analysis",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Body Fluid Routine Analysis", "Body Fluid Routine"],
        "tests": [
            {"name": "SAMPLE TYPE", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "VOLUME", "unit": "mL", "refRange": ">1.5 mL", "status": "Normal"},
            {"name": "COLOUR", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "APPEARANCE", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "COAGULUM", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "BLOOD", "unit": "", "refRange": "NEGATIVE", "status": "Normal"},
            {"name": "GLUCOSE", "unit": "mg/dL", "refRange": "", "status": "Normal"},
            {"name": "TOTAL PROTEIN", "unit": "gm/dL", "refRange": "", "status": "Normal"},
            {"name": "TLC, BODY FLUID", "unit": "/cumm", "refRange": "", "status": "Normal"},
            {"name": "DLC – NEUTROPHIL", "unit": "%", "refRange": "", "status": "Normal"},
            {"name": "DLC – LYMPHOCYTE", "unit": "%", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 39. SAAG (Serum Ascites Albumin Gradient)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "SAAG",
        "name": "SAAG (Serum Ascites Albumin Gradient)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["SAAG (Serum Ascites Albumin Gradient)", "SAAG"],
        "tests": [
            {"name": "ALBUMIN, SERUM", "unit": "gm/dL", "refRange": "3.50–5.50", "status": "Normal"},
            {"name": "ALBUMIN, FLUID", "unit": "gm/dL", "refRange": "", "status": "Normal"},
            {"name": "SAAG", "unit": "gm/dL", "refRange": "", "status": "Normal"},
        ],
        "remarks": "SAAG >= 1.1 g/dL indicates portal hypertension.",
    },
    # ─────────────────────────────────────────────────────────────
    # 40. Iron Profile
    # ─────────────────────────────────────────────────────────────
    {
        "key": "IRON_PROFILE",
        "name": "Iron Profile",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Iron Profile"],
        "tests": [
            {"name": "IRON, SERUM", "unit": "µg/dL", "refRange": "49–181", "status": "Normal"},
            {"name": "TIBC", "unit": "µg/dL", "refRange": "261–462", "status": "Normal"},
            {"name": "UNSATURATED IRON BINDING CAPACITY", "unit": "µg/dL", "refRange": "110.0–370.0", "status": "Normal"},
            {"name": "TRANSFERRIN SATURATION", "unit": "%", "refRange": "14–50", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 41. Blood Picture (Peripheral Smear)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "PERIPHERAL_SMEAR",
        "name": "Blood Picture (Peripheral Smear)",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Blood Picture (Peripheral Smear)", "Peripheral Smear"],
        "tests": [
            {"name": "RED CELL MORPHOLOGY", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "WBC MORPHOLOGY", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "PLATELET ASSESSMENT", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "HAEMOPARASITES", "unit": "", "refRange": "NONE SEEN", "status": "Normal"},
            {"name": "IMPRESSION", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # 42. Anti-TPO (Thyroid Peroxidase Antibody)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "ANTI_TPO",
        "name": "Anti-TPO (Thyroid Peroxidase Antibody)",
        "report_type": "Immunology – Serology",
        "report_category": "IMMUNOLOGY – SEROLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Anti-TPO (Thyroid Peroxidase Antibody)", "Anti-TPO"],
        "tests": [
            {"name": "Anti-TPO (Thyroid Peroxidase Antibody)", "unit": "", "refRange": "<0.9 Not Detected", "status": "Normal"},
        ],
        "remarks": (
            "<0.9: Not Detected | 0.9–1.1: Borderline | >1.1: Positive. "
            "Anti-TPO antibodies are indicative of Hashimoto's thyroiditis if present. "
            "Method: ELISA."
        ),
    },
    # ─────────────────────────────────────────────────────────────
    # 43. Bleeding Time (BT) & Clotting Time (CT)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "BT_CT",
        "name": "Bleeding Time (BT) & Clotting Time (CT)",
        "report_type": "Haematology",
        "report_category": "HAEMATOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Bleeding Time (BT) & Clotting Time (CT)", "BT & CT", "BT CT"],
        "tests": [
            {"name": "BT (Bleeding Time)", "unit": "Min/Sec", "refRange": "02–07", "status": "Normal"},
            {"name": "CT (Clotting Time)", "unit": "Min/Sec", "refRange": "04–09", "status": "Normal"},
        ],
    },
    # ─────────────────────────────────────────────────────────────
    # Radiology (generic – unchanged)
    # ─────────────────────────────────────────────────────────────
    {
        "key": "SPUTUM_AFB",
        "name": "Sputum for AFB",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["SPUTUM FOR AFB", "Sputum for AFB"],
        "tests": [
            {"name": "RESULT", "unit": "", "refRange": "NO ACID FAST BACILLI SEEN", "status": "Normal"},
        ],
    },
    {
        "key": "SPUTUM_GRAM",
        "name": "Sputum Gram Stain",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["SPUTUM GRAM STAIN", "Sputum Gram Stain"],
        "tests": [
            {"name": "RESULT", "unit": "", "refRange": "No pathogenic bacteria seen", "status": "Normal"},
        ],
    },
    {
        "key": "SPUTUM_CS",
        "name": "Sputum C/S (Culture & Sensitivity)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["SPUTUM C/S", "Sputum C/S (Culture & Sensitivity)"],
        "tests": [
            {"name": "SPECIMEN SOURCE", "unit": "", "refRange": "SPUTUM C/S", "status": "Normal"},
            {"name": "DATE RECEIVED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "DATE REPORTED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CULTURE RESULT", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "ANTIBIOTIC SENSITIVITY", "unit": "", "refRange": "Sensitive / Resistant", "status": "Normal"},
        ],
    },
    {
        "key": "STOOL_CS",
        "name": "Stool C/S (Culture & Sensitivity)",
        "report_type": "Microbiology",
        "report_category": "MICROBIOLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["STOOL C/S", "Stool C/S (Culture & Sensitivity)"],
        "tests": [
            {"name": "SPECIMEN SOURCE", "unit": "", "refRange": "STOOL C/S", "status": "Normal"},
            {"name": "DATE RECEIVED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "DATE REPORTED", "unit": "", "refRange": "", "status": "Normal"},
            {"name": "CULTURE RESULT", "unit": "", "refRange": "", "status": "Normal"},
        ],
    },
    {
        "key": "TFT",
        "name": "Thyroid Function Test (T3, FT4, TSH)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["Thyroid Function Test", "TFT", "T3 FT4 TSH"],
        "tests": [
            {"name": "T3", "unit": "pmol/L", "refRange": "0.9-2.5", "status": "Normal"},
            {"name": "Free Thyroxine (FT4)", "unit": "pmol/L", "refRange": "60-135", "status": "Normal"},
            {"name": "Thyroid Stimulating Hormone (TSH)", "unit": "pmol/L", "refRange": "0.25-5.0", "status": "Normal"},
        ],
    },
    {
        "key": "VITAMIN_B12",
        "name": "Vitamin B12 (Cyanocobalamin, Serum)",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["VITAMIN B-12", "Vitamin B12", "CYANOCOBALAMIN, SERUM"],
        "tests": [
            {"name": "VITAMIN B-12 CYANOCOBALAMIN, SERUM", "unit": "pg/ml", "refRange": "211-911", "status": "Normal"},
        ],
    },
    {
        "key": "VITAMIN_D3",
        "name": "25 OH Vitamin D3",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["25 OH VITAMIN D3", "Vitamin D3"],
        "tests": [
            {"name": "25 OH VITAMIN D3", "unit": "ng/ml", "refRange": "30-100", "status": "Normal"},
        ],
    },
    {
        "key": "D_DIMER",
        "name": "D-Dimer",
        "report_type": "Immunology – Serology",
        "report_category": "IMMUNOLOGY – SEROLOGY",
        "bill_category": "PATHOLOGY",
        "aliases": ["D-DIMER", "D Dimer", "D-Dimer"],
        "tests": [
            {"name": "D-DIMER", "unit": "", "refRange": "", "status": "Normal"},
        ],
        "remarks": "Interpret in clinical context for DVT/VTE/PE/DIC. Negative result helps exclude thrombosis; positive result requires confirmatory evaluation.",
    },
    {
        "key": "HOMOCYSTEINE",
        "name": "Homocysteine, Quantitative, Serum",
        "report_type": "Biochemistry",
        "report_category": "BIOCHEMISTRY",
        "bill_category": "PATHOLOGY",
        "aliases": ["HOMOCYSTEINE, QUANTITATIVE, SERUM", "Homocysteine"],
        "tests": [
            {"name": "HOMOCYSTEINE", "unit": "umol/L", "refRange": "5.45-16.20", "status": "Normal"},
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