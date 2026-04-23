import React from 'react';

interface VendorGlyphProps {
  label: string;
  iconSlug: string | null;
  className?: string;
}

const SHAPES = ['circle', 'triangle', 'hexagon', 'diamond', 'octagon'] as const;

export const VendorGlyph: React.FC<VendorGlyphProps> = ({ label, iconSlug, className }) => {
  if (iconSlug) {
    return (
      <div className={`vendor-glyph ${className ?? ''}`.trim()}>
        <img
          src={`/vendor-icons/logos/${iconSlug}.svg`}
          alt={label}
          loading="lazy"
          onError={(event) => {
            event.currentTarget.style.display = 'none';
            const fallback = event.currentTarget.nextElementSibling as HTMLElement | null;
            if (fallback) fallback.style.display = 'grid';
          }}
        />
        <div
          className={`vendor-glyph__fallback vendor-glyph__fallback--${pickShape(label)}`}
          style={{ display: 'none' }}
        >
          {label.charAt(0).toUpperCase()}
        </div>
      </div>
    );
  }

  return (
    <div className={`vendor-glyph ${className ?? ''}`.trim()}>
      <div className={`vendor-glyph__fallback vendor-glyph__fallback--${pickShape(label)}`}>
        {label.charAt(0).toUpperCase()}
      </div>
    </div>
  );
};

function pickShape(label: string) {
  const seed = label
    .split('')
    .reduce((total, char) => total + char.charCodeAt(0), 0);
  return SHAPES[seed % SHAPES.length];
}
