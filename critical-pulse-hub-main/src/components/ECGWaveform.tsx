const ECGWaveform = ({ className = '', color = '#06D6A0', strokeWidth = 1.5, animate = true }: {
  className?: string;
  color?: string;
  strokeWidth?: number;
  animate?: boolean;
}) => {
  const d = "M0 40 L40 40 L60 40 L80 40 L90 15 L100 60 L115 5 L130 55 L145 40 L180 40 L200 40 L220 40 L230 20 L240 58 L255 8 L270 52 L285 40 L320 40 L360 40 L380 40 L390 15 L400 60 L415 5 L430 55 L445 40 L480 40 L520 40 L540 40 L550 20 L560 58 L575 8 L590 52 L605 40 L640 40 L680 40 L700 40 L710 15 L720 60 L735 5 L750 55 L765 40 L800 40";

  return (
    <svg
      viewBox="0 0 800 70"
      fill="none"
      preserveAspectRatio="none"
      className={className}
    >
      <path
        d={d}
        stroke={color}
        strokeWidth={strokeWidth}
        fill="none"
        className={animate ? 'ecg-line' : ''}
      />
    </svg>
  );
};

export default ECGWaveform;
