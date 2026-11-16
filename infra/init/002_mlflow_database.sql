-- MLflow uses a dedicated database, separate from the application schema.
-- PostgreSQL runs init scripts only when the data directory is first initialized.
CREATE DATABASE mlflow OWNER neuroflow;
