\getenv app_user HAPPY_DB_USER
\getenv app_password HAPPY_DB_PASSWORD
\getenv app_database HAPPY_DB_NAME

SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE',
  :'app_user', :'app_password'
) \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'app_database', :'app_user') \gexec
