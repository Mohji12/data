ALTER TABLE `package`
  ADD COLUMN `plan_type` VARCHAR(30) NULL DEFAULT 'one_time' AFTER `total_amount`,
  ADD COLUMN `duration_months` INT NULL AFTER `plan_type`;

UPDATE `package`
SET `plan_type` = 'one_time'
WHERE `plan_type` IS NULL OR TRIM(`plan_type`) = '';

CREATE TABLE IF NOT EXISTS `user_subscriptions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `batch_slug` VARCHAR(255) NOT NULL,
  `package_id` INT NOT NULL,
  `duration_months` INT NULL,
  `start_at` DATETIME NOT NULL,
  `end_at` DATETIME NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'active',
  `auto_renew` VARCHAR(1) NOT NULL DEFAULT '0',
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_subscriptions_user_id` (`user_id`),
  KEY `idx_user_subscriptions_batch_slug` (`batch_slug`),
  KEY `idx_user_subscriptions_status_end` (`status`, `end_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
