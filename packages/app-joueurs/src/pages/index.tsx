//packages/app-joueurs/src/pages

import { useEffect, useRef, useState } from "react";

function usePartyWS(baseApi: string, partieId?: string) {
  const [etat, setEtat] = useState<any>();
  const ref = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!partieId) return;
    const wsBase = baseApi.replace(/^http/, "ws").replace(/\/$/, "");
    const url = `${wsBase}/ws?partie=${encodeURIComponent(partieId)}`;
    let stop = false,
      backoff = 500;

    const connect = () => {
      if (stop) return;
      const ws = new WebSocket(url);
      ref.current = ws;
      ws.onopen = () => {
        backoff = 500;
      };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "etat") setEtat(msg.data);
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
      ref.current?.close();
    };
  }, [baseApi, partieId]);

  return etat;
}

export default function AppJoueurs() {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const [id, setId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const etat = usePartyWS(base, id);

  const creer = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${base}/parties`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ joueurs: ["moi"] }),
      });
      const data = await r.json();
      setId(data.id_partie);
    } finally {
      setLoading(false);
    }
  };

  const jouer = async () => {
    if (!id) return;
    await fetch(`${base}/parties/${id}/actions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type: "perturbation_retard", cible: "moi" }),
    });
    // le WS poussera l’état à jour
  };

  return (
    <main
      style={{
        padding: 16,
        maxWidth: 520,
        margin: "0 auto",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h1 style={{ fontSize: 24, marginBottom: 12 }}>
        joueur — aventure politique
      </h1>
      <p style={{ opacity: 0.7, fontSize: 14, marginBottom: 16 }}>
        serveur: {base}
      </p>

      {!id ? (
        <button
          onClick={creer}
          disabled={loading}
          style={{
            width: "100%",
            padding: 12,
            borderRadius: 12,
            border: "1px solid #ddd",
          }}
        >
          {loading ? "création..." : "créer une partie"}
        </button>
      ) : (
        <>
          <div style={{ marginBottom: 12, fontSize: 14 }}>
            id partie: <code>{id}</code>
          </div>
          <button
            onClick={jouer}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 12,
              border: "1px solid #ddd",
              marginBottom: 12,
            }}
          >
            jouer «perturbation_retard»
          </button>
        </>
      )}

      <h3 style={{ fontSize: 16, marginTop: 16 }}>état (temps réel)</h3>
      <pre
        style={{
          background: "#111",
          color: "#0f0",
          padding: 12,
          borderRadius: 12,
          fontSize: 12,
          overflowX: "auto",
        }}
      >
        {JSON.stringify(
          etat ?? { info: id ? "en attente d'événements..." : "aucune partie" },
          null,
          2,
        )}
      </pre>
    </main>
  );
}
