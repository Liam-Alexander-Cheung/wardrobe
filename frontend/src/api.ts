// Everything the page asks the Python server. One place, so tests can mock it.

export const CATEGORIES = ["top", "bottom", "outerwear", "shoes", "accessory", "fullbody"] as const;
export const SEASONS = ["spring", "summer", "autumn", "winter"] as const;
export type Category = (typeof CATEGORIES)[number];
export type Season = (typeof SEASONS)[number];

export interface Item {
  id: string;
  name: string;
  category: Category | null;
  colors: string[];
  pattern: string | null;
  formality: number | null;
  seasons: Season[];
  tags: string[];
  notes: string;
  created_at: string;
  last_worn: string | null;
  images: { original: string; cutout: string; thumb: string };
}
export type ItemPatch = Partial<Omit<Item, "id" | "created_at" | "images">>;

export interface Placement { item_id: string; slot: Category; x: number; y: number; z: number }
export interface OutfitIn { name: string; occasion: string; notes: string; items: Placement[] }
export interface Outfit extends OutfitIn {
  id: string;
  created_by: "liam" | "claude";
  created_at: string;
  items: (Placement & { name: string; images: Item["images"] })[];
}

export type AskEvent =
  | { type: "init"; session_id: string }
  | { type: "text"; text: string }
  | { type: "status"; text: string }
  | { type: "result"; session_id: string; is_error: boolean; turns: number }
  | { type: "changed" }
  | { type: "error"; text: string; fatal?: boolean };

// POST + read the Server-Sent Events stream by hand (EventSource can only do GET).
async function ask(message: string, sessionId: string | null, onEvent: (e: AskEvent) => void) {
  const r = await fetch("/api/ask", json("POST", { message, session_id: sessionId }));
  if (!r.ok || !r.body) {
    const body = await r.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `${r.status} ${r.statusText}`);
  }
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const f of frames) if (f.startsWith("data: ")) onEvent(JSON.parse(f.slice(6)));
  }
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? body.error ?? `${r.status} ${r.statusText}`);
  }
  return (r.status === 204 ? undefined : await r.json()) as T;
}
const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listItems: () => call<Item[]>("/api/items"),
  uploadItem: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<Item>("/api/items", { method: "POST", body: form });
  },
  updateItem: (id: string, patch: ItemPatch) => call<Item>(`/api/items/${id}`, json("PATCH", patch)),
  deleteItem: (id: string) => call<void>(`/api/items/${id}`, { method: "DELETE" }),
  listOutfits: () => call<Outfit[]>("/api/outfits"),
  createOutfit: (body: OutfitIn) => call<Outfit>("/api/outfits", json("POST", body)),
  updateOutfit: (id: string, body: OutfitIn) => call<Outfit>(`/api/outfits/${id}`, json("PUT", body)),
  deleteOutfit: (id: string) => call<void>(`/api/outfits/${id}`, { method: "DELETE" }),
  ask,
};
