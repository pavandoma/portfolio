import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { githubIcon, SiteShell } from "@/components/site/shell";
import { formatDate, postBySlug, posts, readingMinutes } from "@/content/blog";
import { displayName } from "@/content/site";

export const dynamicParams = false;

export function generateStaticParams() {
  return posts.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const post = postBySlug((await params).slug);
  return {
    title: post?.title ?? "Blog",
    description: post?.excerpt,
    alternates: { canonical: post ? `/blog/${post.slug}/` : "/" },
  };
}

const back = (
  <svg viewBox="0 0 24 24" className="h-4 w-4 transition-transform duration-300 motion-safe:group-hover/back:-translate-x-1 motion-reduce:translate-none" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M19 12H5M11 18l-6-6 6-6" />
  </svg>
);

/**
 * One blog story: a narrow reading column on a boxed panel over the star
 * field, the story's key number as a callout, and links to the code and to
 * the next stories.
 */
export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const post = postBySlug((await params).slug);
  if (!post) notFound();
  const others = posts.filter((p) => p.slug !== post.slug);

  return (
    <SiteShell base="/" current="#blogs">
      <main className="relative px-4 pb-16 pt-28 md:px-6">
        <article className="mx-auto max-w-3xl rounded-[2rem] border border-white/10 bg-gray-950/80 px-6 py-12 md:px-14 md:py-16">
          <Link
            href="/#blogs"
            className="group/back -my-3 inline-flex items-center gap-2 py-3 text-sm text-gray-400 transition-[color,scale] duration-200 hover:text-emerald-300 active:scale-95"
          >
            {back}
            All stories
          </Link>

          <p className="mt-10 font-mono text-xs uppercase tracking-[0.2em] text-emerald-400">
            {post.project}
          </p>
          <h1 className="mt-4 text-3xl leading-[1.15] tracking-[-0.02em] text-white md:text-5xl">
            {post.title}
          </h1>
          <p className="mt-5 text-sm text-gray-400">
            {displayName} · {formatDate(post.date)} · {readingMinutes(post)} min read
          </p>

          <div className="mt-10 flex items-baseline gap-4 rounded-2xl border border-emerald-400/20 bg-emerald-400/5 px-6 py-5">
            <span className="text-4xl font-medium text-emerald-400">{post.figure.value}</span>
            <span className="text-sm text-gray-400">{post.figure.label}</span>
          </div>

          <div className="mt-10 space-y-6 text-[1.0625rem] leading-[1.75] text-gray-300">
            {post.body.map((para) =>
              para.startsWith("## ") ? (
                <h2 key={para} className="pt-4 text-xl tracking-[-0.01em] text-white md:text-2xl">
                  {para.slice(3)}
                </h2>
              ) : (
                <p key={para}>{para}</p>
              ),
            )}
          </div>

          <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-white/5 pt-8">
            <div className="flex flex-wrap gap-2">
              {post.tags.map((t) => (
                <span
                  key={t}
                  className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300"
                >
                  {t}
                </span>
              ))}
            </div>
            <a
              href={post.repo}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-4 py-2 text-sm text-white transition-[translate,border-color,color,scale] duration-300 motion-safe:hover:-translate-y-0.5 hover:border-emerald-400/60 hover:text-emerald-300 active:scale-[0.97] motion-reduce:translate-none"
            >
              {githubIcon()}
              View the code
            </a>
          </div>
        </article>

        <section aria-label="More stories" className="mx-auto mt-10 max-w-3xl">
          <h2 className="mb-5 px-2 text-lg text-white">More Stories</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {others.map((p) => (
              <Link
                key={p.slug}
                href={`/blog/${p.slug}/`}
                className="rounded-2xl border border-white/5 bg-gray-900/70 p-6 transition-[translate,border-color,scale] duration-300 motion-safe:hover:-translate-y-1 hover:border-emerald-400/30 active:scale-[0.99] motion-reduce:translate-none"
              >
                <p className="font-mono text-xs text-gray-400">{formatDate(p.date)}</p>
                <h3 className="mt-3 leading-snug text-white">{p.title}</h3>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
