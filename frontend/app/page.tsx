"use client";

import { useEffect, useMemo, useState } from "react";

type Job = {
  id: number;
  source: string;
  job_title: string | null;
  company: string | null;
  location: string | null;
  job_url: string | null;
  external_id: string | null;
  received_date: string;
  posted_date: string | null;
  raw_text: string;
  dedupe_fingerprint: string | null;
  processed_email_id: number;
  created_at: string;
  updated_at: string;
};

type JobsResponse = {
  total: number;
  items: Job[];
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
const NOT_AVAILABLE = "Not available";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [apiTotal, setApiTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function fetchJobs() {
      try {
        setLoading(true);
        setError(null);
        if (!API_URL) {
          throw new Error("NEXT_PUBLIC_API_URL is not configured");
        }
        const response = await fetch(`${API_URL}/api/v1/jobs`, {
          signal: controller.signal,
          headers: { Accept: "application/json" }
        });

        if (!response.ok) {
          throw new Error(`Jobs API returned ${response.status}`);
        }

        const data = (await response.json()) as JobsResponse;
        setJobs(Array.isArray(data.items) ? data.items : []);
        setApiTotal(Number.isFinite(data.total) ? data.total : 0);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Unable to load jobs");
        }
      } finally {
        setLoading(false);
      }
    }

    fetchJobs();
    return () => controller.abort();
  }, []);

  const filterOptions = useMemo(() => {
    return {
      sources: uniqueValues(jobs.map((job) => job.source)),
      companies: uniqueValues(jobs.map((job) => job.company)),
      locations: uniqueValues(jobs.map((job) => job.location))
    };
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    const query = search.trim().toLowerCase();
    return jobs
      .filter((job) => {
        const searchable = [job.job_title, job.company, job.location, job.source]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        return (
          (!query || searchable.includes(query)) &&
          (!source || job.source === source) &&
          (!company || job.company === company) &&
          (!location || job.location === location)
        );
      })
      .sort((a, b) => new Date(b.received_date).getTime() - new Date(a.received_date).getTime());
  }, [jobs, search, source, company, location]);

  return (
    <main className="page">
      <section className="header">
        <div>
          <h1>PetroMatch</h1>
          <p>Oil &amp; Gas Job Discovery</p>
        </div>
        <div className="summary" aria-label="Total jobs">
          <span>Total jobs</span>
          <strong>{apiTotal}</strong>
        </div>
      </section>

      <section className="controls" aria-label="Job filters">
        <label className="search">
          <span>Search</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title, company, location or source"
          />
        </label>

        <FilterSelect label="Source" value={source} options={filterOptions.sources} onChange={setSource} />
        <FilterSelect label="Company" value={company} options={filterOptions.companies} onChange={setCompany} />
        <FilterSelect label="Location" value={location} options={filterOptions.locations} onChange={setLocation} />
      </section>

      <section className="content" aria-live="polite">
        {loading ? <StateMessage title="Loading jobs" detail="Fetching the latest opportunities." /> : null}
        {!loading && error ? (
          <StateMessage title="Unable to load jobs" detail={`${error}. Check that the API is running at ${API_URL}.`} />
        ) : null}
        {!loading && !error && jobs.length === 0 ? (
          <StateMessage title="No jobs found" detail="No jobs are currently available from the backend." />
        ) : null}
        {!loading && !error && jobs.length > 0 && filteredJobs.length === 0 ? (
          <StateMessage title="No matching jobs" detail="Try clearing search or filter selections." />
        ) : null}

        {!loading && !error && filteredJobs.length > 0 ? (
          <div className="jobs" aria-label="Job results">
            {filteredJobs.map((job) => (
              <article className="job-card" key={job.id}>
                <div className="job-main">
                  <p className="source">{displayValue(job.source)}</p>
                  <h2>{displayValue(job.job_title)}</h2>
                  <dl>
                    <Field label="Company" value={job.company} />
                    <Field label="Location" value={job.location} />
                    <Field label="Received" value={formatDate(job.received_date)} />
                  </dl>
                </div>
                <div className="job-action">
                  {job.job_url ? (
                    <a href={job.job_url} target="_blank" rel="noreferrer" className="button">
                      Open Job
                    </a>
                  ) : (
                    <span className="button disabled" aria-disabled="true">
                      Open Job
                    </span>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{displayValue(value)}</dd>
    </div>
  );
}

function StateMessage({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="state">
      <h2>{title}</h2>
      <p>{detail}</p>
    </div>
  );
}

function uniqueValues(values: Array<string | null>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value)))).sort((a, b) =>
    a.localeCompare(b)
  );
}

function displayValue(value: string | null | undefined) {
  return value && value.trim() ? value : NOT_AVAILABLE;
}

function formatDate(value: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}
