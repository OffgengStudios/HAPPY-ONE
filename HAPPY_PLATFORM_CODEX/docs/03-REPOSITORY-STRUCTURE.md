# Repository Structure

```text
happy-management-platform/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   ├── work/
│   │   │   ├── employers/
│   │   │   ├── vacancies/
│   │   │   ├── participants/
│   │   │   ├── matching/
│   │   │   ├── placements/
│   │   │   ├── training/
│   │   │   ├── merl/
│   │   │   ├── marketing/
│   │   │   ├── reports/
│   │   │   └── admin/
│   │   ├── lib/
│   │   ├── hooks/
│   │   └── tests/
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   │   └── v1/
│       │   ├── core/
│       │   ├── db/
│       │   ├── modules/
│       │   │   ├── auth/
│       │   │   ├── iam/
│       │   │   ├── organizations/
│       │   │   ├── vacancies/
│       │   │   ├── participants/
│       │   │   ├── matching/
│       │   │   ├── interviews/
│       │   │   ├── placements/
│       │   │   ├── training/
│       │   │   ├── merl/
│       │   │   ├── marketing/
│       │   │   ├── files/
│       │   │   ├── tasks/
│       │   │   ├── reporting/
│       │   │   └── audit/
│       │   └── main.py
│       └── tests/
├── packages/
│   ├── api-client/
│   ├── ui/
│   ├── config/
│   └── shared-types/
├── database/
│   ├── migrations/
│   ├── seeds/
│   └── docs/
├── infra/
│   ├── docker/
│   └── deployment/
├── tests/
│   ├── e2e/
│   ├── fixtures/
│   └── security/
├── docs/
│   └── implementation-spec/
├── scripts/
├── .env.example
├── docker-compose.yml
├── AGENTS.md
└── README.md
```

## Module Internal Structure

The tree above is the target layout, not a claim that every module exists.
Current domain packages use `modules/iam`, `modules/demand`, and the preserved
`modules/supply` draft. Generic bindings live in `modules/external_references`;
controlled provenance lives in `db/provenance.py`.

Future integration boundaries are small packages under `app/integrations/`:
`cv_parser` (Phase 7), `hamis` (Phase 12), `employer_portal` (Phase 13).
They contain architectural declarations only, not speculative clients or jobs.
Reuse the existing SQLAlchemy service pattern; add repository abstractions only
when actual persistence complexity justifies them.

Each backend domain module should generally contain:

```text
module/
├── models.py
├── schemas.py
├── repository.py
├── service.py
├── permissions.py
├── routes.py
├── events.py
└── tests/
```

Rules:
- routes remain thin
- services own business logic
- repositories own persistence concerns
- permission checks are explicit
- cross-module operations use service interfaces
- audit is invoked at the service/business boundary
