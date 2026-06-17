# docs

Architecture, onboarding, data dictionary, runbooks, and design decision records.

## Documents

- `architecture.md`: platform architecture and dependency direction.
- `cicd.md`: GitHub Actions CI, Docker build, and deployment automation guide.
- `containerization.md`: Docker image, Docker Compose, Airflow containers, and environment management.
- `data_dictionary.md`: customer, enrichment, health, and reporting data definitions.
- `onboarding.md`: first steps for local development.

## Why This Folder Exists

- Makes ownership clear as the Customer 360 platform grows.
- Keeps orchestration, transformation, domain logic, infrastructure adapters, documentation, and tests separated.
- Helps engineers find the right place for new production assets without guessing.

## Operating Rules

- Keep files cohesive with this folder's responsibility.
- Do not commit secrets or production customer data.
- Prefer small, reviewed changes with tests, validation, or clear run notes.
