FROM postgres:17

# The official image already has the PGDG apt repo, which packages HypoPG.
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-17-hypopg \
 && rm -rf /var/lib/apt/lists/*

# Init scripts run in name order, once, when the data volume is first created.
COPY init.sql  /docker-entrypoint-initdb.d/01_init.sql
COPY roles.sql /docker-entrypoint-initdb.d/02_roles.sql
