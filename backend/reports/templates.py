# backend/patients/templates.py

DISCHARGE_TEMPLATES = {
    "NORMAL": {
        "title": "DISCHARGE SUMMARY",
        "sections": [
            {"key": "final_diagnosis", "label": "FINAL DIAGNOSIS :", "type": "textarea", "value": ""},
            {"key": "chief_complaints", "label": "CHIEF COMPLAINTS/REASON FOR ADMISSION :", "type": "textarea", "value": "Patient came/presented in hospital with complaints of - "},
            {"key": "k_c_o", "label": "K/C/O :", "type": "textarea", "value": ""},
            {"key": "clinical_examination", "label": "EXAMINATION :", "type": "vitals_grid", "value": {"bp": "", "pulse": "", "spo2": "", "temp": "", "chest": "", "cvs": "", "cns": "", "abd": "", "pallor": "", "icterus": ""}},
            {"key": "operations_procedures", "label": "OPERATIONS/PROCEDURES DONE :", "type": "textarea", "value": "None"},
            {"key": "course_in_hospital", "label": "COURSE IN HOSPITAL/CASE SUMMARY :", "type": "textarea", "value": ""},
            {"key": "investigations", "label": "INVESTIGATIONS :", "type": "textarea", "value": "All investigation is enclosed."},
            {"key": "condition_at_discharge", "label": "CONDITION AT DISCHARGE :", "type": "text", "value": "Fair & Stable."},
            {"key": "next_appointment", "label": "NEXT APPOINTMENT :", "type": "text", "value": "R/W after 5 days"},
            {"key": "treatment_advised", "label": "TREATMENT ADVISED :", "type": "textarea", "value": ""}
        ]
    },
    "LAMA": {
        "title": "LAMA SUMMARY",
        "sections": [
            {"key": "final_diagnosis", "label": "FINAL DIAGNOSIS :", "type": "textarea", "value": ""},
            {"key": "chief_complaints", "label": "CHIEF COMPLAINTS/REASON FOR ADMISSION :", "type": "textarea", "value": "Patient came/presented in hospital with complaints of - "},
            {"key": "k_c_o", "label": "K/C/O :", "type": "textarea", "value": ""},
            {"key": "clinical_examination", "label": "EXAMINATION :", "type": "vitals_grid", "value": {"bp": "", "pulse": "", "spo2": "", "temp": "", "chest": "", "cvs": "", "cns": "", "abd": "", "pallor": "", "icterus": ""}},
            {"key": "operations_procedures", "label": "OPERATIONS/PROCEDURES DONE :", "type": "textarea", "value": "None"},
            {"key": "course_in_hospital", "label": "COURSE IN HOSPITAL/CASE SUMMARY :", "type": "textarea", "value": ""},
            {"key": "investigations", "label": "INVESTIGATIONS :", "type": "textarea", "value": "All investigation is enclosed."},
            {"key": "condition_at_discharge", "label": "CONDITION AT DISCHARGE :", "type": "text", "value": "LAMA."}
        ]
    },
    "REFER": {
        "title": "REFER SUMMARY",
        "sections": [
            {"key": "final_diagnosis", "label": "FINAL DIAGNOSIS :", "type": "textarea", "value": ""},
            {"key": "chief_complaints", "label": "CHIEF COMPLAINTS/REASON FOR ADMISSION :", "type": "textarea", "value": "Patient came/presented in hospital with complaints of - "},
            {"key": "k_c_o", "label": "K/C/O :", "type": "textarea", "value": ""},
            {"key": "clinical_examination", "label": "EXAMINATION :", "type": "vitals_grid", "value": {"bp": "", "pulse": "", "spo2": "", "temp": "", "chest": "", "cvs": "", "cns": "", "abd": "", "pallor": "", "icterus": ""}},
            {"key": "operations_procedures", "label": "OPERATIONS/PROCEDURES DONE :", "type": "textarea", "value": "None"},
            {"key": "course_in_hospital", "label": "COURSE IN HOSPITAL/CASE SUMMARY :", "type": "textarea", "value": ""},
            {"key": "investigations", "label": "INVESTIGATIONS :", "type": "textarea", "value": "All investigation is enclosed."},
            {"key": "condition_at_discharge", "label": "CONDITION AT DISCHARGE :", "type": "text", "value": "REFER."}
        ]
    },
    "DOPR": {
        "title": "DOPR SUMMARY",
        "sections": [
            {"key": "final_diagnosis", "label": "FINAL DIAGNOSIS :", "type": "textarea", "value": ""},
            {"key": "chief_complaints", "label": "CHIEF COMPLAINTS/REASON FOR ADMISSION :", "type": "textarea", "value": "Patient came/presented in hospital with complaints of - "},
            {"key": "clinical_examination", "label": "EXAMINATION :", "type": "vitals_grid", "value": {"bp": "", "pulse": "", "spo2": "", "temp": "", "chest": "", "cvs": "", "cns": "", "abd": "", "pallor": "", "icterus": ""}},
            {"key": "operations_procedures", "label": "OPERATIONS/PROCEDURES DONE :", "type": "textarea", "value": "None"},
            {"key": "course_in_hospital", "label": "COURSE IN HOSPITAL/CASE SUMMARY :", "type": "textarea", "value": ""},
            {"key": "investigations", "label": "INVESTIGATIONS :", "type": "textarea", "value": "All investigation is enclosed."},
            {"key": "condition_at_discharge", "label": "CONDITION AT DISCHARGE :", "type": "text", "value": "DOPR."},
            {"key": "next_appointment", "label": "NEXT APPOINTMENT :", "type": "text", "value": "R/W after 5 days"},
            {"key": "treatment_advised", "label": "TREATMENT ADVISED :", "type": "textarea", "value": ""}
        ]
    },
    "DEATH": {
        "title": "DEATH SUMMARY",
        "sections": [
            {"key": "final_diagnosis", "label": "FINAL DIAGNOSIS :", "type": "textarea", "value": ""},
            {"key": "chief_complaints", "label": "CHIEF COMPLAINTS/REASON FOR ADMISSION :", "type": "textarea", "value": "Patient came/presented in hospital with complaints of - "},
            {"key": "k_c_o", "label": "K/C/O :", "type": "textarea", "value": ""},
            {"key": "clinical_examination", "label": "EXAMINATION :", "type": "vitals_grid", "value": {"bp": "", "pulse": "", "spo2": "", "temp": "", "chest": "", "cvs": "", "cns": "", "abd": "", "pallor": "", "icterus": ""}},
            {"key": "operations_procedures", "label": "OPERATIONS/PROCEDURES DONE :", "type": "textarea", "value": "None"},
            {"key": "course_in_hospital", "label": "COURSE IN HOSPITAL/CASE SUMMARY :", "type": "textarea", "value": ""},
            {"key": "investigations", "label": "INVESTIGATIONS :", "type": "textarea", "value": "All investigation is enclosed."},
            {"key": "condition_at_discharge", "label": "CONDITION AT DISCHARGE :", "type": "text", "value": "DEATH."}
        ]
    }
}