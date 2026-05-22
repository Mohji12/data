export type RegistrationCatalogRow = {
  batch_slug: string;
  batch_name: string;
  launch_ready: boolean;
  status: string;
  brochure_url?: string | null;
};

/**
 * Public-facing batch list used across homepage + navbar.
 * Rule: show only DB-active batches (status=1).
 */
export function filterPublicBatches(rows: RegistrationCatalogRow[]): RegistrationCatalogRow[] {
  return (rows || []).filter((b) => String(b.status ?? '0') === '1');
}

export function getPublicBatchDisplayName(row: RegistrationCatalogRow): string {
  const slug = String(row.batch_slug || '').toLowerCase();
  if (slug === 'cp-7') return 'Batch-9 CC-1';
  if (slug === 'cp-8') return 'Batch-9 CC-2';
  if (slug === 'ccm-2' || slug === 'ccm-practical-series' || slug === 'ccm-practical-series-batch-2') return 'ccm-practical-series-batch-2';
  if (slug === 'ccm-3' || slug === 'ccm-practical-series-batch-3') return 'ccm-practical-series-batch-3';
  return row.batch_name;
}

