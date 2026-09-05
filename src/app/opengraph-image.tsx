import { ImageResponse } from "next/og";
import { cinematic } from "@/content/cinematic";
import { profile } from "@/content/profile";

// Static export: rendered once at build into /opengraph-image.png.
export const dynamic = "force-static";

export const alt = `${profile.name} — ${profile.title}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * The share card. Same register as the site: black ground, tracked mono
 * label, the name large and light, one bone-coloured rule.
 */
export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: "#000000",
          color: "#eaeef4",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 22,
            letterSpacing: "0.28em",
            textTransform: "uppercase",
            color: "#8a8f98",
          }}
        >
          {profile.title} · {profile.location}
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              fontSize: 132,
              fontWeight: 300,
              letterSpacing: "-0.04em",
              lineHeight: 0.95,
              textTransform: "uppercase",
            }}
          >
            {cinematic.hero.name}
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 40,
              width: 160,
              height: 3,
              background: "#d8cfc0",
            }}
          />
          <div
            style={{
              display: "flex",
              marginTop: 32,
              fontSize: 30,
              color: "#8a8f98",
              maxWidth: 900,
              lineHeight: 1.35,
            }}
          >
            {profile.tagline}
          </div>
        </div>
      </div>
    ),
    size,
  );
}
