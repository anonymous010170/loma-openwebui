import psycopg

class Logger:
    def __init__(self, postgres_url: str):
        self.postgres_url = postgres_url
        self._init_log_table()


    def _init_log_table(self):
        with psycopg.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_logs (
                        id          SERIAL PRIMARY KEY,
                        timestamp   TIMESTAMPTZ NOT NULL,
                        run_id      TEXT,
                        agent_name  TEXT,
                        query       TEXT,
                        response    TEXT,
                        model       TEXT,
                        provider    TEXT,
                        metrics     JSONB,
                        log_references  JSONB
                    )
                """)
            conn.commit()

    def log(self, timestamp, run_id, agent_name, query, response, model, provider, metrics, log_references):
        with psycopg.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_logs
                        (timestamp, run_id, agent_name, query, response,
                         model, provider, metrics, log_references)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    timestamp,
                    run_id,
                    agent_name,
                    query,
                    response,
                    model,
                    provider,
                    metrics,
                    log_references
                ))
            conn.commit()