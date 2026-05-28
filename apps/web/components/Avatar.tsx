import { hueFor, initials } from "@/lib/format";

interface AvatarProps {
  name: string | null | undefined;
  size?: number;
}

export function Avatar({ name, size = 36 }: AvatarProps) {
  const hue = hueFor(name);
  return (
    <div
      className="ava"
      style={{
        width: size,
        height: size,
        borderRadius: `${(size * 0.28).toFixed(1)}px`,
        background: `linear-gradient(180deg, oklch(0.78 0.07 ${hue}) 0%, oklch(0.55 0.10 ${hue}) 100%)`,
        fontSize: `${(size * 0.36).toFixed(1)}px`,
      }}
    >
      {initials(name)}
    </div>
  );
}
