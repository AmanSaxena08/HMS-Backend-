import os, base64, io, copy, qrcode
import datetime
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from rest_framework import generics, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from xhtml2pdf import pisa
from patients.models import Patient, Admission, MedicalHistory, Discharge, Billing
from master.models import HospitalSettings, MedicineMaster
from core.utils import get_or_create_current_billing
from .models import LabReport, DischargeSummary, PharmacyRecord, ReportMaster
from .serializers import LabReportSerializer, DischargeSummarySerializer, PharmacyRecordSerializer, ReportMasterSerializer
from .templates import DISCHARGE_TEMPLATES
from .report_templates import build_suggested_reports_for_admission, build_report_from_template, get_template_by_label
from tasks.models import Task

# Create your views here.

def _prefill_sections_from_db(sections, admission):
    """
    Walk through all sections of a discharge summary template and fill in
    values from the already-saved MedicalHistory and Discharge models.
 
    This is called both when serving a fresh template (GET, no saved summary)
    AND when printing without a saved summary, so the PDF always has real data.
 
    Only fills a section if it currently has an empty or default value —
    never overwrites something the user explicitly typed and saved.
    """
    med = getattr(admission, 'medicalHistory', None)
    discharge = getattr(admission, 'discharge', None)
 
    # Map each section key → where the real data lives in the DB
    # Left side = section key in DISCHARGE_TEMPLATES
    # Right side = lambda(med, discharge) → the value to use
    DB_FIELD_MAP = {
        # Filled by receptionist at admission time (MedicalHistory model)
        'final_diagnosis': lambda m, d: (
            getattr(m, 'provisionalDiagnosis', '') or
            getattr(d, 'diagnosis', '') or ''
        ),
        'chief_complaints': lambda m, d: (
            getattr(m, 'chiefComplaints', '') or
            getattr(m, 'presentComplaints', '') or ''
        ),
        'k_c_o': lambda m, d: getattr(m, 'previousDiagnosis', '') or '',
        'operations_procedures': lambda m, d: getattr(m, 'treatmentAdvised', '') or '',
        'treatment_advised': lambda m, d: getattr(m, 'treatmentAdvised', '') or '',
        'investigations': lambda m, d: getattr(m, 'investigations', '') or '',
        'course_in_hospital': lambda m, d: getattr(m, 'notes', '') or '',
 
        # Filled by receptionist at discharge time (Discharge model)
        'condition_at_discharge': lambda m, d: (
            d.dischargeStatus.upper() if d and d.dischargeStatus else ''
        ),
 
        # Vitals grid — map all vitals from MedicalHistory into the dict
        'clinical_examination': lambda m, d: {
            'bp':     getattr(m, 'bp', '')    or '',
            'pulse':  getattr(m, 'pulse', '') or getattr(m, 'pr', '') or '',
            'spo2':   getattr(m, 'spo2', '')  or '',
            'temp':   getattr(m, 'temp', '')  or '',
            'chest':  getattr(m, 'chest', '') or '',
            'cvs':    getattr(m, 'cvs', '')   or '',
            'cns':    getattr(m, 'cns', '')   or '',
            'abd':    getattr(m, 'pa', '')    or '',  # P/A maps to abd
            'pallor': '',
            'icterus': '',
        } if m else None,
    }
 
    for section in sections:
        key = section.get('key')
        if key not in DB_FIELD_MAP:
            continue
 
        getter = DB_FIELD_MAP[key]
        db_value = getter(med, discharge)
 
        if not db_value:
            # Nothing in DB for this field, leave the template default alone
            continue
 
        current_value = section.get('value', '')
 
        if section.get('type') == 'vitals_grid':
            # For vitals: merge DB values into the existing dict
            # Don't overwrite if user already put something there
            if isinstance(current_value, dict):
                merged = {}
                for vkey, vval in current_value.items():
                    # Use DB value only if the current slot is empty
                    merged[vkey] = vval if vval else db_value.get(vkey, '')
                section['value'] = merged
            else:
                section['value'] = db_value
 
        elif isinstance(current_value, str):
            # For text/textarea: only fill if current value is empty
            # or is one of the generic template placeholders
            GENERIC_PREFIXES = (
                'Patient came/presented in hospital with complaints of -',
                'All investigation is enclosed.',
                'Fair & Stable.',
                'R/W after 5 days',
                'None',
                'LAMA.',
                'REFER.',
                'DOPR.',
                'DEATH.',
            )
            is_generic = not current_value.strip() or any(
                current_value.strip().startswith(p) for p in GENERIC_PREFIXES
            )
            if is_generic:
                section['value'] = db_value
 
    return sections
 
 
