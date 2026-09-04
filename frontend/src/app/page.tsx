import Link from "next/link";

const pages = [
  {
    title: "Query Playground",
    description: "Test RAG pipelines and stream answers.",
    href: "/playground",
  },
  {
    title: "Pipeline Manager",
    description: "Manage pipelines and view analytics.",
    href: "/pipelines",
  },
  {
    title: "Evaluation Feed",
    description: "Monitor evaluation scores in real time.",
    href: "/evaluations",
  },
  {
    title: "Documents",
    description: "Upload and inspect indexed documents.",
    href: "/documents",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-white">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-4xl font-bold">NeuroFlow</h1>
        <p className="mt-2 text-slate-400">
          RAG platform dashboard
        </p>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {pages.map((page) => (
            <Link
              key={page.href}
              href={page.href}
              className="rounded-xl border border-slate-800 bg-slate-900 p-6 transition hover:border-slate-600"
            >
              <h2 className="text-xl font-semibold">{page.title}</h2>
              <p className="mt-2 text-slate-400">
                {page.description}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
