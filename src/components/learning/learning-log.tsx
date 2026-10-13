"use client";

import { useMemo, useState } from "react";
import { ActivityGrid, CumulativeChart, Ring } from "@/components/learning/charts";
import { learning } from "@/content/learning";
import { useProgress } from "@/lib/learning-api";
import { computeStats } from "@/lib/learning-stats";

const label = "font-mono text-[11px] tracking-[0.24em] uppercase text-muted";

function Stat({ value, caption }: { value: string; caption: string }) {
  return (
    <div className="border-t border-hairline pt-4">
      <p className="font-sans text-[clamp(1.75rem,3.2vw,2.75rem)] leading-none font-light tracking-[-0.03em] text-foreground tabular-nums">
        {value}
      </p>
      <p className={`mt-3 ${label} !text-[10px] !tracking-[0.2em]`}>{caption}</p>
    </div>
  );
}

/** The owner's way in: a passphrase box that turns the checkboxes live. */
function EditControl({
  owner,
  message,
  onUnlock,
  onLock,
}: {
  owner: boolean;
  message: string | null;
  onUnlock: (value: string) => Promise<boolean>;
  onLock: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  if (owner) {
    return (
      <p className={`flex items-center gap-4 ${label}`}>
        <span className="text-lit">Editing</span>
        <button type="button" onClick={onLock} className="py-2 transition-colors hover:text-foreground">
          Lock
        </button>
      </p>
    );
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={`py-2 transition-colors hover:text-foreground ${label}`}>
        Edit
      </button>
    );
  }

  return (
    <form
      className="flex flex-wrap items-center gap-3"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!value || busy) return;
        setBusy(true);
        const ok = await onUnlock(value);
        setBusy(false);
        if (ok) {
          setValue("");
          setOpen(false);
        }
      }}
    >
      <label className="sr-only" htmlFor="passphrase">
        Passphrase
      </label>
      <input
        id="passphrase"
        type="password"
        autoComplete="current-password"
        autoFocus
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Passphrase"
        className="w-48 border-b border-hairline bg-transparent py-2 font-mono text-[12px] tracking-[0.1em] text-foreground outline-none placeholder:text-muted focus:border-lit"
      />
      <button type="submit" disabled={busy} className={`py-2 transition-colors hover:text-foreground disabled:opacity-50 ${label}`}>
        {busy ? "Checking" : "Unlock"}
      </button>
      <button type="button" onClick={() => setOpen(false)} className={`py-2 transition-colors hover:text-foreground ${label}`}>
        Cancel
      </button>
      {message && (
        <p role="alert" className="basis-full font-mono text-[11px] tracking-[0.14em] text-lit">
          {message}
        </p>
      )}
    </form>
  );
}