def _clean_discharge_status(raw_status):
    s = str(raw_status).upper()
    if 'LAMA' in s:  return 'LAMA'
    if 'DOPR' in s:  return 'DOPR'
    if 'REFER' in s: return 'REFER'
    if 'DEATH' in s: return 'DEATH'
    return 'NORMAL'


class LabReportListCreateView(generics.ListCreateAPIView):
    serializer_class = LabReportSerializer

    def get_queryset(self):
        uhid = self.kwargs.get('uhid')
        adm_no = self.kwargs.get('adm_no')
        return LabReport.objects.filter(patient__uhid=uhid, admission__admNo=adm_no).order_by('report_date', 'id')

    def perform_create(self, serializer):
        uhid = self.kwargs.get('uhid')
        adm_no = self.kwargs.get('adm_no')
        
        patient = get_object_or_404(Patient, uhid=uhid)

        user = self.request.user
        if user.role == 'admin':
            if patient.branch_location != user.branch:
                raise PermissionDenied("You are not authorized to modify reports for this patient.")
        elif user.role == 'receptionist':
            if patient.branch_location != getattr(user, 'branch', None):
                raise PermissionDenied("You can only add reports for patients in your branch.")
        elif user.role not in ['superadmin', 'office_admin', 'hod']:
            is_assigned = Task.objects.filter(
                patient=patient,
                assigned_to=user
            ).exists()
            if not is_assigned:
                raise PermissionDenied("You are not authorized to modify reports for this patient.")

        admission = get_object_or_404(Admission, patient=patient, admNo=adm_no)

        lookup = {
            'patient': patient,
            'admission': admission,
            'report_name': serializer.validated_data.get('report_name'),
            'report_type': serializer.validated_data.get('report_type', ''),
            'report_date': serializer.validated_data.get('report_date'),
        }
        defaults = {
            **serializer.validated_data,
            'created_by': self.request.user.first_name or self.request.user.username,
        }
        report, _ = LabReport.objects.update_or_create(defaults=defaults, **lookup)
        serializer.instance = report

class LabReportBulkSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uhid, adm_no):
        patient = get_object_or_404(Patient, uhid=uhid)

        user = request.user
        if user.role == 'admin':
            if patient.branch_location != user.branch:
                return Response({'error': 'You are not authorized to modify reports for this patient.'}, status=status.HTTP_403_FORBIDDEN)
        elif user.role == 'receptionist':
            if patient.branch_location != getattr(user, 'branch', None):
                return Response({'error': 'You can only add reports for patients in your branch.'}, status=status.HTTP_403_FORBIDDEN)
        elif user.role not in ['superadmin', 'office_admin', 'hod']:
            is_assigned = Task.objects.filter(
                patient=patient,
                assigned_to=user
            ).exists()
            if not is_assigned:
                return Response({'error': 'You are not authorized to modify reports for this patient.'}, status=status.HTTP_403_FORBIDDEN)

        admission = get_object_or_404(Admission, patient=patient, admNo=adm_no)
        reports = request.data.get('reports') or []

        created_by = request.user.first_name or request.user.username
        created_reports = []

        with transaction.atomic():
            LabReport.objects.filter(patient=patient, admission=admission).delete()

            for report in reports:
                # ── Ghost Prevention: Do not save completely empty templates ──
                has_data = False
                
                if str(report.get('remarks', '')).strip():
                    has_data = True
                if str(report.get('findings', '')).strip() or str(report.get('impression', '')).strip():
                    has_data = True
                    
                md = report.get('modality_details', {})
                if isinstance(md, dict) and (str(md.get('findings', '')).strip() or str(md.get('impression', '')).strip()):
                    has_data = True
                
                tests = report.get('tests', []) or report.get('table_data', [])
                if isinstance(tests, list):
                    for t in tests:
                        val = str(t.get('value', '')).strip()
                        if val and val not in ('-', 'N/A', 'None'):
                            has_data = True
                            break
                            
                if not has_data:
                    continue

                serializer = LabReportSerializer(data=report)
                serializer.is_valid(raise_exception=True)
                created_reports.append(LabReport(
                    patient=patient,
                    admission=admission,
                    created_by=created_by,
                    **serializer.validated_data,
                ))

            if created_reports:
                LabReport.objects.bulk_create(created_reports)

        payload = LabReportSerializer(
            LabReport.objects.filter(patient=patient, admission=admission).order_by('report_date', 'id'),
            many=True,
        ).data
        return Response(payload, status=status.HTTP_200_OK)


