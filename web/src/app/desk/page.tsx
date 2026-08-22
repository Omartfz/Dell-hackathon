"use client";

import { useCallback, useState } from "react";

import { Ambient, Chip, Dot, Header } from "@/components/shell";
import { Dropzone } from "@/components/dropzone";
import { ResultView } from "@/components/result-view";
import { Button } from "@/components/ui/button";
import { download, formatBytes, redactFile, type Job } from "@/lib/client";

const STAGE_LABEL: Record<Job["stage"], string> = {
  queued: "Queued",
  reading: "Reading",
  model: "Local model",
  redacting: "Redacting",
  done: "Done",
  error: "Stopped",
};

function JobCard({ job }: { job: Job }) {
  const tone =
    job.stage === "done" ? "success" : job.stage === "error" ? "danger" : "info";
  const live = job.stage !== "done" && job.stage !== "error";

  return (
    <div className="glass flex flex-wrap items-center gap-3 rounded-[12px] px-4 py-3">
      <Dot tone={tone} live={live} />
      <p className="min-w-0 flex-1 truncate text-[14px] font-medium">{job.name}</p>
      <span className="mono-micro">{formatBytes(job.size)}</span>
      <Chip tone={tone}>{STAGE_LABEL[job.stage]}</Chip>
      {job.detail && <span className="mono-micro w-full">{job.detail}</span>}
      {job.error && (
        <p className="w-full text-[13px] text-danger">{job.error}</p>
      )}
    </div>
  );
}

export default function Desk() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);

  const patch = useCallback((id: string, next: Partial<Job>) => {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, ...next } : job)),
    );
  }, []);

  const start = useCallback(
    async (files: File[]) => {
      const queued: Job[] = files.map((file) => ({
        id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
        name: file.name,
        size: file.size,
        stage: "queued",
      }));
      setJobs((current) => [...current, ...queued]);
      setBusy(true);

      // One at a time: a single local GPU is doing the thinking.
      for (const [index, job] of queued.entries()) {
        try {
          await redactFile(files[index], (event) => {
            if (event.stage === "model") {
              patch(job.id, { stage: "model", detail: `RUNNING ${event.model.toUpperCase()}` });
            } else if (event.stage === "redacting") {
              patch(job.id, {
                stage: "redacting",
                detail: `${event.proposed} VALUES PROPOSED, APPLYING POLICY`,
              });
            } else if (event.stage === "done") {
              patch(job.id, { stage: "done", detail: undefined, result: event.file });
            } else if (event.stage === "error") {
              patch(job.id, { stage: "error", detail: undefined, error: event.error });
            } else {
              patch(job.id, { stage: "reading" });
            }
          });
        } catch (error) {
          patch(job.id, {
            stage: "error",
            error: error instanceof Error ? error.message : String(error),
          });
        }
      }

      setBusy(false);
    },
    [patch],
  );

  const results = jobs.filter((job) => job.result).map((job) => job.result!);
  const empty = jobs.length === 0;

  return (
    <>
      <Ambient />
      <Header
        tagline="THE DOCUMENT NEVER LEAVES THIS MACHINE"
        action={
          !empty && (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => setJobs([])}
            >
              Clear
            </Button>
          )
        }
      />

      <main className="mx-auto w-full max-w-[1240px] flex-1 px-6 pb-24 md:px-12">
        {empty ? (
          <div className="mx-auto max-w-[720px] pt-10 md:pt-16">
            <h1 className="text-[32px] leading-[1.1] font-semibold tracking-[-0.035em] sm:text-[40px]">
              What are we making safe today?
            </h1>
            <p className="mt-3 max-w-[52ch] text-[16px] text-ink-2">
              Drop the files you would send to an AI tool if you were allowed
              to. You get back a copy with the identifying parts swapped for
              stable handles.
            </p>
            <div className="mt-8">
              <Dropzone onFiles={start} />
            </div>
          </div>
        ) : (
          <div className="space-y-6 pt-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <p className="mono-eyebrow">02 · WORKING</p>
                {results.length > 1 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      results.forEach((file) =>
                        download(
                          file.download.base64,
                          file.download.mime,
                          file.safeName,
                        ),
                      )
                    }
                  >
                    Download all
                  </Button>
                )}
              </div>
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>

            {results.map((file) => (
              <ResultView key={file.safeName} file={file} />
            ))}

            <Dropzone onFiles={start} compact />
          </div>
        )}
      </main>
    </>
  );
}
