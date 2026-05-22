-- FastAPI registration / payment flow (not present on legacy PHP DB). Run once on admin_CriticalCareClasses (or your DB name).

CREATE TABLE IF NOT EXISTS `registration_payment_txn` (
  `id` int NOT NULL AUTO_INCREMENT,
  `request_id` varchar(255) NOT NULL,
  `user_id` int NOT NULL,
  `batch_slug` varchar(255) NOT NULL,
  `package_id` int NOT NULL,
  `amount` double DEFAULT 0,
  `currency` varchar(20) DEFAULT 'INR',
  `gateway` varchar(50) DEFAULT 'razorpay',
  `gateway_order_id` varchar(255) DEFAULT NULL,
  `gateway_payment_id` varchar(255) DEFAULT NULL,
  `gateway_signature` varchar(255) DEFAULT NULL,
  `gateway_status` varchar(50) DEFAULT 'created',
  `coupon_code` varchar(100) DEFAULT NULL,
  `callback_payload` text,
  `webhook_payload` text,
  `is_finalized` varchar(1) DEFAULT '0',
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_registration_payment_txn_request_id` (`request_id`),
  KEY `idx_registration_payment_txn_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