export function LearningLog() {
  const { done, updated, load, message, owner, unlock, lock, toggle } = useProgress();
  const stats = useMemo(() => computeStats(done), [done]);

  const updatedLabel = updated
    ? new Date(updated).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })
    : null;

  return (
    <div className="mx-auto w-full max-w-6xl px-6 pt-40 pb-32 sm:px-10">
      <header>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className={label}>{learning.label}</p>
          <EditControl owner={owner} message={message} onUnlock={unlock} onLock={lock} />
        </div>
        <h1 className="mt-5 max-w-4xl font-sans text-[clamp(2.25rem,6vw,5.5rem)] leading-[1] font-light tracking-[-0.04em] text-foreground">
          {learning.title}
        </h1>
        <p className="mt-8 max-w-xl text-lg leading-relaxed font-light text-muted">{learning.intro}</p>
        {owner && message && (
          <p role="alert" className="mt-6 font-mono text-[11px] tracking-[0.14em] text-lit">
            {message}
          </p>
        )}
        {load === "offline" && (
          <p role="status" className="mt-6 font-mono text-[11px] tracking-[0.14em] text-lit">
            Progress couldn&apos;t be loaded just now, so the path is shown without ticks.
          </p>
        )}
      </header>

      {/* Dashboard ------------------------------------------------------- */}
      <section aria-label="Progress" className="mt-20">
        <div className="grid grid-cols-2 gap-x-8 gap-y-10 sm:grid-cols-4">
          <Stat value={`${stats.percent}%`} caption="Of the path" />
          <Stat value={`${stats.done} / ${stats.total}`} caption="Steps finished" />
          <Stat value={`${stats.hoursDone} h`} caption={`Of ${stats.hoursTotal} h`} />
          <Stat value={`${stats.streak}`} caption="Day streak" />
        </div>

        <div className="mt-16 grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-5">
          {stats.tracks.map((track) => (
            <Ring key={track.id} percent={track.percent} label={track.title} done={track.done} total={track.total} />
          ))}
        </div>

        <div className="mt-20 grid gap-14 lg:grid-cols-[3fr_2fr]">
          <div>
            <p className={`mb-4 ${label}`}>Steps finished over time</p>
            <CumulativeChart series={stats.cumulative} total={stats.total} />
          </div>
          <div>
            <p className={`mb-4 ${label}`}>
              Last twenty weeks · {stats.last7} {stats.last7 === 1 ? "step" : "steps"} in the last 7 days
            </p>
            <ActivityGrid perDay={stats.perDay} />
          </div>
        </div>
        {updatedLabel && <p className={`mt-10 ${label} !text-[10px]`}>Last updated {updatedLabel}</p>}
      </section>

      {/* The path -------------------------------------------------------- */}
      <section aria-label="The learning path" className="mt-28 space-y-24">
        {learning.tracks.map((track, index) => {
          const trackStats = stats.tracks.find((t) => t.id === track.id);
          return (
            <div key={track.id} id={track.id}>
              <div className="flex flex-wrap items-baseline justify-between gap-4 border-t border-hairline pt-8">
                <div>
                  <p className={label}>{String(index + 1).padStart(2, "0")}</p>
                  <h2 className="mt-3 font-sans text-[clamp(1.75rem,3.4vw,3rem)] leading-[1.05] font-light tracking-[-0.03em] text-foreground">
                    {track.title}
                  </h2>
                  <p className="mt-3 max-w-md font-light text-muted">{track.summary}</p>
                </div>
                <p className="font-mono text-[11px] tracking-[0.2em] text-muted tabular-nums">
                  {trackStats?.done} / {trackStats?.total} · {trackStats?.percent}%
                </p>
              </div>

              <div className="mt-10 grid gap-x-16 gap-y-10 md:grid-cols-2">
                {track.modules.map((module) => (
                  <fieldset key={module.id}>
                    <legend className={`mb-4 ${label} !text-lit`}>{module.title}</legend>
                    <ul className="divide-y divide-hairline border-y border-hairline">
                      {module.items.map((item) => {
                        const finished = Boolean(done[item.id]);
                        return (
                          <li key={item.id}>
                            <label
                              className={`flex items-start gap-4 py-4 ${owner ? "cursor-pointer" : "cursor-default"}`}
                            >
                              <input
                                type="checkbox"
                                checked={finished}
                                disabled={!owner}
                                onChange={(event) => toggle(item.id, event.target.checked)}
                                className="peer sr-only"
                              />
                              <span
                                aria-hidden="true"
                                className="mt-1 grid size-4 shrink-0 place-items-center border border-muted text-background transition-colors peer-checked:border-lit peer-checked:bg-lit peer-focus-visible:outline peer-focus-visible:outline-1 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-lit"
                              >
                                <svg viewBox="0 0 12 12" className={`size-3 ${finished ? "opacity-100" : "opacity-0"}`}>
                                  <path d="M2.5 6.5 5 9l4.5-5.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                                </svg>
                              </span>
                              <span className="flex-1">
                                <span className={`block font-light ${finished ? "text-muted line-through decoration-hairline" : "text-foreground"}`}>
                                  {item.title}
                                </span>
                                <span className="mt-1 block font-mono text-[10px] tracking-[0.18em] text-muted tabular-nums">
                                  {item.hours} h{finished && done[item.id] ? ` · ${done[item.id]}` : ""}
                                </span>
                              </span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </fieldset>
                ))}
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
