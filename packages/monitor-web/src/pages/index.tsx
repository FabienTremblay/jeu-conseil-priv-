import { useEffect, useRef, useState } from "react";

function useLobby(baseApi: string) {
  const [parties, setParties] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // 1) fetch initial
  useEffect(() => {
    fetch(`${baseApi}/parties`)
      .then((r) => r.json())
      .then(setParties)
      .catch(() => {});
  }, [baseApi]);

  // 2) abonnement WS lobby
  useEffect(() => {
    const wsBase = baseApi.replace(/^http/, "ws").replace(/\/$/, "");
    const url = `${wsBase}/ws?partie=${encodeURIComponent("_lobby")}`;
    let stop = false,
      backoff = 500;

    const connect = () => {
      if (stop) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "partie_creee" && msg.data?.id_partie) {
            setParties((prev) => {
              if (prev.some((p) => p.id_partie === msg.data.id_partie))
                return prev;
              return [msg.data, ...prev];
            });
          }
        } catch {}
      };
      ws.onclose = () => {
        if (stop) return;
        setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 8000);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      stop = true;
      wsRef.current?.close();
    };
  }, [baseApi]);

  return parties;
}

export default function Home() {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const parties = useLobby(base);

  const [id, setId] = useState<string>();
  const [etat, setEtat] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  const creer = async () => {
    setErr("");
    try {
      const r = await fetch(`${base}/parties`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ joueurs: ["alice", "bob"] }),
      });
      const text = await r.text();
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${text}`);
      const data = JSON.parse(text);
      setId(data.id_partie);
      setEtat(data.etat);
    } catch (e: any) {
      setErr(String(e));
    }
  };

  const lire = async () => {
    if (!id) return;
    setErr("");
    try {
      const r = await fetch(`${base}/parties/${id}/etat`);
      setEtat(await r.json());
    } catch (e: any) {
      setErr(String(e));
    }
  };

  const jouer = async () => {
    if (!id) return;
    setErr("");
    try {
      const r = await fetch(`${base}/parties/${id}/actions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ type: "perturbation_retard", cible: "alice" }),
      });
      setEtat(await r.json());
    } catch (e: any) {
      setErr(String(e));
    }
  };

  return (
    <main style={{ padding: 24 }}>
      <h1>Moniteur — parties en cours</h1>
      <p>API: {base}</p>

      <h3>Lobby</h3>
      <ul>
        {parties.map((p: any) => (
          <li key={p.id_partie} style={{ marginBottom: 6 }}>
            <strong>{p.id_partie}</strong> — tour {p.tour} — joueurs:{" "}
            {p.nb_joueurs}
          </li>
        ))}
        {parties.length === 0 && <li>Aucune partie (encore)</li>}
      </ul>

      <hr style={{ margin: "16px 0" }} />

      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        <button onClick={creer}>Créer partie</button>
        <button onClick={lire} disabled={!id}>
          Lire état
        </button>
        <button onClick={jouer} disabled={!id}>
          Jouer “retard”
        </button>
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}

      <pre style={{ background: "#111", color: "#0f0", padding: 12 }}>
        {JSON.stringify({ id, etat }, null, 2)}
      </pre>
    </main>
  );
}
