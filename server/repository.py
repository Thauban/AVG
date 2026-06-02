import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from loguru import logger
import datetime

class InvoiceRepository:
    def __init__(self, dsn):
        logger.info("Initialisiere PostgreSQL Connection Pool")
        self.pool = ThreadedConnectionPool(1, 20, dsn)

    @contextmanager
    def _get_connection(self):
        connection = self.pool.getconn()
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"Datenbankfehler im Repository: {e}")
            raise e
        finally:
            self.pool.putconn(connection)

    def add_object(self, obj):
        """Speichert eine Rechnung in der Tabelle 'rechnung.rechnung'."""
        jetzt = datetime.datetime.now()
        invoice_id = obj.get("invoice_id")

        with self._get_connection() as connection:
            with connection.cursor() as cur:
                if invoice_id and invoice_id.strip():
                    sql = """
                        INSERT INTO rechnung.rechnung (invoice_id, customer_name, IBAN, total_amount, currency, issue_date, erzeugt, aktualisiert)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (invoice_id) DO UPDATE 
                        SET customer_name = EXCLUDED.customer_name,
                            IBAN = EXCLUDED.IBAN,
                            total_amount = EXCLUDED.total_amount,
                            currency = EXCLUDED.currency,
                            issue_date = EXCLUDED.issue_date,
                            aktualisiert = EXCLUDED.aktualisiert
                        RETURNING invoice_id;
                    """
                    # HIER NUTZEN WIR JETZT DYNAMISCH obj["iban"] UND obj["currency"]!
                    params = (invoice_id, obj["customer_name"], obj["iban"], obj["total_amount"], obj["currency"], obj["issue_date"], jetzt, jetzt)
                else:
                    sql = """
                        INSERT INTO rechnung.rechnung (customer_name, IBAN, total_amount, currency, issue_date, erzeugt, aktualisiert)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING invoice_id;
                    """
                    params = (obj["customer_name"], obj["iban"], obj["total_amount"], obj["currency"], obj["issue_date"], jetzt, jetzt)
                
                cur.execute(sql, params)
                generated_id = cur.fetchone()[0]
                return generated_id

    def get_object(self, data_id):
        """Liest eine spezifische Rechnung inklusive IBAN und Währung aus."""
        with self._get_connection() as connection:
            with connection.cursor() as cur:
                # Spalten erweitert um IBAN und currency!
                cur.execute(
                    "SELECT invoice_id, customer_name, total_amount, issue_date, IBAN, currency FROM rechnung.rechnung WHERE invoice_id = %s;",
                    (data_id,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "invoice_id": row[0],
                        "customer_name": row[1],
                        "total_amount": float(row[2]),
                        "issue_date": str(row[3]),
                        "iban": row[4],        # NEU: Wird an Logic/Router weitergereicht
                        "currency": row[5]    # NEU: Wird an Logic/Router weitergereicht
                    }
        return None

    def list_objects(self):
        """Gibt alle Rechnungen inklusive IBAN und Währung aus der Datenbank zurück."""
        invoices = []
        with self._get_connection() as connection:
            with connection.cursor() as cur:
                # Spalten erweitert um IBAN und currency!
                cur.execute("SELECT invoice_id, customer_name, total_amount, issue_date, IBAN, currency FROM rechnung.rechnung;")
                rows = cur.fetchall()
                for row in rows:
                    invoices.append({
                        "invoice_id": row[0],
                        "customer_name": row[1],
                        "total_amount": float(row[2]),
                        "issue_date": str(row[3]),
                        "iban": row[4],        # NEU
                        "currency": row[5]    # NEU
                    })
        return invoices

    def delete_object(self, data_id):
        """Löscht eine Rechnung aus der Datenbank."""
        with self._get_connection() as connection:
            with connection.cursor() as cur:
                cur.execute("DELETE FROM rechnung.rechnung WHERE invoice_id = %s;", (data_id,))
                return cur.rowcount > 0