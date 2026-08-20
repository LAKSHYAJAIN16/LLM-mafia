import Link from "next/link";

export default function SiteNav() {
  return (
    <nav className="site-nav">
      <Link href="/">Games</Link>
      <Link href="/prompts">Prompts</Link>
      <Link href="/blog">Blog</Link>
      <Link href="/home">Home</Link>
    </nav>
  );
}
