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
from xhtml2pdf import pisa
from patients.models import Patient, Admission, MedicalHistory, Discharge, Billing
from master.models import HospitalSettings, MedicineMaster
from core.utils import get_or_create_current_billing
from .models import LabReport, DischargeSummary, PharmacyRecord, ReportMaster
from .serializers import LabReportSerializer, DischargeSummarySerializer, PharmacyRecordSerializer, ReportMasterSerializer
from .templates import DISCHARGE_TEMPLATES
from .report_templates import build_suggested_reports_for_admission

# Create your views here.

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
        admission = get_object_or_404(Admission, patient=patient, admNo=adm_no)
        reports = request.data.get('reports') or []

        created_by = request.user.first_name or request.user.username
        created_reports = []

        with transaction.atomic():
            LabReport.objects.filter(patient=patient, admission=admission).delete()

            for report in reports:
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
        patient = get_object_or_404(Patient, uhid=uhid)
        admission = get_object_or_404(Admission, patient=patient, admNo=adm_no)

        suggested_reports = build_suggested_reports_for_admission(patient, admission)
        return Response(
            {
                'patient': patient.uhid,
                'admNo': admission.admNo,
                'suggested_reports': suggested_reports,
            },
            status=status.HTTP_200_OK,
        )
    
class DynamicDischargeSummaryView(APIView):
    def _clean_status(self, raw_status):
        status_str = str(raw_status).upper()
        if "LAMA" in status_str: return "LAMA"
        if "DOPR" in status_str: return "DOPR"
        if "REFER" in status_str: return "REFER"
        if "DEATH" in status_str: return "DEATH"
        return "NORMAL"

    def get(self, request, uhid, adm_no):
        raw_type = request.query_params.get('type', 'NORMAL')
        summary_type = self._clean_status(raw_type)
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)

        existing_summary = DischargeSummary.objects.filter(admission=admission).first()
        if existing_summary:
            return Response({
                "is_existing": True,
                "summary_type": existing_summary.summary_type,
                "content": existing_summary.content
            }, status=status.HTTP_200_OK)

        template = copy.deepcopy(DISCHARGE_TEMPLATES.get(summary_type, DISCHARGE_TEMPLATES["NORMAL"]))

        # 🌟 UPDATED PRE-FILL: Iterate through the List to find keys
        try:
            med_hist = getattr(admission, 'medicalHistory', None)
            if med_hist:
                for section in template["sections"]:
                    if section["key"] == "k_c_o" and med_hist.previousDiagnosis:
                        section["value"] = med_hist.previousDiagnosis
        except Exception:
            pass

        return Response({"is_existing": False, "summary_type": summary_type, "content": template}, status=status.HTTP_200_OK)

    def post(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        raw_type = request.data.get('summary_type', 'NORMAL')
        summary_type = self._clean_status(raw_type)
        content = request.data.get('content', {})

        summary, created = DischargeSummary.objects.update_or_create(
            admission=admission,
            defaults={'summary_type': summary_type, 'content': content, 'created_by': request.user if request.user.is_authenticated else None}
        )
        return Response({"message": "Discharge Summary saved successfully!", "data": DischargeSummarySerializer(summary).data}, status=status.HTTP_200_OK)

class PrintDischargeSummaryView(APIView):
    def get(self, request, uhid, adm_no):
        admission = get_object_or_404(Admission, patient__uhid=uhid, admNo=adm_no)
        summary = DischargeSummary.objects.filter(admission=admission).first()
        if not summary:
            discharge = getattr(admission, 'discharge', None)
            raw_status = getattr(discharge, 'dischargeStatus', 'NORMAL')
            status_str = str(raw_status).upper()
            if "LAMA" in status_str:
                fallback_type = "LAMA"
            elif "DOPR" in status_str:
                fallback_type = "DOPR"
            elif "REFER" in status_str:
                fallback_type = "REFER"
            elif "DEATH" in status_str:
                fallback_type = "DEATH"
            else:
                fallback_type = "NORMAL"
            summary = DischargeSummary(
                admission=admission,
                summary_type=fallback_type,
                content=copy.deepcopy(DISCHARGE_TEMPLATES.get(fallback_type, DISCHARGE_TEMPLATES["NORMAL"])),
            )
        
        status_map = {"NORMAL": "pdf/normal.html", "RECOVERED": "pdf/normal.html", "LAMA": "pdf/lama.html", "REFER": "pdf/refer.html", "DOPR": "pdf/dopr.html", "DEATH": "pdf/death.html"}
        template_file = status_map.get(summary.summary_type, "pdf/normal.html")
        
        patient = admission.patient
        discharge = getattr(admission, 'discharge', None)
        billing = admission.bills.order_by('-id').first()

        age = "--"
        if patient.dob:
            calc_age = (timezone.now().date() - patient.dob).days // 365
            age = f"{calc_age} YRS"

        sections = summary.content.get("sections", [])

        # 🌟 NEW: BACKEND AUTO-CONVERTER 🌟
        # If an old database record is an Object/Dict, convert it to a List format instantly!
        if isinstance(sections, dict):
            sections = [{"key": k, **v} for k, v in sections.items()]

        # Now we can safely iterate through the list without crashing
        if discharge:
            for section in sections:
                if section.get("key") == "condition_at_discharge":
                    section["value"] = discharge.dischargeStatus.upper() if discharge.dischargeStatus else "--"

        context = {
            "s": summary, "sections": sections, "uhid": patient.uhid,
            "ipd_no": admission.ipdNo, "patient_name": patient.patientName.upper(),
            "guardian_name": patient.guardianName.upper() if patient.guardianName else "--",
            "address": patient.address, "consultant": discharge.doctorName.upper() if discharge and discharge.doctorName else "--",
            "claim_id": patient.tpaPanelCardNo if patient.tpaPanelCardNo else "--",
            "doa": admission.dateTime.strftime("%d-%m-%Y %H:%M HRS") if admission.dateTime else "--",
            "dod": discharge.dod.strftime("%d-%m-%Y %H:%M HRS") if (discharge and discharge.dod) else "--",
            "bill_no": f"{billing.id}/{admission.dateTime.strftime('%y')}" if billing else "--",
            "bill_date": discharge.dod.strftime("%d-%m-%Y %H:%M HRS") if (discharge and discharge.dod) else "--",
            "age_sex": f"{age} / {patient.gender.upper()}", "card_no": patient.tpaCard if patient.tpaCard else "--",
            "room": f"{discharge.roomNo} / {discharge.wardName.upper()}" if discharge and discharge.roomNo else "-- / --",
            "panel": patient.tpa.upper() if patient.tpa else (admission.payMode.upper() if admission.payMode else 'CASH'),
            "contact_no": patient.phone, "status_on_discharge": discharge.dischargeStatus.upper() if discharge and discharge.dischargeStatus else "--",
        }

        html_string = render_to_string(template_file, context)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{uhid}_summary.pdf"'
            return response

        return Response({"error": "PDF Generation Failed"}, status=400)


def _build_patient_header_context(admission, summary_label):
    patient = admission.patient
    discharge = getattr(admission, 'discharge', None)
    billing = admission.bills.order_by('-id').first()

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