import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "../App";
import { api, type Item } from "../api";
import { filterItems } from "../Closet";

vi.mock("../api", async (orig) => {
  const real = await orig<typeof import("../api")>();
  return { ...real, api: { listItems: vi.fn(), uploadItem: vi.fn(), updateItem: vi.fn(), deleteItem: vi.fn() } };
});
const mocked = vi.mocked(api);

let n = 0;
export function item(p: Partial<Item> = {}): Item {
  const id = (++n).toString(16).padStart(12, "0");
  return {
    id, name: "", category: null, colors: [], pattern: null, formality: null, seasons: [],
    tags: [], notes: "", created_at: "2026-11-08", last_worn: null,
    images: { original: `/o/${id}`, cutout: `/c/${id}`, thumb: `/t/${id}` }, ...p,
  };
}

const tee = item({ name: "Red tee", category: "top", colors: ["red"] });
const knit = item({ name: "Oyster jumper", category: "top", colors: ["white"], tags: ["wool"] });
const flare = item({ name: "Kick flare", category: "bottom", colors: ["blue"] });
const fresh = item();

beforeEach(() => {
  vi.clearAllMocks();
  mocked.listItems.mockResolvedValue([tee, knit, flare, fresh]);
});

describe("filterItems", () => {
  const all = [tee, knit, flare, fresh];
  it("filters by category and untagged", () => {
    expect(filterItems(all, "top", "")).toEqual([tee, knit]);
    expect(filterItems(all, "untagged", "")).toEqual([fresh]);
    expect(filterItems(all, "all", "")).toHaveLength(4);
  });
  it("searches name, colours and tags", () => {
    expect(filterItems(all, "all", "flare")).toEqual([flare]);
    expect(filterItems(all, "all", "WHITE")).toEqual([knit]);
    expect(filterItems(all, "all", "wool")).toEqual([knit]);
  });
});

describe("Closet", () => {
  it("shows items and filters by chip", async () => {
    render(<App />);
    expect(await screen.findByText("Red tee")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^bottoms/i }));
    expect(screen.getByText("Kick flare")).toBeInTheDocument();
    expect(screen.queryByText("Red tee")).not.toBeInTheDocument();
  });

  it("uploads picked photos one after another", async () => {
    const order: string[] = [];
    mocked.uploadItem.mockImplementation(async (f: File) => {
      order.push(f.name);
      return item({ name: f.name });
    });
    render(<App />);
    await screen.findByText("Red tee");
    const files = [new File(["a"], "IMG_1.jpg", { type: "image/jpeg" }),
                   new File(["b"], "IMG_2.jpg", { type: "image/jpeg" })];
    await userEvent.upload(screen.getByLabelText(/add photos/i), files);
    await waitFor(() => expect(screen.getByText("IMG_2.jpg")).toBeInTheDocument());
    expect(order).toEqual(["IMG_1.jpg", "IMG_2.jpg"]);
    expect(screen.getByRole("status")).toHaveTextContent("2 of 2");
  });

  it("reports a failed upload and carries on", async () => {
    mocked.uploadItem.mockRejectedValueOnce(new Error("not a readable image"))
                     .mockResolvedValueOnce(item({ name: "ok.jpg" }));
    render(<App />);
    await screen.findByText("Red tee");
    await userEvent.upload(screen.getByLabelText(/add photos/i),
      [new File(["x"], "bad.jpg", { type: "image/jpeg" }), new File(["y"], "ok.jpg", { type: "image/jpeg" })]);
    expect(await screen.findByText("ok.jpg")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/1 failed/);
  });
});

describe("Item editor", () => {
  it("saves changed fields only", async () => {
    mocked.updateItem.mockImplementation(async (_id, patch) => ({ ...fresh, ...patch }));
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /untitled/i }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "Black boots");
    await userEvent.selectOptions(within(dialog).getByLabelText("Category"), "shoes");
    await userEvent.click(within(dialog).getByRole("button", { name: "winter" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(mocked.updateItem).toHaveBeenCalledWith(fresh.id,
      { name: "Black boots", category: "shoes", seasons: ["winter"] });
    expect(await screen.findByText("Black boots")).toBeInTheDocument();
  });

  it("deletes after confirming", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mocked.deleteItem.mockResolvedValue(undefined);
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /kick flare/i }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
    expect(mocked.deleteItem).toHaveBeenCalledWith(flare.id);
    await waitFor(() => expect(screen.queryByText("Kick flare")).not.toBeInTheDocument());
  });
});
