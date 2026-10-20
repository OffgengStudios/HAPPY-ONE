import json
import subprocess
from pathlib import Path

from app.integrations.intake.schemas import EmployerSubmission, ParticipantSubmission

ROOT = Path(__file__).resolve().parents[4]


def client_payload(script: str) -> dict:
    output = subprocess.check_output(["node", "-e", script], cwd=ROOT, text=True)
    return json.loads(output)


def test_actual_hamis_client_payload_is_accepted_by_public_api_schema():
    data = client_payload(
        "const c=require('./frontend/js/intake-contract.js');"
        "process.stdout.write(JSON.stringify(c.buildPayload({firstName:'Synthetic',"
        "surname:'Person',telephone:'0241234567',community:'Accra',"
        "educationLevel:'Secondary',employmentStatus:'Unemployed'}, {},"
        "'SYNTHETIC-1','00000000-0000-4000-8000-000000000001')))"
    )
    parsed = ParticipantSubmission.model_validate(data)
    assert parsed.basic.first_name == "Synthetic"
    assert parsed.employment.employment_status == "Unemployed"
    assert parsed.consent.accepted


def test_actual_employer_client_payload_is_accepted_by_public_api_schema():
    data = client_payload(
        "const c=require('./portal/src/contract.js');process.stdout.write(JSON.stringify("
        "c.buildPayload({company_name:'Synthetic Employer',contact_name:'Synthetic Contact',"
        "contact_phone:'0241234567',contact_email:'synthetic@example.org',"
        "consent_agreement:true,consent_contact:true},[{job_title:'Assistant',"
        "location:'Tema',employment_type:'FULL_TIME',openings:'2',salary_min:'1500.00',"
        "salary_frequency:'MONTHLY',skills:'Excel',accommodation:'no'}],[],"
        "'00000000-0000-4000-8000-000000000002')))"
    )
    parsed = EmployerSubmission.model_validate(data)
    assert parsed.vacancies[0].openings == 2
    assert parsed.vacancies[0].requirements[0].value_json == "Excel"
