"use client";

import { useState, type FormEvent } from "react";

/**
 * The site is a static export with no backend, so "Send" opens the visitor's
 * mail app with the message already composed.
 */
export function ContactForm({ email }: { email: string }) {
  const [sent, setSent] = useState(false);

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const name = `${data.get("first") ?? ""} ${data.get("last") ?? ""}`.trim();
    const subject = String(data.get("subject") || `Hello from ${name || "your site"}`);
    const body = `${data.get("message") ?? ""}\n\n— ${name}\n${data.get("email") ?? ""}`;
    window.location.href = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    setSent(true);
  };

  const field =
    "w-full rounded-lg border border-white/10 bg-black/40 px-4 py-3 text-sm text-white placeholder:text-gray-400 outline-none transition-colors focus:border-emerald-400/60";

  return (
    <form onSubmit={onSubmit} className="rounded-2xl border border-white/5 bg-gray-900/60 p-6 md:p-8">
      <h3 className="mb-6 text-xl text-white">Send me a message</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-2 block text-sm text-gray-400">First name</span>
          <input name="first" className={field} autoComplete="given-name" />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-gray-400">Last name</span>
          <input name="last" className={field} autoComplete="family-name" />
        </label>
      </div>
      <label className="mt-4 block">
        <span className="mb-2 block text-sm text-gray-400">Email</span>
        <input name="email" type="email" required className={field} autoComplete="email" />
      </label>
      <label className="mt-4 block">
        <span className="mb-2 block text-sm text-gray-400">Subject</span>
        <input name="subject" className={field} />
      </label>
      <label className="mt-4 block">
        <span className="mb-2 block text-sm text-gray-400">Message</span>
        <textarea name="message" rows={5} required className={`${field} resize-none`} />
      </label>
      <button
        type="submit"
        className="mt-6 w-full rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-black transition-[translate,scale,background-color,box-shadow] duration-300 ease-out motion-safe:hover:-translate-y-0.5 hover:bg-emerald-400 hover:shadow-lg hover:shadow-emerald-500/25 active:translate-y-0 active:scale-[0.98] motion-reduce:translate-none"
      >
        Send message
      </button>
      {sent && (
        <p className="mt-3 text-center text-sm text-gray-400" role="status">
          Your mail app should open with the message ready to send.
        </p>
      )}
    </form>
  );
}
