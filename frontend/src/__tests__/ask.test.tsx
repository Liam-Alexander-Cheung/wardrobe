import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "../App";
import { Rich } from "../AskPanel";
import { api, type AskEvent } from "../api";

vi.mock("../api", async (orig) => {
  const real = await orig<typeof import("../api")>();
  const fns = ["listItems", "uploadItem", "updateItem", "deleteItem", "listOutfits",
               "createOutfit", "updateOutfit", "deleteOutfit", "ask"];
  return { ...real, api: Object.fromEntries(fns.map((f) => [f, vi.fn()])) };
});
const mocked = vi.mocked(api);

function script(events: AskEvent[]) {
  return async (_m: string, _s: string | null, onEvent: (e: AskEvent) => void) => {
    for (const e of events) onEvent(e);
  };
}
const HAPPY: AskEvent[] = [
  { type: "init", session_id: "s1" },
  { type: "text", text: "Saved " },
  { type: "status", text: "create_outfit" },
  { type: "text", text: "Cold School Day." },
  { type: "result", session_id: "s1", is_error: false, turns: 3 },
  { type: "changed" },
];

async function openPanel() {
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Ask Claude" }));
  return screen.getByRole("complementary", { name: "Ask Claude" });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.listItems.mockResolvedValue([]);
  mocked.listOutfits.mockResolvedValue([]);
});

it("streams the answer and continues the same session", async () => {
  mocked.ask.mockImplementation(script(HAPPY));
  const panel = await openPanel();
  await userEvent.type(screen.getByLabelText("Message"), "outfit for school, cold day{enter}");
  expect(await screen.findByText("Saved Cold School Day.")).toBeInTheDocument();
  expect(panel).toHaveTextContent("outfit for school, cold day");
  expect(mocked.ask.mock.calls[0][1]).toBeNull();

  await userEvent.type(screen.getByLabelText("Message"), "swap the shoes{enter}");
  await waitFor(() => expect(mocked.ask).toHaveBeenCalledTimes(2));
  expect(mocked.ask.mock.calls[1][1]).toBe("s1");
});

it("refreshes clothes after Claude changed something", async () => {
  mocked.ask.mockImplementation(script(HAPPY));
  await openPanel();
  const before = mocked.listItems.mock.calls.length;
  await userEvent.click(screen.getByRole("button", { name: /outfit for school/i }));   // suggestion
  await waitFor(() => expect(mocked.listItems.mock.calls.length).toBeGreaterThan(before));
});

it("shows which tool is running while Claude works", async () => {
  let finish!: () => void;
  mocked.ask.mockImplementation(async (_m, _s, onEvent) => {
    onEvent({ type: "status", text: "view_items" });
    await new Promise<void>((r) => (finish = r));
  });
  await openPanel();
  await userEvent.type(screen.getByLabelText("Message"), "hi{enter}");
  expect(await screen.findByText(/looking at your clothes/i)).toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toBeDisabled();
  finish();
  await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled());
});

it("shows errors", async () => {
  mocked.ask.mockImplementation(script([{ type: "error", text: "Can't find 'claude'." }]));
  await openPanel();
  await userEvent.type(screen.getByLabelText("Message"), "hi{enter}");
  expect(await screen.findByText(/can't find 'claude'/i)).toBeInTheDocument();
});

it("new chat forgets the session", async () => {
  mocked.ask.mockImplementation(script(HAPPY));
  await openPanel();
  await userEvent.type(screen.getByLabelText("Message"), "one{enter}");
  await screen.findByText("Saved Cold School Day.");
  await userEvent.click(screen.getByRole("button", { name: "New chat" }));
  expect(screen.queryByText("Saved Cold School Day.")).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Message"), "two{enter}");
  await waitFor(() => expect(mocked.ask).toHaveBeenCalledTimes(2));
  expect(mocked.ask.mock.calls[1][1]).toBeNull();
});

it("renders **bold** without showing the asterisks", () => {
  render(<p data-testid="b"><Rich text="pair the **Red tee** with **jeans**" /></p>);
  expect(screen.getByTestId("b")).toHaveTextContent("pair the Red tee with jeans");
  expect(screen.getByText("Red tee").tagName).toBe("STRONG");
});
