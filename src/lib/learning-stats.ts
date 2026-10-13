import { allItems, learning } from "@/content/learning";

/** item id → the day it was finished, "YYYY-MM-DD". */
export type DoneMap = Record<string, string>;

const DAY_MS = 86_400_000;

/** "YYYY-MM-DD" → a Date at local midnight (never UTC, so days don't shift). */
export function parseDay(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDay(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

const addDays = (date: Date, days: number) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
const dayDiff = (a: Date, b: Date) => Math.round((a.getTime() - b.getTime()) / DAY_MS);

export type TrackStats = {
  id: string;
  title: string;
  done: number;
  total: number;
  percent: number;
};

export type Stats = {
  done: number;
  total: number;
  percent: number;
  hoursDone: number;
  hoursTotal: number;
  streak: number;
  last7: number;
  tracks: TrackStats[];
  /** Cumulative items finished per day, oldest first, ending today. */
  cumulative: { day: string; count: number }[];
  /** Items finished per day, for the activity grid. */
  perDay: Record<string, number>;
};

/**
 * Everything the dashboard shows, computed from the saved ticks and the path.
 * Ticks for ids no longer in the path are ignored, so removing a step from
 * learning.ts quietly drops it from the numbers rather than breaking them.
 */
export function computeStats(done: DoneMap, today: Date = new Date()): Stats {
  const known = allItems.filter((item) => done[item.id]);
  const total = allItems.length;

  const perDay: Record<string, number> = {};
  for (const item of known) perDay[done[item.id]] = (perDay[done[item.id]] ?? 0) + 1;

  const tracks = learning.tracks.map((track) => {
    const ids = allItems.filter((item) => item.trackId === track.id);
    const finished = ids.filter((item) => done[item.id]).length;
    return {
      id: track.id,
      title: track.title,
      done: finished,
      total: ids.length,
      percent: ids.length ? Math.round((finished / ids.length) * 100) : 0,
    };
  });

  // Cumulative line: from the earlier of the first finish or four weeks ago.
  const todayDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Object.keys(perDay).sort();
  const first = days.length ? parseDay(days[0]) : todayDay;
  const start = dayDiff(todayDay, first) > 27 ? first : addDays(todayDay, -27);
  const cumulative: { day: string; count: number }[] = [];
  let running = 0;
  for (let cursor = start; cursor <= todayDay; cursor = addDays(cursor, 1)) {
    const key = formatDay(cursor);
    running += perDay[key] ?? 0;
    cumulative.push({ day: key, count: running });
  }
  // Anything dated before the window (older than `start` can't happen) or in
  // the future still counts toward the total shown, so reconcile the last point.
  if (cumulative.length) cumulative[cumulative.length - 1].count = known.length;

  // Streak: consecutive days with a finish, ending today or yesterday.
  let streak = 0;
  let cursor = perDay[formatDay(todayDay)] ? todayDay : addDays(todayDay, -1);
  while (perDay[formatDay(cursor)]) {
    streak += 1;
    cursor = addDays(cursor, -1);
  }

  let last7 = 0;
  for (let i = 0; i < 7; i += 1) last7 += perDay[formatDay(addDays(todayDay, -i))] ?? 0;

  return {
    done: known.length,
    total,
    percent: total ? Math.round((known.length / total) * 100) : 0,
    hoursDone: known.reduce((sum, item) => sum + item.hours, 0),
    hoursTotal: allItems.reduce((sum, item) => sum + item.hours, 0),
    streak,
    last7,
    tracks,
    cumulative,
    perDay,
  };
}

/** The last `weeks` weeks as columns of seven days (Sunday first), ending this week. */
export function activityWeeks(perDay: Record<string, number>, weeks = 20, today: Date = new Date()) {
  const todayDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const endOfGrid = addDays(todayDay, 6 - todayDay.getDay());
  const startOfGrid = addDays(endOfGrid, -(weeks * 7 - 1));
  const columns: { day: string; count: number; future: boolean }[][] = [];
  for (let w = 0; w < weeks; w += 1) {
    const column = [];
    for (let d = 0; d < 7; d += 1) {
      const date = addDays(startOfGrid, w * 7 + d);
      const key = formatDay(date);
      column.push({ day: key, count: perDay[key] ?? 0, future: date > todayDay });
    }
    columns.push(column);
  }
  return columns;
}
