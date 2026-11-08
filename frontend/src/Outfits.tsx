import { useEffect, useState } from "react";
import { api, CATEGORIES, type Category, type Item, type Outfit } from "./api";
import Board, { HOME, type Piece } from "./Board";

interface Props { items: Item[] }

export default function Outfits({ items }: Props) {
  const [outfits, setOutfits] = useState<Outfit[]>([]);
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [editing, setEditing] = useState<string | null>(null);   // id of the loaded outfit
  const [name, setName] = useState("");
  const [occasion, setOccasion] = useState("");
  const [pick, setPick] = useState<Category | "all">("all");
  const [error, setError] = useState("");

  useEffect(() => { api.listOutfits().then(setOutfits).catch((e) => setError(e.message)); }, []);

  const tagged = items.filter((i) => i.category !== null);
  const untagged = items.length - tagged.length;
  const onBoard = new Set(pieces.map((p) => p.item_id));

  function toggle(i: Item) {
    if (onBoard.has(i.id)) return setPieces((ps) => ps.filter((p) => p.item_id !== i.id));
    const slot = i.category!;
    const z = Math.max(0, ...pieces.map((p) => p.z)) + 1;
    setPieces((ps) => [...ps, { item_id: i.id, slot, ...HOME[slot], z, name: i.name, images: i.images }]);
  }
  const move = (id: string, x: number, y: number) =>
    setPieces((ps) => ps.map((p) => (p.item_id === id ? { ...p, x, y } : p)));
  const raise = (id: string) =>
    setPieces((ps) => { const top = Math.max(...ps.map((p) => p.z));
      return ps.map((p) => (p.item_id === id && p.z < top ? { ...p, z: top + 1 } : p)); });

  function load(o: Outfit) {
    setEditing(o.id); setName(o.name); setOccasion(o.occasion); setPieces(o.items);
  }
  function reset() { setEditing(null); setName(""); setOccasion(""); setPieces([]); }

  async function save() {
    const body = { name: name.trim() || "Untitled outfit", occasion, notes: "",
      items: pieces.map(({ item_id, slot, x, y, z }) => ({ item_id, slot, x, y, z })) };
    try {
      const o = editing ? await api.updateOutfit(editing, body) : await api.createOutfit(body);
      setOutfits((os) => [o, ...os.filter((x) => x.id !== o.id)]);
      setEditing(o.id); setError("");
    } catch (e) { setError((e as Error).message); }
  }

  async function remove(o: Outfit) {
    if (!window.confirm(`Delete outfit "${o.name}"? The clothes stay.`)) return;
    await api.deleteOutfit(o.id);
    setOutfits((os) => os.filter((x) => x.id !== o.id));
    if (editing === o.id) reset();
  }

  return (
    <main className="outfits">
      <section className="picker" role="region" aria-label="Pick items">
        <select value={pick} onChange={(e) => setPick(e.target.value as Category | "all")} aria-label="Show">
          <option value="all">All categories</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="mini-grid">
          {tagged.filter((i) => pick === "all" || i.category === pick).map((i) => (
            <button key={i.id} className={onBoard.has(i.id) ? "mini on" : "mini"} onClick={() => toggle(i)}
                    aria-label={i.name || "Untitled"} aria-pressed={onBoard.has(i.id)}>
              <img src={i.images.thumb} alt="" />
            </button>
          ))}
        </div>
        {untagged > 0 && <p className="hint">{untagged} untagged item{untagged > 1 && "s"} hidden. Give them a category in the closet.</p>}
      </section>

      <section className="stage">
        <Board pieces={pieces} label="Outfit board" onMove={move} onRaise={raise} />
        {pieces.length === 0 && <p className="board-hint">Pick pieces on the left. Drag them to arrange.</p>}
        <form className="save-row" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <input aria-label="Outfit name" placeholder="Name this outfit" value={name} onChange={(e) => setName(e.target.value)} />
          <input aria-label="Occasion" placeholder="Occasion" value={occasion} onChange={(e) => setOccasion(e.target.value)} />
          <button type="button" onClick={reset}>New</button>
          <button type="submit" className="primary" disabled={pieces.length === 0}>Save outfit</button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="saved" aria-label="Saved outfits">
        <h2>Saved <span>{outfits.length}</span></h2>
        <ul>
          {outfits.map((o) => (
            <li key={o.id} className={o.id === editing ? "current" : ""}>
              <button className="saved-card" onClick={() => load(o)} aria-label={`Open ${o.name}`}>
                <Board pieces={o.items} />
                <span className="saved-name">{o.name}</span>
                <span className="saved-meta">{o.occasion}{o.created_by === "claude" && <b> · by Claude</b>}</span>
              </button>
              <button className="x" onClick={() => remove(o)} aria-label={`Delete ${o.name}`}>×</button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