class LabReportTemplateSuggestionsAPIView(APIView):
    permission_classes = [IsAuthenticated]
 
    def get(self, request, uhid, adm_no):
        patient   = get_object_or_404(Patient, uhid=uhid)
        admission = get_object_or_404(Admission, patient=patient, admNo=adm_no)
 
        medical_history = getattr(admission, 'medicalHistory', None)
        ordered_by      = getattr(medical_history, 'treatingDoctor', '') if medical_history else ''
 
        results = []
 
        # ── Step 1: Already-saved lab reports for this admission ──────────────
        # These come first — receptionist already added these for this patient.
        # Build them from the saved LabReport rows (real data, already filled).
        saved_report_names = set()
        for lab in admission.lab_reports.all().order_by('id'):
            # Try to merge with a rich template for consistent structure
            template = get_template_by_label(lab.report_name)
            md = lab.modality_details if isinstance(lab.modality_details, dict) else {}
            
            # ── Check if this saved report actually has data (Ghost Prevention) ──
            has_data = False
            if lab.remarks and str(lab.remarks).strip():
                has_data = True
            elif md.get('findings', '').strip() or md.get('impression', '').strip():
                has_data = True
            else:
                tests = lab.table_data if isinstance(lab.table_data, list) else []
                for test in tests:
                    val = str(test.get('value', '')).strip()
                    if val and val not in ('-', 'N/A', 'None'):
                        has_data = True
                        break
            
            if not has_data:
                # Skip empty ghost reports! (They will be picked up fresh as unsaved if recommended)
                continue

            saved_report_names.add(lab.report_name.strip().casefold())

            if template:
                report = build_report_from_template(
                    template, patient=patient, admission=admission, ordered_by=ordered_by
                )
                # Overlay the actual saved values on top of the template structure
                report['id']          = lab.id
                report['amount']      = lab.amount or 0
                report['remarks']     = lab.remarks or ''
                report['findings']    = md.get('findings', '')
                report['impression']  = md.get('impression', '')
                if isinstance(lab.table_data, list) and lab.table_data:
                    report['tests']   = lab.table_data
                report['is_saved']    = True
                report['is_recommended'] = True
            else:
                # No hardcoded template — use the raw saved data
                report = {
                    'id':             lab.id,
                    'reportName':     lab.report_name,
                    'reportType':     lab.report_type or 'Custom',
                    'reportCategory': getattr(lab, 'report_category', 'CUSTOM') or 'CUSTOM',
                    'billCategory':   getattr(lab, 'bill_category', 'PATHOLOGY') or 'PATHOLOGY',
                    'date':           lab.report_date.isoformat() if lab.report_date else timezone.localdate().isoformat(),
                    'orderedBy':      lab.ordered_by or ordered_by or '',
                    'amount':         lab.amount or 0,
                    'remarks':        lab.remarks or '',
                    'findings':       md.get('findings', ''),
                    'impression':     md.get('impression', ''),
                    'tests':          lab.table_data if isinstance(lab.table_data, list) else [],
                    'patientUhid':    patient.uhid,
                    'patientName':    patient.patientName,
                    'admNo':          admission.admNo,
                    'is_saved':       True,
                    'is_recommended': True,
                }
            results.append(report)
 
        # ── Step 2: Unsaved suggested reports from Medical History & Services ─
        def _split_text(raw):
            if not raw:
                return []
            parts = []
            for chunk in str(raw).replace('\r', '\n').split('\n'):
                for piece in chunk.replace('|', ',').replace(';', ',').split(','):
                    cleaned = piece.strip()
                    if cleaned:
                        parts.append(cleaned)
            return parts

        suggested_names = []
        if medical_history and medical_history.investigations:
            for token in _split_text(medical_history.investigations):
                if token.casefold() not in saved_report_names:
                    suggested_names.append(token)
                    saved_report_names.add(token.casefold())

        for svc in admission.services.all():
            cat_lower = (svc.svcCat or '').lower()
            if any(key in cat_lower for key in ('pathology', 'radiology', 'lab', 'test', 'scan', 'x-ray', 'xray', 'ultrasound', 'mri', 'ct scan')):
                svc_name = svc.svcName.strip()
                if svc_name and svc_name.casefold() not in saved_report_names:
                    suggested_names.append(svc_name)
                    saved_report_names.add(svc_name.casefold())

        for name in suggested_names:
            template = get_template_by_label(name)
            if template:
                report = build_report_from_template(
                    template, patient=patient, admission=admission, ordered_by=ordered_by
                )
            else:
                report = {
                    'reportName':     name,
                    'reportType':     'Custom',
                    'reportCategory': 'CUSTOM',
                    'billCategory':   'PATHOLOGY',
                    'date':           timezone.localdate().isoformat(),
                    'orderedBy':      ordered_by or '',
                    'amount':         0,
                    'remarks':        '',
                    'findings':       '',
                    'impression':     '',
                    'tests':          [],
                    'patientUhid':    patient.uhid,
                    'patientName':    patient.patientName,
                    'admNo':          admission.admNo,
                }
            
            report['is_saved'] = False
            report['is_recommended'] = True
            results.append(report)

        return Response(
            {
                'patient':           patient.uhid,
                'admNo':             admission.admNo,
                'suggested_reports': results,
            },
            status=status.HTTP_200_OK,
        )
 
    
