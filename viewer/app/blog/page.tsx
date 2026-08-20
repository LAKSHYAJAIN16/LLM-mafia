import Link from "next/link";
import SiteNav from "../components/SiteNav";
import { POSTS } from "@/lib/blog";

export default function BlogIndexPage() {
  return (
    <div className="wrap">
      <SiteNav />
      <h1>Blog</h1>
      <p className="subtitle">A running log of what&apos;s shipped on MafiaSim, newest first.</p>

      {POSTS.map((post) => (
        <Link key={post.slug} href={`/blog/${post.slug}`} className="blog-row">
          <div className="blog-date">{post.date}</div>
          <h2>{post.title}</h2>
          <p className="blog-summary">{post.summary}</p>
        </Link>
      ))}
    </div>
  );
}
