import { useCallback, useEffect, useState } from "react";
import { api, type Item } from "./api";
import AskPanel from "./AskPanel";
import Closet from "./Closet";
import Outfits from "./Outfits";

type View = "closet" | "outfits";

// App owns the item list so every view sees the same data. `version` goes up whenever
// Claude changed something (tagged items, saved an outfit), and the views reload.
export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [view, setView] = useState<View>("closet");
  const [askOpen, setAskOpen] = useState(false);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [demo, setDemo] = useState(false);

  useEffect(() => { api.health?.().then((h) => setDemo(h.demo)).catch(() => {}); }, []);

  useEffect(() => {
    api.listItems().then(setItems).catch((e) => setError(String(e.message ?? e)));
  }, [version]);
  const changed = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <div className={askOpen ? "shell with-ask" : "shell"}>
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
      {demo && <p className="demo-note">Demo wardrobe: drawn garments in a temporary folder. Nothing you change is kept.</p>}
      {error && <p className="error">Couldn't reach the server: {error}</p>}
      {view === "closet"
        ? <Closet items={items} setItems={setItems} />
        : <Outfits items={items} version={version} />}
      <AskPanel open={askOpen} onToggle={() => setAskOpen((o) => !o)} onChanged={changed} />
    </div>
  );
}
