import clsx from "clsx";
import {
  useEffect,
  useMemo,
  useState,
} from "react";

import type { Annotation } from "../types";

interface MagnifierProps {
  annotation: Annotation;
  imageUrl: string;
  cursor: { x: number; y: number } | null;
}

export default function Magnifier({ annotation, imageUrl, cursor }: MagnifierProps): JSX.Element | null {
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const scale = 2;

  useEffect(() => {
    if (!imageUrl) {
      return;
    }
    const image = new Image();
    image.src = imageUrl;
    image.onload = () => {
      setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
    };
  }, [imageUrl]);

  const { style, position, magnifierDimensions } = useMemo(() => {
    if (!naturalSize || !cursor) {
      return {
        style: {},
        position: { left: 0, top: 0 },
        magnifierDimensions: { width: 0, height: 0 }
      };
    }

    const { bbox } = annotation;
    const magnifierWidth = bbox.width * scale;
    const magnifierHeight = bbox.height * scale;

    const backgroundSize = `${naturalSize.width * scale}px ${naturalSize.height * scale}px`;
    const backgroundPosition = `-${bbox.x * scale}px -${bbox.y * scale}px`;

    // Calculate intelligent positioning to prevent clipping
    const offset = 16;
    let left = cursor.x + offset;
    let top = cursor.y + offset;

    // Check viewport boundaries and adjust position
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Adjust horizontal position if clipping on right
    if (left + magnifierWidth > viewportWidth) {
      left = cursor.x - magnifierWidth - offset;
    }

    // Adjust vertical position if clipping on bottom
    if (top + magnifierHeight > viewportHeight) {
      top = cursor.y - magnifierHeight - offset;
    }

    // Ensure we don't go negative
    left = Math.max(0, left);
    top = Math.max(0, top);

    const style = {
      backgroundImage: `url(${imageUrl})`,
      backgroundSize,
      backgroundPosition,
    } as const;

    const position = { left, top };
    const magnifierDimensions = { width: magnifierWidth, height: magnifierHeight };

    return { style, position, magnifierDimensions };
  }, [annotation, imageUrl, naturalSize, scale, cursor]);

  if (!cursor) {
    return null;
  }

  return (
    <div
      className="pointer-events-none fixed z-50"
      style={{
        left: position.left,
        top: position.top,
      }}
    >
      <div
        className="rounded-lg border border-slate-700 shadow-lg overflow-hidden bg-slate-900"
        style={{ width: magnifierDimensions.width, height: magnifierDimensions.height }}
      >
        <div
          className={clsx("w-full h-full bg-no-repeat bg-cover pointer-events-none")}
          style={style}
        />
      </div>
    </div>
  );
}
