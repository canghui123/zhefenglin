import { API_BASE, ApiError } from "./api";

export interface JobStatus {
  id: number;
  job_type: string;
  status: "queued" | "running" | "succeeded" | "failed";
  payload_json: string | null;
  result_json: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export async function getJobStatus(jobId: number): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(err.detail || "查询任务状态失败", res.status);
  }
  return res.json();
}

export async function pollJob(
  jobId: number,
  opts: { intervalMs?: number; maxAttempts?: number } = {}
): Promise<JobStatus> {
  const interval = opts.intervalMs ?? 1000;
  const maxAttempts = opts.maxAttempts ?? 120;

  for (let i = 0; i < maxAttempts; i++) {
    const job = await getJobStatus(jobId);
    if (job.status === "succeeded" || job.status === "failed") {
      return job;
    }
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new ApiError("任务超时，请稍后重试", 408);
}
