import { useEffect, useState } from 'react';
import { fetchAdminDocumentBlob, isImageFilename, isPdfFilename } from '@/lib/adminDocument';

type Props = {
  userId: number;
  filename?: string | null;
  file?: 1 | 2;
  label?: string;
};

export default function AdminDocumentPreview({ userId, filename, file = 1, label = 'Document' }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!filename?.trim()) {
      setBlobUrl(null);
      setError(null);
      return;
    }

    let revoked: string | null = null;
    setLoading(true);
    setError(null);

    void fetchAdminDocumentBlob(userId, file)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        revoked = url;
        setBlobUrl(url);
      })
      .catch((e: Error) => {
        setBlobUrl(null);
        setError(e.message);
      })
      .finally(() => setLoading(false));

    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [userId, filename, file]);

  if (!filename?.trim()) {
    return <p className="text-xs text-ink-faint italic">No document uploaded.</p>;
  }

  if (loading) {
    return <p className="text-xs font-mono text-ink-faint">Loading {label}…</p>;
  }

  if (error) {
    return <p className="text-xs text-red-600">{error}</p>;
  }

  if (!blobUrl) return null;

  if (isPdfFilename(filename)) {
    return (
      <iframe
        title={label}
        src={blobUrl}
        className="w-full h-[min(70vh,520px)] border border-border-soft rounded-sm bg-chalk-warm"
      />
    );
  }

  if (isImageFilename(filename)) {
    return (
      <img
        src={blobUrl}
        alt={label}
        className="max-w-full max-h-[min(70vh,520px)] border border-border-soft rounded-sm object-contain"
      />
    );
  }

  return (
    <a
      href={blobUrl}
      download={filename}
      className="text-xs font-semibold text-mint hover:underline"
    >
      Download {label}
    </a>
  );
}
