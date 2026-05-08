import os
import django
import pandas as pd
import math

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sangi_hospital.settings")
django.setup()

from patients.models import MedicineMaster, ReportMaster

def import_data():
    # Pointing exactly to your Excel file in the data folder
    excel_file_path = os.path.join(os.path.dirname(__file__), "data", "medicine_report.xlsx")
    
    print("--- Starting Medicine Import ---")
    MedicineMaster.objects.all().delete()
    
    try:
        # Read the excel file natively
        df = pd.read_excel(excel_file_path, header=None)
        
        # Find the row that contains our headers
        header_row_idx = None
        for idx, row in df.iterrows():
            row_str = " ".join([str(val).lower() for val in row.values])
            if "description" in row_str and "batch" in row_str:
                header_row_idx = idx
                break
                
        if header_row_idx is not None:
            # Re-read the dataframe using the correct header row
            df = pd.read_excel(excel_file_path, header=header_row_idx)
            
            count = 0
            for _, row in df.iterrows():
                desc = str(row.get('Description', '')).strip()
                
                # Skip empty or footer rows
                if not desc or str(desc).lower() == 'nan' or "end of" in desc.lower() or "total" in desc.lower():
                    continue
                
                # Handle potential NaN values
                batch = str(row.get('Batch No.', ''))
                batch = "" if batch.lower() == 'nan' else batch.strip()
                
                exp = str(row.get('Exp.', ''))
                exp = "" if exp.lower() == 'nan' else exp.strip()
                
                rate_val = row.get('Rate', 0)
                try:
                    rate = float(rate_val) if not math.isnan(float(rate_val)) else 0.00
                except (ValueError, TypeError):
                    rate = 0.00
                
                MedicineMaster.objects.create(name=desc, batch_no=batch, expiry_date=exp, rate=rate)
                count += 1
                
            print(f"✅ Successfully imported {count} medicines!")
        else:
            print("❌ Could not find the 'Description' header in the Excel file.")
            
    except Exception as e:
        print(f"Error importing medicines: {e}")

    print("\n--- Populating Lab Reports ---")
    ReportMaster.objects.all().delete()
    
    # NOTE: These names MUST exactly match the "name" field of the corresponding
    # template in report_templates.py so the frontend dropdown and template
    # lookup (get_template_by_label) stay in sync.
    reports_list = [
        "Complete Blood Count (CBC)",
        "Kidney Function Test (KFT)",
        "Liver Function Test (LFT)",
        "Lipid Profile",
        "Blood Gas Analysis",
        "CRP (Qualitative)",
        "Blood Glucose (Random)",
        "Blood Glucose (Fasting)",
        "Widal Test (Slide Method)",
        "Malaria Antigen Test",
        "Typhi Dot (IgG & IgM)",
        "Dengue (IgM & IgG)",
        "Dengue NS1 Antigen Test",
        "Viral Markers (HIV, HBsAg, HCV)",
        "COVID-19 Rapid Antigen",
        "Urine Examination (Routine)",
        "Urine Gram Stain",
        "Aerobic Culture & Sensitivity",
        "Serum Procalcitonin",
        "Sputum for AFB",
        "Sputum Gram Stain",
        "Cardiac Markers (Trop-T, Trop-I, CPK)",
        "Total Thyroid Profile",
        "Vitamin B-12 (Cyanocobalamin)",
        "25 OH Vitamin D3",
        "Stool Examination",
        "Blood Group & Rh Factor",
        "HbA1c (Glycosylated Hemoglobin)",
        "Urine Ketone",
        "D-Dimer",
        "Serum Amylase & Lipase",
        "Homocysteine (Quantitative)",
        "PSA (Prostate Specific Antigen)",
        "Prothrombin Time (PT)",
        "Activated Partial Thromboplastin Time (APTT)",
        "Adenosine Deaminase (ADA)",
        "Body Fluid For Cytology",
        "Body Fluid Routine Analysis",
        "SAAG (Serum Ascites Albumin Gradient)",
        "Iron Profile",
        "Blood Picture (Peripheral Smear)",
        "Anti-TPO (Thyroid Peroxidase Antibody)",
        "Bleeding Time (BT) & Clotting Time (CT)",
    ]
    
    for report_name in reports_list:
        ReportMaster.objects.create(name=report_name)
    
    print(f"✅ {len(reports_list)} reports ready.")

if __name__ == '__main__':
    import_data()