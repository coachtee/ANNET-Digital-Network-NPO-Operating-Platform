import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def report_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    return render(request, "reporting/list.html", {"organisation": organisation})


@login_required
def organisation_profile_pdf(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{organisation.slug}-profile.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 60

    def line(text, size=11, gap=18, bold=False):
        nonlocal y
        p.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        p.drawString(50, y, text)
        y -= gap

    line(f"Organisation Profile — {organisation.display_name}", 16, 28, bold=True)
    line(f"Generated {request.user.get_full_name() or request.user.email} on the Bohlale Impact platform", 9, 24)
    line(f"Legal name: {organisation.legal_name}")
    line(f"Trading name: {organisation.trading_name or '—'}")
    line(f"Organisation type: {organisation.get_organisation_type_display()}")
    line(f"Legal structure: {organisation.get_legal_structure_display() or 'Not set'}")
    line(f"Province: {organisation.get_province_display() or '—'}")
    line(f"Email: {organisation.email or '—'}")
    line(f"DSD registered: {organisation.dsd_registered}")
    line(f"CIPC registered: {organisation.cipc_registered}")
    line(f"SARS PBO approved: {organisation.sars_pbo_approved}")
    line(f"Section 18A approved: {organisation.section18a_approved}")
    y -= 10
    line("This report reflects Compliance Readiness records held on the platform.", 9)
    line("It is not a legal or regulatory compliance certification.", 9)
    p.showPage()
    p.save()
    return response


@login_required
def compliance_csv(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{organisation.slug}-compliance.csv"'
    writer = csv.writer(response)
    writer.writerow(["Authority", "Obligation", "Frequency", "Due Date", "Status", "Submitted At", "Submission Reference"])
    for o in organisation.compliance_obligations.select_related("rule"):
        writer.writerow([o.rule.authority, o.rule.name, o.rule.get_frequency_display(), o.due_date, o.get_status_display(), o.submitted_at, o.submission_reference])
    return response


@login_required
def attendance_csv(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{organisation.slug}-attendance.csv"'
    writer = csv.writer(response)
    writer.writerow(["Programme", "Activity", "Date", "Named beneficiary", "Headcount", "Method"])
    for r in organisation.attendance_records.select_related("programme", "activity", "beneficiary"):
        writer.writerow([r.programme.name, r.activity.name if r.activity else "", r.attendance_date,
                          str(r.beneficiary) if r.beneficiary else "", r.headcount, r.get_check_in_method_display()])
    return response


@login_required
def expense_csv(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{organisation.slug}-expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(["Project", "Description", "Amount", "Status", "Submitted by", "Reviewed by"])
    for e in organisation.expenses.select_related("project", "submitted_by", "reviewed_by"):
        writer.writerow([e.project.name, e.description, e.amount, e.get_status_display(),
                          str(e.submitted_by) if e.submitted_by else "", str(e.reviewed_by) if e.reviewed_by else ""])
    return response
