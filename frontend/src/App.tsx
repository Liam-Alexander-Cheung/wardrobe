import { useEffect, useState } from "react";
import { api, type Item } from "./api";
import Closet from "./Closet";

// App owns the item list so every view (closet now, outfit builder next) sees the same data.
export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listItems().then(setItems).catch((e) => setError(String(e.message ?? e)));
  }, []);

  return (
    <div className="shell">
      <header className="masthead">
        <h1>Wardrobe</h1>
        <p className="count">{items.length} pieces</p>
      </header>
      {error && <p className="error">Couldn't reach the server: {error}</p>}
      <Closet items={items} setItems={setItems} />
    </div>
  );
}
