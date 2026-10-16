from typing import Any

WORKSPACES = {
    "DEMAND": "Demand",
    "SUPPLY": "Supply",
    "MATCHING": "Matching",
    "MERL": "M&E / MERL",
    "MARKETING": "Marketing",
    "MANAGEMENT": "Management",
}

# Ambiguous restricted/subset grants remain denied until their policies are agreed.
ROLE_GRANTS: dict[str, set[str]] = {
    "DEMAND": {
        "organization:view",
        "organization:create",
        "organization:edit",
        "organization_contact:view",
        "organization_contact:edit",
        "partnership:view",
        "partnership:edit",
        "vacancy:view",
        "vacancy:create",
        "vacancy:edit",
        "marketing_request:view",
        "marketing_request:create",
        "employer_submission:view",
        "employer_submission:manage",
    },
    "SUPPLY": {
        "vacancy:view",
        "participant:view",
        "participant:create",
        "participant:edit",
        "cv:view",
        "cv:edit",
        "cv:download",
        "cv_parse:view",
        "cv_parse:run",
        "cv_parse:review",
        "marketing_request:view",
        "marketing_request:create",
        "training:view",
        "training:edit",
    },
    "MATCHING": {
        "organization:view",
        "partnership:view",
        "vacancy:view",
        "vacancy:create",
        "vacancy:edit",
        "participant:view",
        "cv:view",
        "candidate_pipeline:view",
        "cv:download",
        "candidate_pipeline:edit",
        "interview:view",
        "interview:edit",
        "placement:view",
        "placement:edit",
        "first_income:view",
        "first_income:edit",
        "marketing_request:view",
        "marketing_request:create",
    },
    "MERL": {
        "organization:view",
        "partnership:view",
        "vacancy:view",
        "participant:view",
        "placement:view",
        "first_income:view",
        "follow_up:view",
        "follow_up:edit",
        "outcome:view",
        "outcome:edit",
        "data_quality:view",
        "data_quality:edit",
        "marketing_request:view",
        "marketing_request:create",
        "training:view",
        "training:edit",
    },
    "MARKETING": {
        "vacancy:view",
        "training:view",
        "marketing_request:view",
        "marketing_request:edit",
        "marketing_request:create",
        "campaign:view",
        "campaign:edit",
        "impact_story:view",
        "impact_story:edit",
    },
    "MANAGEMENT": {
        "organization:view",
        "partnership:view",
        "vacancy:view",
        "placement:view",
        "outcome:view",
        "campaign:view",
        "impact_story:view",
        "follow_up:view",
        "data_quality:view",
        "report:view",
        "report:export",
        "training:view",
    },
}
WORK_PERMISSIONS = {
    "task:view",
    "task:edit",
    "handoff:view",
    "handoff:manage",
    "notification:view",
}
for role_code in ROLE_GRANTS:
    ROLE_GRANTS[role_code].update(WORK_PERMISSIONS)
EXPLICIT_PERMISSIONS = {
    "external_reference:view",
    "external_reference:manage",
    "user:manage",
    "role:manage",
    "audit:view",
    "participant_sensitive:view",
    "participant_sensitive:edit",
    "participant:merge",
    "placement:confirm",
    "placement:correct_confirmation",
    "vacancy:overfill_override",
    "record:hard_delete",
    "report:export",
    "report:sensitive_export",
    "report:view",
    "report_target:manage",
    "follow_up:configure",
    "integration_event:view",
    "integration_event:manage",
    "employer_submission:view",
    "employer_submission:manage",
    "notification:manage",
}
for code in WORKSPACES:
    ROLE_GRANTS[code].add(f"workspace_{code.lower()}:view")
PERMISSION_CODES = EXPLICIT_PERMISSIONS | set().union(*ROLE_GRANTS.values())
ROLE_GRANTS["ADMIN"] = set(PERMISSION_CODES)


def effective_permissions(grants: set[str], overrides: dict[str, str]) -> set[str]:
    return (grants | {key for key, effect in overrides.items() if effect == "ALLOW"}) - {
        key for key, effect in overrides.items() if effect == "DENY"
    }


def project_fields(
    record: dict[str, Any], allowed: set[str], field_permissions: dict[str, str]
) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in field_permissions or field_permissions[key] in allowed
    }
