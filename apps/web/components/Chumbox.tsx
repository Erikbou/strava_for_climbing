interface ChumAd {
  img: string;
  headline: string;
  src: string;
  href: string;
}

const SPECIFIC_URL = "https://specific.dev/";

const CLIMBING_ADS: ChumAd[] = [
  {
    img: "https://picsum.photos/seed/chum-a/240/180",
    headline: "1 weird trick climbers use to send V12 (gyms hate it)",
    src: "FlashHacks.co",
    href: "#",
  },
  {
    img: "https://picsum.photos/seed/chum-b/240/180",
    headline: "Local belayer's $4 chalk swap shocks pros",
    src: "CragDaily",
    href: "#",
  },
  {
    img: "https://picsum.photos/seed/chum-c/240/180",
    headline: "Doctors stunned: this finger move adds 2 grades overnight",
    src: "TendonTimes",
    href: "#",
  },
  {
    img: "https://picsum.photos/seed/chum-d/240/180",
    headline: "She climbed once a week. What happened next will shock you.",
    src: "BetaBuzz",
    href: "#",
  },
  {
    img: "https://picsum.photos/seed/chum-e/240/180",
    headline: "Top 7 hangboards banned in 3 countries — see #4",
    src: "PumpFeed",
    href: "#",
  },
  {
    img: "https://picsum.photos/seed/chum-f/240/180",
    headline: "This routesetter retired at 29. Here's his secret.",
    src: "SendMoney",
    href: "#",
  },
];

const SPECIFIC_ADS: ChumAd[] = [
  {
    img: "https://picsum.photos/seed/specific-a/240/180",
    headline: "1 weird trick devs use to ship infra in minutes (AWS hates it)",
    src: "specific.dev",
    href: SPECIFIC_URL,
  },
  {
    img: "https://picsum.photos/seed/specific-b/240/180",
    headline: "This founder replaced his DevOps team with one .hcl file",
    src: "specific.dev",
    href: SPECIFIC_URL,
  },
  {
    img: "https://picsum.photos/seed/specific-c/240/180",
    headline: "Doctors stunned: `specific dev` boots a full stack overnight",
    src: "specific.dev",
    href: SPECIFIC_URL,
  },
  {
    img: "https://picsum.photos/seed/specific-d/240/180",
    headline: "She wrote Terraform once. What happened next will shock you.",
    src: "specific.dev",
    href: SPECIFIC_URL,
  },
  {
    img: "https://picsum.photos/seed/specific-e/240/180",
    headline: "Top 7 IaC tools banned in 3 countries — see #4 (it's Specific)",
    src: "specific.dev",
    href: SPECIFIC_URL,
  },
  {
    img: "https://picsum.photos/seed/specific-f/240/180",
    headline: "Local SRE retired at 29 after running `specific check`",
    src: "specific.dev",
    href: SPECIFIC_URL,
  },
];

function ChumSlide({ ad, delayMs }: { ad: ChumAd; delayMs: number }) {
  const external = ad.href.startsWith("http");
  return (
    <a
      className="chum-slide"
      href={ad.href}
      target={external ? "_blank" : undefined}
      rel="noopener sponsored"
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <div
        className="chum-img"
        style={{ backgroundImage: `url('${ad.img}')` }}
      />
      <div className="chum-headline">{ad.headline}</div>
      <div className="chum-src">{ad.src} · Sponsored</div>
    </a>
  );
}

export function Chumbox({ slot = 0 }: { slot?: number }) {
  const tiles = Array.from({ length: 4 }, (_, k) => {
    const climb = CLIMBING_ADS[(slot * 4 + k) % CLIMBING_ADS.length];
    const spec = SPECIFIC_ADS[(slot * 4 + k) % SPECIFIC_ADS.length];
    const [front, back] = k % 2 === 0 ? [climb, spec] : [spec, climb];
    const stagger = k * 700;
    return (
      <div className="chum-tile" key={k}>
        <ChumSlide ad={front} delayMs={stagger} />
        <ChumSlide ad={back} delayMs={stagger - 4000} />
      </div>
    );
  });

  return (
    <div className="chum-card" role="complementary" aria-label="Sponsored content">
      <div className="chum-label">Promoted Stories · Ads by Specific</div>
      <div className="chum-grid">{tiles}</div>
      <div className="chum-disclaimer">
        Sponsored by{" "}
        <a
          href={SPECIFIC_URL}
          target="_blank"
          rel="noopener sponsored"
          style={{ color: "#0033aa", textDecoration: "underline" }}
        >
          specific.dev
        </a>
      </div>
    </div>
  );
}
