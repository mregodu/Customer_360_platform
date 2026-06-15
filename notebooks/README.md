# notebooks

Exploratory analysis notebooks; production logic should move into src/customer360 modules.

## Why This Folder Exists

- Makes ownership clear as the Customer 360 platform grows.
- Keeps orchestration, transformation, domain logic, infrastructure adapters, documentation, and tests separated.
- Helps engineers find the right place for new production assets without guessing.

## Operating Rules

- Keep files cohesive with this folder's responsibility.
- Do not commit secrets or production customer data.
- Prefer small, reviewed changes with tests, validation, or clear run notes.
