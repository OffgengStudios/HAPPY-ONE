from sqlalchemy import or_, select
from sqlalchemy.orm import Session, load_only

from app.core.errors import ApiError
from app.modules.demand.models import Organization, Vacancy
from app.modules.iam.actors import AuthorizationContext
from app.modules.iam.service import page_query
from app.modules.marketing.models import Campaign
from app.modules.placement.models import Placement
from app.modules.search.schemas import Entity, SearchItem, SearchPage, SearchRequest, SearchResponse
from app.modules.supply.models import Participant, Person
from app.modules.supply.service import full_name

PERMISSIONS: dict[Entity, str] = {
    "PARTICIPANT": "participant:view",
    "ORGANIZATION": "organization:view",
    "VACANCY": "vacancy:view",
    "PLACEMENT": "placement:view",
    "CAMPAIGN": "campaign:view",
}


def search(db: Session, actor: AuthorizationContext, data: SearchRequest) -> SearchResponse:
    allowed = {
        entity for entity, permission in PERMISSIONS.items() if permission in actor.permissions
    }
    requested = set(data.entities) if data.entities is not None else allowed
    if not requested or not requested <= allowed or not set(data.cursors) <= requested:
        raise ApiError(403, "PERMISSION_DENIED", "You do not have access to these search results.")
    groups: dict[Entity, SearchPage] = {}
    for entity in PERMISSIONS:
        if entity not in requested:
            continue
        if entity == "PARTICIPANT":
            participant_query = (
                select(Participant)
                .join(Person, Participant.person_id == Person.id)
                .where(
                    Participant.archived_at.is_(None),
                    Person.archived_at.is_(None),
                    or_(
                        Person.normalized_name.icontains(data.q.casefold(), autoescape=True),
                        Participant.participant_code.icontains(data.q, autoescape=True),
                        Person.phone_normalized.icontains(data.q, autoescape=True),
                        Person.phone_raw.icontains(data.q, autoescape=True),
                    ),
                )
            )
            page = page_query(
                participant_query, Participant, db, data.limit, data.cursors.get(entity)
            )
            # Batch only the public name/location columns, never identity or sensitive profiles.
            people = (
                {
                    person.id: person
                    for person in db.scalars(
                        select(Person)
                        .where(Person.id.in_([row.person_id for row in page["rows"]]))
                        .options(
                            load_only(
                                Person.first_name,
                                Person.surname,
                                Person.other_names,
                                Person.community,
                            )
                        )
                    )
                }
                if page["rows"]
                else {}
            )
            items = [
                SearchItem(
                    entity_type=entity,
                    id=row.id,
                    code=row.participant_code,
                    label=full_name(people[row.person_id]),
                    context=people[row.person_id].community,
                )
                for row in page["rows"]
            ]
        elif entity in {"ORGANIZATION", "VACANCY"}:
            model = Organization if entity == "ORGANIZATION" else Vacancy
            name = Organization.name if entity == "ORGANIZATION" else Vacancy.title
            code = (
                Organization.organization_code if entity == "ORGANIZATION" else Vacancy.vacancy_code
            )
            record_query = select(model).where(
                model.archived_at.is_(None),
                or_(
                    name.icontains(data.q, autoescape=True), code.icontains(data.q, autoescape=True)
                ),
            )
            page = page_query(record_query, model, db, data.limit, data.cursors.get(entity))
            items = [
                SearchItem(
                    entity_type=entity,
                    id=row.id,
                    code=row.organization_code if entity == "ORGANIZATION" else row.vacancy_code,
                    label=row.name if entity == "ORGANIZATION" else row.title,
                    context=row.community if entity == "ORGANIZATION" else row.location_community,
                )
                for row in page["rows"]
            ]
        elif entity == "PLACEMENT":
            placement_query = (
                select(Placement)
                .join(Participant, Participant.id == Placement.participant_id)
                .join(Person, Person.id == Participant.person_id)
                .join(Vacancy, Vacancy.id == Placement.vacancy_id)
                .join(Organization, Organization.id == Placement.organization_id)
                .where(
                    Placement.archived_at.is_(None),
                    or_(
                        Placement.placement_code.icontains(data.q, autoescape=True),
                        Person.normalized_name.icontains(data.q.casefold(), autoescape=True),
                        Vacancy.title.icontains(data.q, autoescape=True),
                        Organization.name.icontains(data.q, autoescape=True),
                    ),
                )
            )
            page = page_query(placement_query, Placement, db, data.limit, data.cursors.get(entity))
            participant_ids = {row.participant_id for row in page["rows"]}
            participants = (
                {
                    row.id: row
                    for row in db.scalars(
                        select(Participant).where(Participant.id.in_(participant_ids))
                    )
                }
                if page["rows"]
                else {}
            )
            people = (
                {
                    row.id: row
                    for row in db.scalars(
                        select(Person).where(
                            Person.id.in_({row.person_id for row in participants.values()})
                        )
                    )
                }
                if page["rows"]
                else {}
            )
            vacancies = (
                {
                    row.id: row
                    for row in db.scalars(
                        select(Vacancy).where(
                            Vacancy.id.in_({row.vacancy_id for row in page["rows"]})
                        )
                    )
                }
                if page["rows"]
                else {}
            )
            items = [
                SearchItem(
                    entity_type=entity,
                    id=row.id,
                    code=row.placement_code,
                    label=full_name(people[participants[row.participant_id].person_id]),
                    context=vacancies[row.vacancy_id].title,
                )
                for row in page["rows"]
            ]
        else:
            campaign_query = select(Campaign).where(
                Campaign.archived_at.is_(None),
                or_(
                    Campaign.campaign_code.icontains(data.q, autoescape=True),
                    Campaign.title.icontains(data.q, autoescape=True),
                    Campaign.audience.icontains(data.q, autoescape=True),
                ),
            )
            page = page_query(campaign_query, Campaign, db, data.limit, data.cursors.get(entity))
            items = [
                SearchItem(
                    entity_type=entity,
                    id=row.id,
                    code=row.campaign_code,
                    label=row.title,
                    context=row.status.replace("_", " ").title(),
                )
                for row in page["rows"]
            ]
        groups[entity] = SearchPage(items=items, next_cursor=page["next_cursor"])
    return SearchResponse(groups=groups)
