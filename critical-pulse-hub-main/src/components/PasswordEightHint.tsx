/** Site-wide student password rule (matches PHP registration / reset). */
export const PASSWORD_EXACT_LENGTH = 8;

export const PASSWORD_EXACT_MESSAGE = 'Password must be exactly 8 characters.';

export function PasswordEightHint({ value }: { value: string }) {
  if (!value) {
    return (
      <p className="font-sans text-[12px] text-ink-muted mt-1.5">{PASSWORD_EXACT_MESSAGE}</p>
    );
  }
  if (value.length === PASSWORD_EXACT_LENGTH) {
    return (
      <p className="font-sans text-[12px] text-mint mt-1.5">8 characters — OK.</p>
    );
  }
  return (
    <p className="font-sans text-[12px] text-amber-700 mt-1.5">
      {PASSWORD_EXACT_MESSAGE} ({value.length}/{PASSWORD_EXACT_LENGTH})
    </p>
  );
}
