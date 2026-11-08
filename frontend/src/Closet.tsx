import { useState, type Dispatch, type SetStateAction } from "react";
import { api, CATEGORIES, type Item } from "./api";
import ItemEditor from "./ItemEditor";

type Filter = "all" | "untagged" | (typeof CATEGORIES)[number];
const LABELS: Record<Filter, string> = {
  all: "All", top: "Tops", bottom: "Bottoms", outerwear: "Outerwear", shoes: "Shoes",
  accessory: "Accessories", fullbody: "Full-body", untagged: "Untagged",
};

export function filterItems(items: Item[], filter: Filter, query: string): Item[] {
  const q = query.trim().toLowerCase();
  return items.filter((i) =>
    (filter === "all" || (filter === "untagged" ? i.category === null : i.category === filter)) &&
    (!q || [i.name, i.notes, ...i.colors, ...i.tags].some((s) => s.toLowerCase().includes(q))));
}

// Fashion colour words that aren't CSS colours (CSS knows navy, beige, khaki… already).
const SWATCH: Record<string, string> = {
  camel: "#c19a6b", cream: "#f3ead3", oyster: "#e8e2d4", ecru: "#e7dfc6", charcoal: "#36454f",
  stone: "#b8ad9a", denim: "#4a6890", burgundy: "#800020", rust: "#b7410e", mustard: "#d4a017",
  sage: "#9caf88", taupe: "#8b7d6b", mint: "#aaf0d1", "off-white": "#f4f1ea", multi: "conic-gradient(red, gold, teal, red)",
};
export const swatch = (c: string) => SWATCH[c.toLowerCase()] ?? c;

interface Progress { done: number; total: number; failed: number; current: string }

interface Props { items: Item[]; setItems: Dispatch<SetStateAction<Item[]>> }

export default function Closet({ items, setItems }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Item | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [dragging, setDragging] = useState(false);

  // One photo at a time: the server cuts each one out (1–3 s), and we can show progress.
  async function upload(files: File[]) {
    const images = files.filter((f) => f.type.startsWith("image/") || /\.hei[cf]$/i.test(f.name));
    const p: Progress = { done: 0, total: images.length, failed: 0, current: "" };
    for (const file of images) {
      setProgress({ ...p, current: file.name });
      try {
        const created = await api.uploadItem(file);
        setItems((prev) => [created, ...prev]);
      } catch {
        p.failed++;
      }
      p.done++;
    }
    setProgress({ ...p, current: "" });
  }

  const counts = (f: Filter) => filterItems(items, f, "").length;
  const shown = filterItems(items, filter, query);

  return (
    <main
      className={`closet${dragging ? " dragging" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false); }}
      onDrop={(e) => { e.preventDefault(); setDragging(false); upload([...e.dataTransfer.files]); }}
    >
      <div className="toolbar">
        <nav className="chips" aria-label="Filter by category">
          {(Object.keys(LABELS) as Filter[]).map((f) => (
            <button key={f} className={f === filter ? "chip on" : "chip"} onClick={() => setFilter(f)}>
              {LABELS[f]} <span>{counts(f)}</span>
            </button>
          ))}
        </nav>
        <input className="search" type="search" placeholder="Search colour, tag, name…"
               value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search" />
        <label className="add">
          Add photos
          <input type="file" accept="image/*,.heic,.heif" multiple hidden
                 onChange={(e) => { upload([...(e.target.files ?? [])]); e.target.value = ""; }} />
        </label>
      </div>

      {progress && (
        <p className="progress" role="status">
          {progress.current ? `Cutting out ${progress.current} · ` : "Done · "}
          {progress.done} of {progress.total}
          {progress.failed > 0 && ` · ${progress.failed} failed`}
        </p>
      )}

      {items.length === 0 ? (
        <div className="empty">
          <p>Your closet is empty.</p>
          <p>AirDrop your photos to this Mac, then drag them anywhere onto this page.</p>
        </div>
      ) : (
        <ul className="grid">
          {shown.map((i) => (
            <li key={i.id}>
              <button className="card" onClick={() => setOpen(i)} aria-label={i.name || "Untitled"}>
                <span className="tile"><img src={i.images.thumb} alt="" loading="lazy" /></span>
                <span className="label">{i.name || <em>Untitled</em>}</span>
                <span className="dots">
                  {i.colors.map((c) => <i key={c} style={{ background: swatch(c) }} title={c} />)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <ItemEditor
          item={open}
          onClose={() => setOpen(null)}
          onSaved={(u) => { setItems((prev) => prev.map((i) => (i.id === u.id ? u : i))); setOpen(null); }}
          onDeleted={(id) => { setItems((prev) => prev.filter((i) => i.id !== id)); setOpen(null); }}
        />
      )}
    </main>
  );
}
