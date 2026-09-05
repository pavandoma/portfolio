"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import type { FrameRenderer } from "@/lib/orbit";
import { subscribeTheme } from "@/lib/theme-store";

/**
 * Where frames come from.
 *
 * `images` is the Apple pattern: a folder of photographed or rendered stills,
 * decoded up front and drawn by index. `procedural` draws each frame from a
 * pure function of progress. Both are scrubbed identically — swapping the
 * orbit for real product photography later is a one-line change here.
 */
export type FrameSource =
  | { kind: "images"; urls: string[] }
  | { kind: "procedural"; render: FrameRenderer };

export type FrameSequenceHandle = {
  /** 0–1. Idempotent: drawing the same progress twice is a no-op. */
  setProgress: (progress: number) => void;
};

/**
 * A full-bleed canvas that shows one frame for a given scroll progress.
 *
 * It never animates on its own. Whatever owns the scroll (a pinned
 * ScrollTrigger) pushes progress in; this only draws when that value changes,
 * so an idle page costs nothing.
 */
export const FrameSequence = forwardRef<
  FrameSequenceHandle,
  { source: FrameSource; className?: string }
>(function FrameSequence({ source, className }, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<HTMLImageElement[]>([]);
  const progressRef = useRef(0);
  const lastDrawnRef = useRef(-1);
  const sizeRef = useRef({ width: 0, height: 0, dpr: 1 });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const { width, height, dpr } = sizeRef.current;
    if (width === 0 || height === 0) return;

    const progress = progressRef.current;

    if (source.kind === "procedural") {
      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      source.render(ctx, progress, width, height);
      ctx.restore();
      lastDrawnRef.current = progress;
      return;
    }

    const frames = imagesRef.current;
    if (frames.length === 0) return;
    const index = Math.min(
      frames.length - 1,
      Math.max(0, Math.round(progress * (frames.length - 1))),
    );
    if (index === lastDrawnRef.current) return;

    const image = frames[index];
    if (!image?.complete || image.naturalWidth === 0) return;

    // Cover-fit, like `object-fit: cover`.
    const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
    const drawWidth = image.naturalWidth * scale;
    const drawHeight = image.naturalHeight * scale;
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(
      image,
      (width - drawWidth) / 2,
      (height - drawHeight) / 2,
      drawWidth,
      drawHeight,
    );
    ctx.restore();
    lastDrawnRef.current = index;
  }, [source]);

  useImperativeHandle(
    ref,
    () => ({
      setProgress: (progress) => {
        const clamped = Math.min(1, Math.max(0, progress));
        if (clamped === progressRef.current && lastDrawnRef.current !== -1) return;
        progressRef.current = clamped;
        draw();
      },
    }),
    [draw],
  );

  // Size to the element's box at device resolution; redraw on resize.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      sizeRef.current = { width: rect.width, height: rect.height, dpr };
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      lastDrawnRef.current = -1;
      draw();
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [draw]);

  // A theme change swaps the palette the renderer reads; the current frame
  // has to be drawn again or the old colours sit there until the next scroll.
  useEffect(
    () =>
      subscribeTheme(() => {
        lastDrawnRef.current = -1;
        draw();
      }),
    [draw],
  );

  // Decode image frames up front so scrubbing never waits on the network.
  useEffect(() => {
    if (source.kind !== "images") return;
    let cancelled = false;
    const loaded: HTMLImageElement[] = source.urls.map((url) => {
      const image = new Image();
      image.decoding = "async";
      image.src = url;
      return image;
    });
    Promise.allSettled(loaded.map((image) => image.decode())).then(() => {
      if (cancelled) return;
      imagesRef.current = loaded;
      lastDrawnRef.current = -1;
      draw();
    });
    return () => {
      cancelled = true;
    };
  }, [source, draw]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
});
