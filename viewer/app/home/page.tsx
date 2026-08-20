import type { Metadata } from "next";
import { Bungee, Space_Mono } from "next/font/google";
import Link from "next/link";
import styles from "./home.module.css";

const marquee = Bungee({ weight: "400", subsets: ["latin"], variable: "--font-marquee" });
const ledger = Space_Mono({ weight: ["400", "700"], subsets: ["latin"], variable: "--font-ledger" });

export const metadata: Metadata = {
  title: "MafiaSim",
  description: "Rival AI companies' models sit at one table, lie to each other, and vote each other out.",
};

const TICKER_ITEMS = [
  "NOW SEATING",
  "14 MODELS",
  "11 HOUSES",
  "VOTES ARE SEALED",
  "NO ONE KNOWS WHO'S LYING",
];

const CARD_HAND: { suit: string; rank: string; red: boolean; faceUp: boolean }[] = [
  { suit: "♠", rank: "A", red: false, faceUp: false },
  { suit: "♥", rank: "K", red: true, faceUp: false },
  { suit: "♣", rank: "7", red: false, faceUp: true },
  { suit: "♦", rank: "Q", red: true, faceUp: false },
  { suit: "♠", rank: "9", red: false, faceUp: false },
];

export default function HomePage() {
  return (
    <div className={`${styles.page} ${marquee.variable} ${ledger.variable}`}>
      <div
        dangerouslySetInnerHTML={{
          __html: `<!--
THESIS: A neon speakeasy-casino front door for an AI-vs-AI Mafia benchmark, refusing the sterile "AI product landing page" template for a real underground room.
OWN-WORLD: Near-black + felt-green grounds, hot-pink/amber neon tube linework, gold-foil numerals, suit-glyph card motifs, a mob-marquee display face over a dealer's-ledger mono.
STORY: A visitor understands instantly this is a real running experiment where rival AI companies' models secretly lie to and vote each other out, and can step into a real replay.
FIRST VIEWPORT: Full-bleed neon MAFIA / SIM marquee over a felt-green haze, a dealt hand of cards below it, tagline stating the mechanism, one lit chip-styled CTA.
FORM: "Neon Underground" -- the pick card (top-ranked grounded candidate); assigned index 7 was "The Evidence Room" (case-file/ledger world); user chose the pick. Seed key 8f3a0ca1.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
-->`,
        }}
      />

      {/* ---------- TICKER ---------- */}
      <div className={styles.ticker} aria-hidden="true">
        <div className={styles.tickerTrack}>
          {Array.from({ length: 2 }).map((_, rep) => (
            <div className={styles.tickerRun} key={rep}>
              {TICKER_ITEMS.map((item, i) => (
                <span className={styles.tickerItem} key={`${rep}-${i}`}>
                  {item}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ---------- HERO ---------- */}
      <section className={styles.hero}>
        <div className={styles.feltHaze} aria-hidden="true" />
        <div className={styles.smokeLayer} aria-hidden="true" />

        <h1 className={styles.marqueeWord}>
          <span className={styles.marqueeLetter} data-letter>MAFIA</span>
          <span className={`${styles.marqueeLetter} ${styles.marqueeAccent}`} data-letter>SIM</span>
        </h1>

        <p className={styles.tagline}>
          Fourteen models. Eleven companies. One table.
          <br />
          <span className={styles.taglineEm}>Nobody knows who&rsquo;s lying.</span>
        </p>

        <div className={styles.hand} role="img" aria-label="A dealt hand of five playing cards, one face up showing the seven of clubs">
          {CARD_HAND.map((c, i) => (
            <div
              key={i}
              className={`${styles.card} ${c.faceUp ? styles.cardUp : styles.cardDown}`}
              style={{ "--i": i } as React.CSSProperties}
            >
              {c.faceUp ? (
                <span className={`${styles.cardFace} ${c.red ? styles.red : ""}`}>
                  <span className={styles.cardRank}>{c.rank}</span>
                  <span className={styles.cardSuitBig}>{c.suit}</span>
                </span>
              ) : (
                <span className={styles.cardBack} aria-hidden="true" />
              )}
            </div>
          ))}
        </div>

        <Link href="/" className={styles.chipButton}>
          <span className={styles.chipRing} aria-hidden="true" />
          {/* TODO: this should trigger a real game launch (server-side `python -m mafia_sim run`);
              deliberately still just a link to the games list until that's built as its own piece of work. */}
          <span className={styles.chipLabel}>Start a Game</span>
        </Link>
      </section>

      {/* ---------- FOOTER ---------- */}
      <footer className={styles.footer}>
        <p className={styles.footerLine}>The house always logs everything.</p>
        <Link href="/" className={styles.footerLink}>
          Browse every game played &rarr;
        </Link>
      </footer>
    </div>
  );
}
