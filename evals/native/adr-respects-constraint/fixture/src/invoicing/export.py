"""Nightly invoice export to the external accountant.

Builds one CSV of the previous day's invoices and uploads it over SFTP. A full
day takes about 25 minutes. Running it twice for the same day uploads two files,
and the accountant's system imports both, so every invoice is booked twice.
"""

import csv
import io
from datetime import date, timedelta

from invoicing.db import connect
from invoicing.sftp import upload


def export_invoices_for_day(day: date) -> int:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["invoice_id", "customer_id", "issued_on", "total_minor", "currency"])
    count = 0
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, customer_id, issued_on, total_minor, currency "
            "FROM invoices WHERE issued_on = %s ORDER BY id",
            (day,),
        )
        for row in rows:
            writer.writerow(row)
            count += 1
    upload(f"invoices-{day.isoformat()}.csv", buffer.getvalue().encode())
    return count


if __name__ == "__main__":
    # Run by hand today: python -m invoicing.export
    print(export_invoices_for_day(date.today() - timedelta(days=1)))