class DynamicDischargeSummaryView(APIView):
 
    def get(self, request, uhid, adm_no):
        """
        Load discharge summary for editing in the frontend form.
        - If a saved summary exists → return it as-is (user's work is preserved).
        - If no saved summary → return the template pre-filled with ALL data
          already in the DB (vitals, complaints, diagnosis, etc.) so the
          billing/office employee doesn't have to re-type what the receptionist
          already entered.
        """
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        existing_summary = DischargeSummary.objects.filter(admission=admission).first()
 
        if existing_summary:
            # User has already worked on this summary — return exactly as saved
            return Response({
                'is_existing': True,
                'summary_type': existing_summary.summary_type,
                'content': existing_summary.content,
            }, status=status.HTTP_200_OK)
 
        # No saved summary yet — build fresh template and pre-fill from DB
        discharge = getattr(admission, 'discharge', None)
        raw_type = request.query_params.get('type', 'NORMAL')
        # Auto-detect summary type from discharge status if not explicitly passed
        if discharge and discharge.dischargeStatus:
            summary_type = _clean_discharge_status(discharge.dischargeStatus)
        else:
            summary_type = _clean_discharge_status(raw_type)
 
        template = copy.deepcopy(
            DISCHARGE_TEMPLATES.get(summary_type, DISCHARGE_TEMPLATES['NORMAL'])
        )
 
        # Pre-fill ALL sections from MedicalHistory + Discharge
        template['sections'] = _prefill_sections_from_db(template['sections'], admission)
 
        return Response({
            'is_existing': False,
            'summary_type': summary_type,
            'content': template,
        }, status=status.HTTP_200_OK)
 
    def post(self, request, uhid, adm_no):
        """Save the discharge summary (create or update)."""
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        raw_type = request.data.get('summary_type', 'NORMAL')
        summary_type = _clean_discharge_status(raw_type)
        content = request.data.get('content', {})
 
        summary, created = DischargeSummary.objects.update_or_create(
            admission=admission,
            defaults={
                'summary_type': summary_type,
                'content': content,
                'created_by': request.user if request.user.is_authenticated else None,
            }
        )
        return Response({
            'message': 'Discharge Summary saved successfully!',
            'data': DischargeSummarySerializer(summary).data,
        }, status=status.HTTP_200_OK)
 
 
