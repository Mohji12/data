-- Run once per database. If column already exists, skip or remove this line from your migration runner.
ALTER TABLE batch_master
    ADD COLUMN brochure_file VARCHAR(255) NULL AFTER registration_fee_structure;
