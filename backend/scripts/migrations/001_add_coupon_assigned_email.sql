-- Per-user coupons: nullable email binding.
-- If the column already exists, skip this migration.

ALTER TABLE coupon_master
  ADD COLUMN assigned_email VARCHAR(255) NULL DEFAULT NULL;