class PrintDischargeSummaryView(APIView):
 
    def get(self, request, uhid, adm_no):
        """
        Generate discharge summary PDF.
        - Uses saved DischargeSummary.content if it exists.
        - If no saved summary, builds from template and pre-fills from DB —
          so the print always has real patient data even if nobody explicitly
          saved the summary form.
        """
        import io
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        from xhtml2pdf import pisa
 
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        summary = DischargeSummary.objects.filter(admission=admission).first()
 
        if summary:
            sections = summary.content.get('sections', [])
            summary_type = summary.summary_type
        else:
            # No saved summary — build and pre-fill from DB so PDF has real data
            discharge = getattr(admission, 'discharge', None)
            raw_status = getattr(discharge, 'dischargeStatus', 'NORMAL')
            summary_type = _clean_discharge_status(raw_status)
 
            template = copy.deepcopy(
                DISCHARGE_TEMPLATES.get(summary_type, DISCHARGE_TEMPLATES['NORMAL'])
            )
            template['sections'] = _prefill_sections_from_db(template['sections'], admission)
            sections = template['sections']
 
            # Build a temporary (unsaved) summary object for context
            summary = DischargeSummary(
                admission=admission,
                summary_type=summary_type,
                content={'sections': sections},
            )
 
        # Handle legacy dict format (old DB records stored sections as dict, not list)
        if isinstance(sections, dict):
            sections = [{'key': k, **v} for k, v in sections.items()]
 
        # Always sync condition_at_discharge from the live Discharge model
        discharge = getattr(admission, 'discharge', None)
        if discharge and discharge.dischargeStatus:
            for section in sections:
                if section.get('key') == 'condition_at_discharge':
                    section['value'] = discharge.dischargeStatus.upper()
 
        patient = admission.patient
 
        # FIX: billing is now OneToOneField with related_name='billing'
        billing = getattr(admission, 'billing', None)
 
        age = '--'
        if patient.dob:
            calc_age = (timezone.now().date() - patient.dob).days // 365
            age = f'{calc_age} YRS'
 
        status_map = {
            'NORMAL':    'pdf/normal.html',
            'RECOVERED': 'pdf/normal.html',
            'LAMA':      'pdf/lama.html',
            'REFER':     'pdf/refer.html',
            'DOPR':      'pdf/dopr.html',
            'DEATH':     'pdf/death.html',
        }
        template_file = status_map.get(summary_type, 'pdf/normal.html')
 
        context = {
            's':                  summary,
            'sections':           sections,
            'uhid':               patient.uhid,
            'ipd_no':             admission.ipdNo,
            'patient_name':       patient.patientName.upper(),
            'guardian_name':      patient.guardianName.upper() if patient.guardianName else '--',
            'address':            patient.address,
            'consultant':         (
                discharge.doctorName.upper() if discharge and discharge.doctorName
                else (
                    getattr(getattr(admission, 'medicalHistory', None), 'treatingDoctor', '') or '--'
                ).upper()
            ),
            'claim_id':           patient.tpaPanelCardNo or '--',
            'doa':                admission.dateTime.strftime('%d-%m-%Y %H:%M HRS') if admission.dateTime else '--',
            'dod':                discharge.dod.strftime('%d-%m-%Y %H:%M HRS') if (discharge and discharge.dod) else '--',
            'bill_no':            f'{billing.id}/{admission.dateTime.strftime("%y")}' if billing else '--',
            'bill_date':          discharge.dod.strftime('%d-%m-%Y %H:%M HRS') if (discharge and discharge.dod) else '--',
            'age_sex':            f'{age} / {patient.gender.upper()}',
            'card_no':            patient.tpaCard or '--',
            'room':               (
                f'{discharge.roomNo} / {discharge.wardName.upper()}'
                if discharge and discharge.roomNo else '-- / --'
            ),
            'panel':              (
                patient.tpa.upper() if patient.tpa
                else (admission.payMode.upper() if admission.payMode else 'CASH')
            ),
            'contact_no':         patient.phone,
            'status_on_discharge': discharge.dischargeStatus.upper() if (discharge and discharge.dischargeStatus) else '--',
        }
 
        html_string = render_to_string(template_file, context)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html_string.encode('UTF-8')), result)
 
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{uhid}_summary.pdf"'
            return response
 
        return Response({'error': 'PDF Generation Failed'}, status=400)

def _build_patient_header_context(admission, summary_label):
    patient = admission.patient
    discharge = getattr(admission, 'discharge', None)
    billing = getattr(admission, 'billing', None)

    age = "--"
    if patient.dob:
        calc_age = (timezone.now().date() - patient.dob).days // 365
        age = f"{calc_age} YRS"

    adm_pay_mode = str(getattr(admission, 'payMode', '') or '').lower()
    is_cashless = adm_pay_mode == 'cashless'

    return {
        "s": {"summary_type": summary_label},
        "uhid": patient.uhid,
        "ipd_no": admission.ipdNo or "--",
        "patient_name": (patient.patientName or "").upper(),
        "guardian_name": (patient.guardianName or "--").upper() if patient.guardianName else "--",
        "address": patient.address or "--",
        "consultant": (
            discharge.doctorName.upper() if (discharge and discharge.doctorName)
            else (
                admission.medicalHistory.treatingDoctor.upper()
                if hasattr(admission, 'medicalHistory') and admission.medicalHistory and admission.medicalHistory.treatingDoctor
                else "--"
            )
        ),
        "claim_id": patient.tpaPanelCardNo or "--",
        "doa": admission.dateTime.strftime("%d-%m-%Y %H:%M HRS") if admission.dateTime else "--",
        "dod": discharge.dod.strftime("%d-%m-%Y %H:%M HRS") if (discharge and discharge.dod) else "--",
        "bill_no": f"{billing.id}/{admission.dateTime.strftime('%y')}" if (billing and admission.dateTime) else "--",
        "bill_date": discharge.dod.strftime("%d-%m-%Y %H:%M HRS") if (discharge and discharge.dod) else "--",
        "age_sex": f"{age} / {(patient.gender or '').upper()}",
        "card_no": patient.tpaCard or "--",
        "room": (f"{discharge.roomNo} / {discharge.wardName.upper()}" if (discharge and discharge.roomNo) else "-- / --"),
        "panel": (patient.tpa.upper() if patient.tpa else (patient.payMode or "--").upper()),
        "contact_no": patient.phone or "--",
        "status_on_discharge": (discharge.dischargeStatus.upper() if (discharge and discharge.dischargeStatus) else "--"),
        "is_cashless": is_cashless,
        "patient": patient,
        "admission": admission,
        "discharge": discharge,
    }


