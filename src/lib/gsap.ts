/**
 * Single GSAP entry point. Plugins are registered once here so every client
 * component imports the same configured instance.
 *
 * Client-only: ScrollTrigger reads `window` when it initialises. Import from
 * "use client" modules only.
 */
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export { gsap, ScrollTrigger, useGSAP };
