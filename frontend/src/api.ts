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
};
