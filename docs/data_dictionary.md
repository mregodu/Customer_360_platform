# Data Dictionary

Core golden customer fields:

| Column | Description |
| --- | --- |
| `golden_customer_id` | Stable generated ID for the resolved customer cluster. |
| `source_customer_ids` | Source-system IDs that contributed to the golden record. |
| `company_name` | Highest-confidence standardized company name. |
| `email` | Most recent standardized customer email. |
| `phone` | Most recent normalized phone number. |
| `address` | Most complete standardized address. |
| `confidence_score` | Entity-resolution confidence score. |