def _render_pdf(template_file, context, filename_suffix, uhid):
    html_string = render_to_string(template_file, context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)
    if pdf.err:
        return Response({"error": "PDF Generation Failed"}, status=status.HTTP_400_BAD_REQUEST)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{uhid}_{filename_suffix}.pdf"'
    return response

class PrintBillView(APIView):
    # If you want to test this easily in the browser without a token, uncomment the line below temporarily:
    permission_classes = [] 

    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        patient = admission.patient
        discharge = getattr(admission, 'discharge', None)
        
        billing_obj, _ = get_or_create_current_billing(admission)
        services = admission.services.all().order_by('svcDate', 'id')

        # 🧮 1. Calculate Totals
        gross_total = sum((svc.svcTot or 0) for svc in services)
        discount = billing_obj.discount or Decimal('0.00')
        advance = billing_obj.advance or Decimal('0.00')
        net_payable = gross_total - discount - advance

        age = "--"
        if patient.dob:
            calc_age = (timezone.now().date() - patient.dob).days // 365
            age = f"{calc_age} YRS"

        # 🌟 2. Fetch Dynamic Hospital Settings based on the PATIENT'S BRANCH!
        settings_obj = HospitalSettings.objects.filter(branch=patient.branch_location).first()
        
        # Fallback just in case the Admin hasn't created settings for this branch yet
        if not settings_obj:
            settings_obj = HospitalSettings.objects.first()

        logo_base64 = ""
        
        # First, try to use the logo uploaded via the Admin panel
        if settings_obj and settings_obj.logo and hasattr(settings_obj.logo, 'path'):
            if os.path.exists(settings_obj.logo.path):
                with open(settings_obj.logo.path, "rb") as image_file:
                    logo_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        
        # If no custom logo is uploaded, fallback to the default static logo
        if not logo_base64:
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as image_file:
                    logo_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        # 🌟 3. Generate the QR Code dynamically (using the dynamic website URL!)
        qr_url = settings_obj.website if settings_obj and settings_obj.website else "https://sangihospital.com/"
        qr = qrcode.make(qr_url)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # 🌟 4. Safely handle Room/Ward to prevent NoneType crash if patient isn't discharged
        safe_room = discharge.roomNo if discharge and discharge.roomNo else '--'
        safe_ward = discharge.wardName.upper() if discharge and discharge.wardName else '--'
        room_ward = f"{safe_room} / {safe_ward}"

        # 📋 5. Build the context for the HTML template
        context = {
            "current_date": timezone.now().strftime("%d/%m/%Y"),
            "admission_type": admission.admissionType.upper(),
            "uhid": patient.uhid,
            "bill_no": f"{billing_obj.id}/{admission.dateTime.strftime('%y')}" if billing_obj else "--",
            "ipd_no": admission.ipdNo or "--",
            "bill_date": timezone.now().strftime("%d/%m/%Y %H:%M HRS"),
            "patient_name": patient.patientName.upper(),
            "age_sex": f"{age} / {patient.gender.upper()}",
            "guardian_name": patient.guardianName.upper() if patient.guardianName else "--",
            "address": patient.address or "--",
            "consultant": discharge.doctorName.upper() if discharge and discharge.doctorName else "--",
            "room_ward": room_ward,
            "claim_id": patient.tpaPanelCardNo or "--",
            "panel": patient.tpa.upper() if patient.tpa else (admission.payMode.upper() if admission.payMode else 'CASH'),
            "doa": timezone.localtime(admission.dateTime).strftime("%d/%m/%Y, %I:%M %p") if admission.dateTime else "--",
            "contact_no": patient.phone or "--",
            "dod": timezone.localtime(discharge.dod).strftime("%d/%m/%Y, %I:%M %p") if discharge and discharge.dod else "--",
            "discharge_status": discharge.dischargeStatus.upper() if discharge and discharge.dischargeStatus else "--",
            
            # The Data & Math
            "services": services,
            "gross_total": f"{gross_total:,.2f}",
            "discount": f"{discount:,.2f}",
            "advance": f"{advance:,.2f}",
            "net_payable": f"{net_payable:,.2f}",
            
            # The Images
            "qr_code": qr_base64,
            "logo_base64": logo_base64,
            "hospital": settings_obj, 
        }

        # 🖨️ 6. Render the PDF
        html_string = render_to_string("pdf/bill.html", context)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{patient.uhid}_final_bill.pdf"'
            return response
            
        return Response({"error": "PDF Generation Failed"}, status=status.HTTP_400_BAD_REQUEST)
    
