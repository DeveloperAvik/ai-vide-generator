import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Frame } from "../components/Frame";
import { AnimatedArchitecture, AnimatedNetwork, AnimatedProcessFlow, AnimatedTimeline } from "../components/diagrams";
import { SyntaxHighlightedCode } from "../components/code";
import { HighlightedKeywords, KineticTypography, LowerThird, StaggeredText } from "../components/typography";
import { loadFonts } from "../utils/fonts";
import { T } from "../utils/theme";

loadFonts();
/** QA-only composition: renders every library component that no storyboard scene drives yet, so each is exercised by a render test.
 *  Sections are 60 frames long: 0 typography, 1 architecture+network, 2 process+timeline, 3 syntax-highlighted code. */
export const GALLERY_SECTION = 60;
const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => <Frame title={title} footer="gallery">{children}</Frame>;

export const Gallery: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={GALLERY_SECTION}><Section title="Typography">
      <div style={{ position: "absolute", left: T.margin, top: 230, fontSize: 52, fontWeight: 600 }}><StaggeredText text="Words rise in one after another" start={0} stagger={3} /></div>
      <div style={{ position: "absolute", left: T.margin, top: 340, fontSize: 48, maxWidth: 1500 }}><HighlightedKeywords text="Never trust client data; validate on the server." keywords={["client data", "server"]} keywordStarts={[10, 24]} /></div>
      <div style={{ position: "absolute", left: T.margin, top: 450 }}><KineticTypography lines={["Defence in depth", "beats a single wall"]} size={72} start={4} /></div>
      <LowerThird name="Instructor" title="Secure Coding" start={4} hold={40} />
    </Section></Sequence>
    <Sequence from={GALLERY_SECTION} durationInFrames={GALLERY_SECTION}><Section title="Architecture and Network">
      <AnimatedArchitecture tiers={[{ name: "Client", items: ["Browser", "Mobile app"] }, { name: "Edge", items: ["WAF", "Load balancer"] }, { name: "Data", items: ["API", "Database"] }]} />
    </Section></Sequence>
    <Sequence from={GALLERY_SECTION * 2} durationInFrames={GALLERY_SECTION}><Section title="Network">
      <AnimatedNetwork nodes={[{ id: "a", label: "Workstation", kind: "host" }, { id: "b", label: "Web server", kind: "server" }, { id: "c", label: "Attacker", kind: "attacker" }, { id: "d", label: "Cloud API", kind: "cloud" }]}
        links={[{ a: "a", b: "b", label: "443" }, { a: "c", b: "b", label: "probe" }, { a: "b", b: "d" }]} />
    </Section></Sequence>
    <Sequence from={GALLERY_SECTION * 3} durationInFrames={GALLERY_SECTION}><Section title="Process and Timeline">
      <AnimatedProcessFlow steps={["Collect", "Analyse", "Contain", "Recover"]} />
      <div style={{ position: "absolute", inset: 0, top: 220 }}><AnimatedTimeline events={[{ label: "Initial access", time: "09:02" }, { label: "Persistence", time: "09:15" }, { label: "Detection", time: "11:40" }]} /></div>
    </Section></Sequence>
    <Sequence from={GALLERY_SECTION * 4} durationInFrames={GALLERY_SECTION}><Section title="Syntax highlighting">
      <div style={{ position: "absolute", left: T.margin, top: 230 }}><SyntaxHighlightedCode language="python" code={'def check(user):\n    if user.role == "admin":  # privileged\n        return 0x1\n    return 0'} size={40} /></div>
    </Section></Sequence>
  </AbsoluteFill>
);
