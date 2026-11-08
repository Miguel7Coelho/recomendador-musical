import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError, loginUrl } from "./api/client";
import type { Job } from "./api/types";
import { Drawer } from "./components/Drawer";
import { Entry } from "./components/Entry";
import { Favorites } from "./components/Favorites";
import { Failed, Progress } from "./components/Progress";
import { Results } from "./components/Results";
import { Button, Notice } from "./components/ui";
import { useSession } from "./store";

const POLL_MS = 1500;

function Screen({ jobId, onReset }: { jobId: string; onReset: () => void }) {
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 3,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "done" || status === "failed") return false;
      return query.state.error instanceof ApiError && query.state.error.status === 404 ? false : POLL_MS;
    },
    refetchOnWindowFocus: false,
  });

  if (job.error instanceof ApiError && job.error.status === 404) {
    return <Failed message="Esta análise expirou. Envie a faixa de novo." onRetry={onReset} />;
  }
  if (!job.data) {
    if (job.isError) return <Failed message="Não foi possível falar com o servidor." onRetry={onReset} />;
    return <p className="pt-12 text-muted">Carregando…</p>;
  }
  if (job.data.status === "failed") {
    return <Failed message={job.data.error ?? "A análise falhou."} onRetry={onReset} />;
  }
  if (job.data.status === "done" && job.data.features && job.data.result) {
    return <Results jobId={jobId} features={job.data.features} result={job.data.result} />;
  }
  return <Progress status={job.data.status} />;
}

function Account() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false, refetchOnWindowFocus: false });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => queryClient.resetQueries({ queryKey: ["me"] }),
  });

  if (!me.data) {
    return (
      <a href={loginUrl} className="inline-flex min-h-11 items-center rounded-sm border border-control px-4 hover:bg-raised">
        Entrar com Spotify
      </a>
    );
  }
  return (
    <>
      <span className="text-small text-muted">{me.data.display_name ?? "Conectado ao Spotify"}</span>
      <Button onClick={() => logout.mutate()} disabled={logout.isPending}>
        Sair
      </Button>
    </>
  );
}

const LOGIN_MESSAGES: Record<string, { tone: "info" | "danger"; text: string }> = {
  ok: { tone: "info", text: "Login no Spotify concluído." },
  cancelado: { tone: "info", text: "Login no Spotify cancelado." },
  erro: { tone: "danger", text: "Não foi possível entrar no Spotify. Tente de novo." },
};

export function App() {
  const { jobId, setJob, favorites } = useSession();
  const queryClient = useQueryClient();
  const [showFavorites, setShowFavorites] = useState(false);
  const [login] = useState(() => new URLSearchParams(window.location.search).get("login"));
  const loginMessage = login ? LOGIN_MESSAGES[login] : undefined;

  useEffect(() => {
    if (login) window.history.replaceState(null, "", window.location.pathname);
  }, [login]);

  function started(job: Job) {
    queryClient.setQueryData(["job", job.job_id], job);
    setJob(job.job_id);
  }

  return (
    <div className="mx-auto max-w-[1120px] px-4 pb-16">
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line py-2.5">
        <h1 className="font-mono text-small font-medium">Recomendador musical</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => setShowFavorites(true)}>Favoritas · {Object.keys(favorites).length}</Button>
          <Account />
          {jobId && <Button onClick={() => setJob(null)}>Nova análise</Button>}
        </div>
      </header>
      {loginMessage && (
        <div className="mt-4">
          <Notice tone={loginMessage.tone}>{loginMessage.text}</Notice>
        </div>
      )}
      <main className="pt-8">
        {jobId ? <Screen key={jobId} jobId={jobId} onReset={() => setJob(null)} /> : <Entry onStarted={started} />}
      </main>
      <Drawer open={showFavorites} onClose={() => setShowFavorites(false)} title="Favoritas">
        <Favorites />
      </Drawer>
    </div>
  );
}
