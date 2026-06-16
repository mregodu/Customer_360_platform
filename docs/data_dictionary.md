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

Customer enrichment metrics:

| Column | Description |
| --- | --- |
| `golden_customer_id` | Stable generated ID for the resolved customer cluster. |
| `metric_date` | Daily metric date represented by the enrichment row. |
| `lifetime_value` | Estimated customer lifetime value based on contract value, renewal likelihood, and expansion signals. |
| `product_adoption_score` | Normalized product adoption from usage, active users, active days, and feature utilization. |
| `engagement_score` | Weighted product, marketing, and support activity engagement score. |
| `support_health_score` | Support experience score where higher means fewer unresolved support concerns. |
| `renewal_probability` | Estimated likelihood of renewal from status, engagement, adoption, support health, and expiration timing. |
| `metric_components` | Variant payload with source-system and formula-version audit metadata. |

Customer health scoring:

| Column | Description |
| --- | --- |
| `score_date` | Daily date for the health score. |
| `health_class` | Predicted class: `Healthy`, `At Risk`, or `Churn Risk`. |
| `churn_risk_score` | Probability assigned to the `Churn Risk` class. |
| `model_algorithm` | Algorithm used for prediction, such as Logistic Regression, Random Forest, or XGBoost. |
| `class_probabilities` | Variant payload with per-class prediction probabilities. |
| `feature_snapshot` | Variant payload with model feature values used at scoring time. |
