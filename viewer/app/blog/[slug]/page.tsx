import Link from "next/link";
import { notFound } from "next/navigation";
import { POSTS } from "@/lib/blog";

export default async function BlogPostPage({ params }: PageProps<"/blog/[slug]">) {
  const { slug } = await params;
  const post = POSTS.find((p) => p.slug === slug);
  if (!post) notFound();

  return (
    <div className="wrap">
      <p className="subtitle">
        <Link href="/blog">&larr; all posts</Link>
      </p>
      <div className="blog-date">{post.date}</div>
      <h1>{post.title}</h1>

      <div className="blog-body">
        {post.body.map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </div>

      <ul className="commit-list">
        {post.commits.map((c) => (
          <li key={c.hash}>
            <span className="commit-hash">{c.hash}</span>
            {c.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
