import type { ReactNode, CSSProperties } from "react";
import { PaperTexture } from "@paper-design/shaders-react";

interface SlipCardProps {
  children: ReactNode;
  accent?: string;
  className?: string;
  style?: CSSProperties;
}

export function SlipCard({
  children,
  accent,
  className = "",
  style,
}: SlipCardProps) {
  return (
    <div
      className={`slip-card ${className}`}
      style={
        {
          "--slip-accent": accent ?? "var(--border)",
          ...style,
        } as CSSProperties
      }
    >
      <PaperTexture
        colorBack="#faf8f4"
        colorFront="#c9c0b4"
        contrast={0.25}
        roughness={0.4}
        fiber={0.3}
        fiberSize={0.2}
        crumples={0.25}
        crumpleSize={0.35}
        folds={0.5}
        foldCount={4}
        drops={0.15}
        fade={0}
        seed={7.2}
        scale={0.55}
        minPixelRatio={1}
        className="slip-paper-texture"
      />
      {children}
    </div>
  );
}
