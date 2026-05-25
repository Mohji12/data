"""Add batch_master.package_subscription and seed display-name to package.subscription links."""

from sqlalchemy import text

from app.db import engine

SEED_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("COMPREHENSIVE COURSE 1", "CP 7"),
    ("COMPREHENSIVE COURSE 2", "CP 8"),
    ("PRACTICAL SERIES BATCH 3", "CCM Batch 3"),
)


def add_package_subscription_column() -> None:
    with engine.connect() as conn:
        print("Checking for package_subscription column in batch_master table...")
        result = conn.execute(text("SHOW COLUMNS FROM batch_master LIKE 'package_subscription'"))
        if not result.fetchone():
            print("Adding package_subscription column to batch_master table...")
            conn.execute(
                text(
                    "ALTER TABLE batch_master ADD COLUMN package_subscription VARCHAR(255) "
                    "NULL AFTER brochure_file"
                )
            )
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column package_subscription already exists.")

        for batch_name, pkg_sub in SEED_MAPPINGS:
            updated = conn.execute(
                text(
                    "UPDATE batch_master SET package_subscription = :pkg_sub "
                    "WHERE LOWER(TRIM(name)) = LOWER(TRIM(:batch_name)) "
                    "AND (package_subscription IS NULL OR TRIM(package_subscription) = '')"
                ),
                {"batch_name": batch_name, "pkg_sub": pkg_sub},
            )
            conn.commit()
            print(f"  {batch_name!r} -> {pkg_sub!r}: {updated.rowcount} row(s) updated")


if __name__ == "__main__":
    add_package_subscription_column()
