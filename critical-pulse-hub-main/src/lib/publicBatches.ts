export type RegistrationCatalogRow = {
  batch_slug: string;
  batch_name: string;
  launch_ready: boolean;
  status: string;
  brochure_url?: string | null;
};

/** Batches hidden from registration UI (register page, navbar batch selector, home course enroll). */
export const registrationExcludedSlugs = new Set([
  'batch-15',
  'ccm-batch-2',
  'ccm-2',
  'ccm-practical',
  'ccm-practical-series',
  'batch-edic-10',
  'edic-10',
  'batch-10-edic-1',
  'edic-1',
]);

const registrationExcludedNames = new Set([
  'batch 15',
  'ccm batch 2',
  'batch edic 10',
]);

export function isRegistrationExcludedBatch(row: {
  batch_slug?: string;
  slug?: string;
  batch_name?: string;
  title?: string;
}): boolean {
  const slug = String(row.batch_slug || row.slug || '').trim();
  if (slug && registrationExcludedSlugs.has(slug)) {
    return true;
  }
  const name = String(row.batch_name || row.title || '')
    .trim()
    .toLowerCase();
  return registrationExcludedNames.has(name);
}

/**
 * Public-facing batch list used across homepage + navbar.
 * Rule: show only DB-active batches (status=1).
 */
export function filterPublicBatches(rows: RegistrationCatalogRow[]): RegistrationCatalogRow[] {
  return (rows || []).filter((b) => String(b.status ?? '0') === '1');
}

/** Active catalog rows allowed on registration flows (excludes closed batches e.g. Batch 15, CCM Batch 2, Batch EDIC 10). */
export function filterRegistrationCatalogBatches(
  rows: RegistrationCatalogRow[],
): RegistrationCatalogRow[] {
  return filterPublicBatches(rows).filter((b) => !isRegistrationExcludedBatch(b));
}

export function getPublicBatchDisplayName(row: RegistrationCatalogRow): string {
  const slug = String(row.batch_slug || '').toLowerCase();
  if (slug === 'cp-7') return 'Batch-9 CC-1';
  if (slug === 'cp-8') return 'Batch-9 CC-2';
  if (slug === 'ccm-2' || slug === 'ccm-practical-series' || slug === 'ccm-practical-series-batch-2') return 'ccm-practical-series-batch-2';
  if (slug === 'ccm-3' || slug === 'ccm-practical-series-batch-3') return 'ccm-practical-series-batch-3';
  return row.batch_name;
}

