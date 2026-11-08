import { useEffect, useRef, useState } from "react";
import { api, type AskEvent } from "./api";

// What each wardrobe tool means, in words, for the "working…" line.
const DOING: Record<string, string> = {
  wardrobe_summary: "Counting your clothes", list_items: "Going through your closet",
  view_items: "Looking at your clothes", update_item: "Tagging items",
  create_outfit: "Saving the outfit", list_outfits: "Checking saved outfits",
};
const SUGGESTIONS = [
  "Outfit for school, cold day",
  "What goes with my jeans?",
  "Tag my untagged items: look at them first, 6 at a time",
];

interface Msg { role: "you" | "claude"; text: string; error?: boolean }

// Claude is asked for plain text, but **bold** slips through sometimes: render just that.
export function Rich({ text }: { text: string }) {
  return <>{text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))}</>;
}
interface Props { open: boolean; onToggle: () => void; onChanged: () => void }

export default function AskPanel({ open, onToggle, onChanged }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [session, setSession] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [doing, setDoing] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  // Block body on purpose: Chrome's scrollIntoView returns a Promise, and an arrow that
  // returns it would hand React a non-function "cleanup" and crash the page.
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs, doing]);

  async function send(text: string) {
    text = text.trim();
    if (!text || doing) return;
    setDraft("");
    setDoing("Thinking");
    setMsgs((m) => [...m, { role: "you", text }, { role: "claude", text: "" }]);
    const append = (t: string, error = false) =>
      setMsgs((m) => { const last = m[m.length - 1];
        return [...m.slice(0, -1), { ...last, text: last.text + t, error: last.error || error }]; });

    const onEvent = (e: AskEvent) => {
      if (e.type === "init" || e.type === "result") setSession(e.session_id);
      else if (e.type === "text") { append(e.text); setDoing("Writing"); }
      else if (e.type === "status") setDoing(DOING[e.text] ?? e.text);
      else if (e.type === "changed") onChanged();
      else if (e.type === "error") append(e.text, true);
    };
    try { await api.ask(text, session, onEvent); }
    catch (err) { append((err as Error).message, true); }
    finally { setDoing(null); }
  }

  function reset() { setMsgs([]); setSession(null); }

  return (
    <>
      <button className="ask-fab" onClick={onToggle} aria-expanded={open}>Ask Claude</button>
      {open && (
        <aside className="ask" aria-label="Ask Claude">
          <header>
            <h2>Stylist</h2>
            <button onClick={reset} disabled={Boolean(doing)}>New chat</button>
            <button onClick={onToggle} aria-label="Close">×</button>
          </header>
          <div className="thread">
            {msgs.length === 0 && (
              <div className="suggest">
                <p>Claude can see your closet, tag items and save outfits here.</p>
                {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
            {msgs.map((m, i) => (
              <p key={i} className={`bubble ${m.role}${m.error ? " error" : ""}`}><Rich text={m.text} /></p>
            ))}
            {doing && <p className="doing">{doing}…</p>}
            <div ref={end} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); send(draft); }}>
            <input aria-label="Message" placeholder="Ask about an outfit…" value={draft}
                   disabled={Boolean(doing)} onChange={(e) => setDraft(e.target.value)} />
          </form>
          <p className="fine">Runs Claude Code on your Pro plan. Each question uses some of your quota.</p>
        </aside>
      )}
    </>
  );
}
