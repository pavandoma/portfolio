"use client";

import { useState } from "react";

type Snippet = { code: string; prompt?: boolean; hint?: string };

/**
 * "Add me to your agent": the MCP endpoint as a copyable snippet, one tab per
 * client. Claude Code and the Codex CLI take a one-line command; ChatGPT
 * takes the bare URL as a custom connector.
 *
 * Tabs and Copy are 44px tall (the phone touch-target size) and use
 * `touch-action: manipulation` so a tap never waits on double-tap-to-zoom.
 */
export function AgentConnect({ url }: { url: string }) {
  const snippets: Record<string, Snippet> = {
    Claude: { code: `claude mcp add -t http pavan ${url}`, prompt: true },
    ChatGPT: {
      code: url,
      hint: "Developer mode → add a connector with this URL, no auth.",
    },
    CLI: {
      code: `codex mcp add pavan --url ${url}`,
      prompt: true,
      hint: "OpenAI Codex CLI. Any MCP client that takes a URL works too.",
    },
  };
  const tabs = Object.keys(snippets);
  const [tab, setTab] = useState(tabs[0]);
  const [copied, setCopied] = useState(false);
  const current = snippets[tab];

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(current.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard blocked (insecure context or permissions): the text stays selectable.
    }
  };

  return (
    <div className="mt-6 max-w-xl">
      <p className="text-gray-300">
        Want to know about me? <span className="text-emerald-400">Add me to your agent.</span>
      </p>

      <div className="mt-3 overflow-hidden rounded-xl border border-white/10 bg-gray-950/90">
        <div className="flex items-center justify-between border-b border-white/5 px-2">
          <div className="flex" role="tablist" aria-label="Agent">
            {tabs.map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                onClick={() => {
                  setTab(t);
                  setCopied(false);
                }}
                className={`flex min-h-11 touch-manipulation items-center border-b-2 px-3 font-mono text-xs transition-[color,border-color,scale] duration-150 active:scale-95 ${
                  tab === t
                    ? "border-emerald-400 text-emerald-300"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={copy}
            className="flex min-h-11 touch-manipulation items-center rounded-md px-3 font-mono text-xs text-gray-400 transition-[color,background-color,scale] duration-200 hover:bg-emerald-400/10 hover:text-emerald-300 active:scale-95"
            aria-live="polite"
          >
            {copied ? "Copied ✓" : "Copy"}
          </button>
        </div>
        <pre className="whitespace-pre-wrap px-4 py-3 font-mono text-[0.8rem] leading-relaxed text-gray-200 [overflow-wrap:anywhere]">
          {current.prompt && <span className="select-none text-emerald-400">$ </span>}
          <code>{current.code}</code>
        </pre>
        {current.hint && (
          <p className="border-t border-white/5 px-4 py-2 text-xs text-gray-400">{current.hint}</p>
        )}
      </div>
    </div>
  );
}