class PrintMedicalHistoryView(APIView):
    permission_classes = []

    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        ctx = _build_patient_header_context(admission, "MEDICAL HISTORY")
        ctx["medical"] = getattr(admission, 'medicalHistory', None)
        return _render_pdf("pdf/medical_history.html", ctx, "medical_history", uhid)
    
class PrintLabReportsView(APIView):
    permission_classes = []

    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        ctx = _build_patient_header_context(admission, "LAB / RADIOLOGY REPORTS")
        reports = list(admission.lab_reports.all().order_by('report_date', 'id'))
        report_rows = []
        total_amount = Decimal("0.00")
        for rep in reports:
            md = rep.modality_details if isinstance(rep.modality_details, dict) else {}
            report_rows.append({
                "report_name": rep.report_name or "Report",
                "report_type": rep.report_type or "",
                "report_category": rep.report_category or "",
                "report_date": rep.report_date.strftime("%d-%m-%Y") if rep.report_date else "--",
                "ordered_by": rep.ordered_by or "--",
                "amount": rep.amount or Decimal("0.00"),
                "remarks": rep.remarks or "",
                "findings": md.get("findings", ""),
                "impression": md.get("impression", ""),
                "tests": rep.table_data if isinstance(rep.table_data, list) else [],
            })
            try:
                total_amount += Decimal(str(rep.amount or 0))
            except (InvalidOperation, TypeError):
                pass
        ctx["reports"] = report_rows
        ctx["total_amount"] = f"{total_amount:,.2f}"
        return _render_pdf("pdf/lab_reports.html", ctx, "lab_reports", uhid)

class PrintPharmacyRecordsView(APIView):
    permission_classes = []

    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        ctx = _build_patient_header_context(admission, "PHARMACY / MEDICINE BILL")
        records = list(admission.pharmacy_records.all().order_by('id'))
        rows = []
        total_amount = Decimal("0.00")
        for rec in records:
            qty = Decimal(str(rec.quantity or 0))
            rate = Decimal(str(rec.rate or 0))
            line_total = qty * rate
            rows.append({
                "medicine_name": rec.medicine_name or "Medicine",
                "date_given": rec.date_given or "--",
                "quantity": int(rec.quantity or 0),
                "rate": rate,
                "amount": line_total,
                "batch_no": rec.batch_no or "--",
                "expiry_date": rec.expiry_date or "--",
            })
            total_amount += line_total
        ctx["medicines"] = rows
        ctx["total_amount"] = f"{total_amount:,.2f}"
        return _render_pdf("pdf/pharmacy_records.html", ctx, "pharmacy_records", uhid)

class PharmacyRecordViewSet(viewsets.ModelViewSet):
    serializer_class = PharmacyRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Using exact kwarg names 'uhid' and 'adm_no' from urls.py
        return PharmacyRecord.objects.filter(
            patient__uhid=self.kwargs['uhid'],
            admission__admNo=self.kwargs['adm_no']
        )

    def perform_create(self, serializer):
        patient = get_object_or_404(Patient, uhid=self.kwargs['uhid'])
        admission = get_object_or_404(Admission, admNo=self.kwargs['adm_no'], patient=patient)
        lookup = {
            'patient': patient,
            'admission': admission,
            'medicine_name': serializer.validated_data.get('medicine_name'),
            'date_given': serializer.validated_data.get('date_given'),
        }
        defaults = {
            **serializer.validated_data,
            'created_by': self.request.user,
        }
        record, _ = PharmacyRecord.objects.update_or_create(defaults=defaults, **lookup)
        serializer.instance = record
    
class PharmacyRecordBulkSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uhid, adm_no):
        patient = get_object_or_404(Patient, uhid=uhid)
        admission = get_object_or_404(Admission, admNo=adm_no, patient=patient)
        records = request.data.get('records') or []

        created_records = []
        with transaction.atomic():
            PharmacyRecord.objects.filter(patient=patient, admission=admission).delete()

            for record in records:
                serializer = PharmacyRecordSerializer(data=record)
                serializer.is_valid(raise_exception=True)
                created_records.append(PharmacyRecord(
                    patient=patient,
                    admission=admission,
                    created_by=request.user,
                    **serializer.validated_data,
                ))

            if created_records:
                PharmacyRecord.objects.bulk_create(created_records)

        payload = PharmacyRecordSerializer(
            PharmacyRecord.objects.filter(patient=patient, admission=admission).order_by('date_given', 'id'),
            many=True,
        ).data
        return Response(payload, status=status.HTTP_200_OK)
    
