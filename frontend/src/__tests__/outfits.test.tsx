import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "../App";
import { api, type Item, type Outfit } from "../api";

vi.mock("../api", async (orig) => {
  const real = await orig<typeof import("../api")>();
  const fns = ["listItems", "uploadItem", "updateItem", "deleteItem",
               "listOutfits", "createOutfit", "updateOutfit", "deleteOutfit"];
  return { ...real, api: Object.fromEntries(fns.map((f) => [f, vi.fn()])) };
});
const mocked = vi.mocked(api);

function item(id: string, name: string, category: Item["category"]): Item {
  return { id, name, category, colors: [], pattern: null, formality: null, seasons: [], tags: [],
           notes: "", created_at: "", last_worn: null,
           images: { original: `/o/${id}`, cutout: `/c/${id}`, thumb: `/t/${id}` } };
}
const tee = item("a", "Red tee", "top");
const jeans = item("b", "Kick flare", "bottom");
const raw = item("c", "", null);

const saved: Outfit = {
  id: "o1", name: "Saturday", occasion: "town", notes: "", created_by: "claude", created_at: "",
  items: [{ item_id: "a", slot: "top", x: 0.5, y: 0.3, z: 0, name: "Red tee", images: tee.images }],
};

async function openOutfits() {
  render(<App />);
  await userEvent.click(await screen.findByRole("tab", { name: "Outfits" }));
}
const board = () => screen.getByRole("region", { name: "Outfit board" });
const picker = () => screen.getByRole("region", { name: "Pick items" });

beforeEach(() => {
  vi.clearAllMocks();
  mocked.listItems.mockResolvedValue([tee, jeans, raw]);
  mocked.listOutfits.mockResolvedValue([saved]);
});

it("places a picked item on the board and toggles it off again", async () => {
  await openOutfits();
  await userEvent.click(within(picker()).getByRole("button", { name: "Kick flare" }));
  expect(within(board()).getByAltText("Kick flare")).toBeInTheDocument();
  await userEvent.click(within(picker()).getByRole("button", { name: "Kick flare" }));
  expect(within(board()).queryByAltText("Kick flare")).not.toBeInTheDocument();
});

it("only offers tagged items", async () => {
  await openOutfits();
  expect(within(picker()).getAllByRole("button", { name: /red tee|kick flare/i })).toHaveLength(2);
  expect(within(picker()).getByText(/1 untagged/)).toBeInTheDocument();
});

it("saves a new outfit with slots and positions", async () => {
  mocked.createOutfit.mockImplementation(async (body) => ({ ...saved, id: "o2", ...body,
    created_by: "liam", items: [] }));
  await openOutfits();
  await userEvent.click(within(picker()).getByRole("button", { name: "Red tee" }));
  await userEvent.click(within(picker()).getByRole("button", { name: "Kick flare" }));
  await userEvent.type(screen.getByLabelText("Outfit name"), "School, cold");
  await userEvent.click(screen.getByRole("button", { name: "Save outfit" }));
  const body = mocked.createOutfit.mock.calls[0][0];
  expect(body.name).toBe("School, cold");
  expect(body.items.map((i) => [i.item_id, i.slot])).toEqual([["a", "top"], ["b", "bottom"]]);
  expect(body.items[0].y).toBeLessThan(body.items[1].y);           // top sits above bottom
  expect(await screen.findByRole("button", { name: /open school, cold/i })).toBeInTheDocument();
});

it("loads a saved outfit, marks Claude's, and updates it", async () => {
  mocked.updateOutfit.mockImplementation(async (id, body) => ({ ...saved, ...body, id, items: saved.items }));
  await openOutfits();
  const card = await screen.findByRole("button", { name: /open saturday/i });
  expect(card).toHaveTextContent(/by claude/i);
  await userEvent.click(card);
  expect(within(board()).getByAltText("Red tee")).toBeInTheDocument();
  expect(screen.getByLabelText("Outfit name")).toHaveValue("Saturday");
  await userEvent.click(screen.getByRole("button", { name: "Save outfit" }));
  expect(mocked.updateOutfit).toHaveBeenCalledWith("o1", expect.objectContaining({ name: "Saturday" }));
});

it("deletes a saved outfit", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  mocked.deleteOutfit.mockResolvedValue(undefined);
  await openOutfits();
  await userEvent.click(await screen.findByRole("button", { name: /delete saturday/i }));
  expect(mocked.deleteOutfit).toHaveBeenCalledWith("o1");
  expect(screen.queryByRole("button", { name: /open saturday/i })).not.toBeInTheDocument();
});
