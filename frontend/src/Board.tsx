import { useRef } from "react";
import type { Category, Item } from "./api";

// The flat-lay board: garments lie where you'd lay them on a bed. Positions are stored as
// 0..1 of the board, so the same outfit looks right at any size (gallery thumbnails too).

export interface Piece { item_id: string; slot: Category; x: number; y: number; z: number;
  name: string; images: Item["images"] }

export const HOME: Record<Category, { x: number; y: number }> = {
  outerwear: { x: 0.3, y: 0.3 }, top: { x: 0.55, y: 0.27 }, fullbody: { x: 0.5, y: 0.42 },
  bottom: { x: 0.52, y: 0.64 }, shoes: { x: 0.5, y: 0.9 }, accessory: { x: 0.85, y: 0.16 },
};
const SIZE: Record<Category, { w: number; h: number }> = {   // % of board width / height
  outerwear: { w: 50, h: 44 }, top: { w: 46, h: 38 }, fullbody: { w: 46, h: 70 },
  bottom: { w: 38, h: 46 }, shoes: { w: 28, h: 14 }, accessory: { w: 20, h: 18 },
};
const clamp = (v: number) => Math.min(1, Math.max(0, v));

interface Props {
  pieces: Piece[];
  label?: string;
  onMove?: (id: string, x: number, y: number) => void;
  onRaise?: (id: string) => void;
}

export default function Board({ pieces, label, onMove, onRaise }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const editable = Boolean(onMove);

  function drag(e: React.PointerEvent<HTMLImageElement>, p: Piece) {
    if (!editable || !ref.current) return;
    e.preventDefault();
    onRaise?.(p.item_id);
    const rect = ref.current.getBoundingClientRect();
    const start = { x: e.clientX, y: e.clientY, px: p.x, py: p.y };
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) =>
      onMove!(p.item_id, clamp(start.px + (ev.clientX - start.x) / rect.width),
                         clamp(start.py + (ev.clientY - start.y) / rect.height));
    const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  return (
    <div ref={ref} className={editable ? "board editable" : "board"} role={label ? "region" : undefined}
         aria-label={label}>
      {[...pieces].sort((a, b) => a.z - b.z).map((p) => (
        <img key={p.item_id} src={p.images.cutout} alt={p.name || "item"} draggable={false}
             onPointerDown={(e) => drag(e, p)}
             style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%`, zIndex: p.z,
                      maxWidth: `${SIZE[p.slot].w}%`, maxHeight: `${SIZE[p.slot].h}%` }} />
      ))}
    </div>
  );
}
