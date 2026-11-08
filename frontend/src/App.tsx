import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "./api/client";
import type { Job } from "./api/types";
import { Entry } from "./components/Entry";
import { Failed, Progress } from "./components/Progress";
import { Results } from "./components/Results";
import { Button } from "./components/ui";
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
    return <Results features={job.data.features} result={job.data.result} />;
  }
  return <Progress status={job.data.status} />;
}

export function App() {
  const { jobId, setJob } = useSession();
  const queryClient = useQueryClient();

  function started(job: Job) {
    queryClient.setQueryData(["job", job.job_id], job);
    setJob(job.job_id);
  }

  return (
    <div className="mx-auto max-w-[1120px] px-4 pb-16">
      <header className="flex min-h-16 items-center justify-between gap-4 border-b border-line">
        <h1 className="font-mono text-small font-medium">Recomendador musical</h1>
        {jobId && <Button onClick={() => setJob(null)}>Nova análise</Button>}
      </header>
      <main className="pt-8">
        {jobId ? <Screen key={jobId} jobId={jobId} onReset={() => setJob(null)} /> : <Entry onStarted={started} />}
      </main>
    </div>
  );
}
