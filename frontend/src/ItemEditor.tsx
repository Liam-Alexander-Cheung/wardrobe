import { useState } from "react";
import { api, CATEGORIES, SEASONS, type Item, type ItemPatch, type Season } from "./api";

const FORMALITY = ["gym", "casual", "smart casual", "smart", "formal"];
const splitList = (s: string) => s.split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);

interface Props {
  item: Item;
  onClose: () => void;
  onSaved: (item: Item) => void;
  onDeleted: (id: string) => void;
}

export default function ItemEditor({ item, onClose, onSaved, onDeleted }: Props) {
  const [draft, setDraft] = useState(item);
  const [colors, setColors] = useState(item.colors.join(", "));
  const [tags, setTags] = useState(item.tags.join(", "));
  const [error, setError] = useState("");
  const set = (p: Partial<Item>) => setDraft((d) => ({ ...d, ...p }));

  function changes(): ItemPatch {
    const next = { ...draft, colors: splitList(colors), tags: splitList(tags) };
    const patch: Record<string, unknown> = {};
    for (const k of ["name", "category", "colors", "pattern", "formality", "seasons", "tags", "notes"] as const) {
      if (JSON.stringify(next[k]) !== JSON.stringify(item[k])) patch[k] = next[k];
    }
    return patch as ItemPatch;
  }

  async function save() {
    try { onSaved(await api.updateItem(item.id, changes())); }
    catch (e) { setError((e as Error).message); }
  }

  async function remove() {
    if (!window.confirm(`Delete ${item.name || "this item"} and its photos?`)) return;
    try { await api.deleteItem(item.id); onDeleted(item.id); }
    catch (e) { setError((e as Error).message); }
  }

  const toggleSeason = (s: Season) =>
    set({ seasons: draft.seasons.includes(s) ? draft.seasons.filter((x) => x !== s) : [...draft.seasons, s] });

  return (
    <div className="scrim" onClick={onClose}>
      <aside className="editor" role="dialog" aria-label="Edit item" onClick={(e) => e.stopPropagation()}>
        <div className="hero"><img src={item.images.cutout} alt="" /></div>
        <form onSubmit={(e) => { e.preventDefault(); save(); }}>
          <label>Name<input value={draft.name} onChange={(e) => set({ name: e.target.value })} /></label>
          <label>Category
            <select value={draft.category ?? ""}
                    onChange={(e) => set({ category: (e.target.value || null) as Item["category"] })}>
              <option value="">untagged</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label>Colours<input value={colors} placeholder="navy, white" onChange={(e) => setColors(e.target.value)} /></label>
          <label>Pattern<input value={draft.pattern ?? ""} placeholder="plain, striped…"
                               onChange={(e) => set({ pattern: e.target.value || null })} /></label>
          <fieldset><legend>Formality</legend>
            {FORMALITY.map((f, i) => (
              <button type="button" key={f} title={f} className={draft.formality === i + 1 ? "seg on" : "seg"}
                      onClick={() => set({ formality: draft.formality === i + 1 ? null : i + 1 })}>{f}</button>
            ))}
          </fieldset>
          <fieldset><legend>Seasons</legend>
            {SEASONS.map((s) => (
              <button type="button" key={s} className={draft.seasons.includes(s) ? "seg on" : "seg"}
                      onClick={() => toggleSeason(s)}>{s}</button>
            ))}
          </fieldset>
          <label>Tags<input value={tags} placeholder="wool, vintage" onChange={(e) => setTags(e.target.value)} /></label>
          <label>Notes<textarea value={draft.notes} rows={2} onChange={(e) => set({ notes: e.target.value })} /></label>
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button type="button" className="danger" onClick={remove}>Delete</button>
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary">Save</button>
          </div>
        </form>
      </aside>
    </div>
  );
}
