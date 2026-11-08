import { useEffect, useState } from "react";
import { api, type Item } from "./api";
import Closet from "./Closet";
import Outfits from "./Outfits";

type View = "closet" | "outfits";

// App owns the item list so every view (closet, outfit builder) sees the same data.
export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [view, setView] = useState<View>("closet");
  const [error, setError] = useState("");

  useEffect(() => {
    api.listItems().then(setItems).catch((e) => setError(String(e.message ?? e)));
  }, []);

  return (
    <div className="shell">
      <header className="masthead">
        <h1>Wardrobe</h1>
        <nav className="tabs" role="tablist">
          {(["closet", "outfits"] as View[]).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}>
              {v === "closet" ? "Closet" : "Outfits"}
            </button>
          ))}
        </nav>
        <p className="count">{items.length} pieces</p>
      </header>
      {error && <p className="error">Couldn't reach the server: {error}</p>}
      {view === "closet" ? <Closet items={items} setItems={setItems} /> : <Outfits items={items} />}
    </div>
  );
}
