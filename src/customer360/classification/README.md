# classification

Customer health scoring classifies each golden customer as `Healthy`, `At Risk`,
or `Churn Risk`.

- `features.py`: builds model-ready features from product usage, support history,
  marketing engagement, and renewal history.
- `models.py`: creates Logistic Regression, Random Forest, and XGBoost classifiers.
- `training.py`: trains candidate models and records accuracy, macro F1,
  confusion matrix, and class-level metrics.
- `prediction.py`: generates Snowflake-ready `ANALYTICS.customer_health_scores`
  rows from a trained model.
- `rules.py`: deterministic fallback rules used for weak labels and baseline tests.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
