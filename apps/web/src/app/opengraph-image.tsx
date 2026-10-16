import { ImageResponse } from "next/og";
import { SITE } from "@/lib/marketing";

export const alt = `${SITE.name}: ${SITE.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          color: "white",
          backgroundColor: "#06071a",
          backgroundImage:
            "radial-gradient(circle at 18% 25%, rgba(91,75,255,0.75), transparent 45%), radial-gradient(circle at 85% 15%, rgba(61,220,245,0.4), transparent 40%), radial-gradient(circle at 70% 85%, rgba(244,114,182,0.45), transparent 45%)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 36, fontWeight: 700 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "linear-gradient(135deg, #5b4bff, #b2369f)",
            }}
          />
          {SITE.name}
        </div>
        <div style={{ display: "flex", flexDirection: "column", fontSize: 76, fontWeight: 800, marginTop: 36, lineHeight: 1.05 }}>
          <span>Book more meetings.</span>
          <span style={{ color: "#cfe9ff" }}>Keep your domain clean.</span>
        </div>
        <div style={{ fontSize: 30, marginTop: 32, color: "#c9cdea" }}>{SITE.tagline}</div>
      </div>
    ),
    size,
  );
}
