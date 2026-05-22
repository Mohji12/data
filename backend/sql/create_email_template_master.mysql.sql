CREATE TABLE IF NOT EXISTS email_template_master (
  id INT NOT NULL AUTO_INCREMENT,
  batch_id INT NOT NULL,
  template_type VARCHAR(64) NOT NULL,
  subject VARCHAR(255) NOT NULL,
  body_html TEXT NOT NULL,
  status VARCHAR(1) NOT NULL DEFAULT '1',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_email_template_master_batch_type (batch_id, template_type),
  KEY idx_email_template_master_batch (batch_id),
  KEY idx_email_template_master_type_status (template_type, status),
  CONSTRAINT fk_email_template_master_batch
    FOREIGN KEY (batch_id) REFERENCES batch_master(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);
