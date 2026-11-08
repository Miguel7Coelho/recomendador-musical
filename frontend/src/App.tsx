import { useQuery } from "@tanstack/react-query";

import { api } from "./api/client";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const status = health.isPending ? "verificando" : health.isSuccess ? "conectado" : "fora do ar";

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-8">
      <h1 className="text-title font-semibold">Recomendador musical</h1>
      <p className="mt-2 font-mono text-label text-muted uppercase">Gateway: {status}</p>
    </main>
  );
}