class CanonicalRecordsAPIView(APIView):
    """Merge every receptionist-saved report and medicine name from any source
    (lab_reports/pharmacy_records, services, medicalHistory.investigations/
    currentMedications) into a single deduplicated payload per admission so
    Branch Admin can render the full picture regardless of where the data
    originally landed."""
    permission_classes = [IsAuthenticated]

    def _split_text(self, raw):
        if not raw:
            return []
        parts = []
        # Split on common delimiters - newline, comma, semicolon, pipe.
        for chunk in str(raw).replace('\r', '\n').split('\n'):
            for piece in chunk.replace('|', ',').replace(';', ',').split(','):
                cleaned = piece.strip()
                if cleaned:
                    parts.append(cleaned)
        return parts

    def _format_date(self, value):
        if not value:
            return ''
        try:
            return value.strftime('%Y-%m-%d')
        except AttributeError:
            return str(value)[:10]

    def _add(self, bucket, seen, name, source, date_str):
        if not name:
            return
        cleaned = str(name).strip()
        if not cleaned:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        bucket.append({
            "name": cleaned,
            "source": source,
            "date": date_str or '',
        })

    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(
            Admission.objects.select_related('patient', 'medicalHistory', 'discharge'),
            patient__uhid=uhid,
            admNo=adm_no,
        )

        admission_date_str = self._format_date(admission.dateTime) or ''

        medicine_master_names = {
            str(name).strip().casefold()
            for name in MedicineMaster.objects.values_list('name', flat=True)
            if name
        }

        report_results = []
        report_seen = set()

        medicine_results = []
        medicine_seen = set()

        # 1. Lab reports (most authoritative)
        for lab in admission.lab_reports.all().order_by('id'):
            self._add(
                report_results,
                report_seen,
                lab.report_name,
                'lab_report',
                self._format_date(lab.report_date) or admission_date_str,
            )

        # 2. Pharmacy records (most authoritative for medicines)
        for pharm in admission.pharmacy_records.all().order_by('id'):
            self._add(
                medicine_results,
                medicine_seen,
                pharm.medicine_name,
                'pharmacy_record',
                pharm.date_given or admission_date_str,
            )

        # 3. Services - classify into reports vs medicines.
        services = admission.services.all().order_by('id')
        for svc in services:
            name = (svc.svcName or '').strip()
            if not name:
                continue
            cat_lower = (svc.svcCat or '').lower()
            svc_date_str = self._format_date(svc.svcDate) or admission_date_str
            is_room_or_consultant = 'room' in cat_lower or 'consultant' in cat_lower or 'icu' in cat_lower
            if is_room_or_consultant:
                continue
            is_medicine_cat = any(key in cat_lower for key in (
                'med', 'pharma', 'drug', 'pharmacy', 'tablet',
                'injection', 'iv fluid', 'consumable',
            ))
            is_medicine_master = name.casefold() in medicine_master_names
            if is_medicine_cat or is_medicine_master:
                self._add(medicine_results, medicine_seen, name, 'service', svc_date_str)
            else:
                self._add(report_results, report_seen, name, 'service', svc_date_str)

        # 4. MedicalHistory free-text fields (least authoritative).
        medical = getattr(admission, 'medicalHistory', None)
        if medical is not None:
            for token in self._split_text(getattr(medical, 'investigations', '')):
                self._add(report_results, report_seen, token, 'investigations', admission_date_str)
            current_meds_raw = getattr(medical, 'currentMedications', '') or getattr(medical, 'treatmentAdvised', '')
            for token in self._split_text(current_meds_raw):
                self._add(medicine_results, medicine_seen, token, 'current_medications', admission_date_str)

        return Response({
            "reports": report_results,
            "medicines": medicine_results,
        }, status=status.HTTP_200_OK)

class PrintAdmissionNoteView(APIView):
    permission_classes = []

    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        ctx = _build_patient_header_context(admission, "ADMISSION NOTE")
        ctx["medical"] = getattr(admission, 'medicalHistory', None)
        return _render_pdf("pdf/admission_note.html", ctx, "admission_note", uhid)

class ReportMasterViewSet(viewsets.ModelViewSet):
    queryset = ReportMaster.objects.all().order_by('name')
    serializer_class = ReportMasterSerializer
    permission_classes = [IsAuthenticated]