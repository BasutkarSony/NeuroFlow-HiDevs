FROM ghcr.io/mlflow/mlflow:v3.17.2

# MLflow's PostgreSQL backend requires the psycopg 3 driver.
RUN pip install --no-cache-dir "psycopg[binary]>=3.2,<4"
