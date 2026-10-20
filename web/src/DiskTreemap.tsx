import { useEffect, useMemo, useRef, useState } from "react";
import type { TreeNode } from "./types";
import { computeLayout } from "./treemapLayout";
import { loadChildren } from "./treeLoader";

interface Props {
  data: TreeNode;
  width: number;
  height: number;
  onNodeClick: (
    node: TreeNode,
    ancestors?: TreeNode[],
    point?: { x: number; y: number },
  ) => void;
  onDataChange: () => void;
}
const colors = [
  "#ef4a45",
  "#f29235",
  "#e9c15b",
  "#b5bc28",
  "#cf7378",
  "#d65c30",
  "#deb36b",
  "#b33c49",
];
function color(name: string) {
  const extension = name.includes(".")
    ? name.split(".").pop()!.toLowerCase()
    : "no-extension";
  let hash = 0;
  for (const char of extension) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return colors[Math.abs(hash) % colors.length];
}
export function DiskTreemap({
  data,
  width,
  height,
  onNodeClick,
  onDataChange,
}: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [revision, setRevision] = useState(0);
  const [hovered, setHovered] = useState(-1);
  const [error, setError] = useState("");
  const layout = useMemo(
    () => computeLayout(data, width, height),
    [data, width, height, revision],
  );
  const rectangles = layout.rectangles;
  useEffect(() => {
    let alive = true;
    if (!layout.pending.length) return;
    Promise.all(layout.pending.slice(0, 4).map(loadChildren))
      .then(() => {
        if (alive) {
          setRevision((v) => v + 1);
          onDataChange();
        }
      })
      .catch((cause) => {
        if (alive) setError(String(cause));
      });
    return () => {
      alive = false;
    };
  }, [layout, onDataChange]);

  const base = useMemo(() => {
    const image = document.createElement("canvas");
    const dpr = window.devicePixelRatio || 1;
    image.width = Math.round(width * dpr);
    image.height = Math.round(height * dpr);
    const ctx = image.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#15120e";
    ctx.fillRect(0, 0, width, height);
    for (const rect of rectangles) {
      const w = rect.x1 - rect.x0,
        h = rect.y1 - rect.y0;
      ctx.fillStyle = rect.hasChildren ? "#787267" : color(rect.name);
      ctx.fillRect(rect.x0, rect.y0, w + 0.1, h + 0.1);
      if (w > 5 && h > 5) {
        const shade = ctx.createLinearGradient(
          rect.x0,
          rect.y0,
          rect.x1,
          rect.y1,
        );
        shade.addColorStop(0, "#ffffff55");
        shade.addColorStop(0.4, "#ffffff04");
        shade.addColorStop(1, "#000000a8");
        ctx.fillStyle = shade;
        ctx.fillRect(rect.x0, rect.y0, w, h);
        ctx.strokeStyle = "#00000035";
        ctx.lineWidth = 0.5;
        ctx.strokeRect(rect.x0 + 0.25, rect.y0 + 0.25, w - 0.5, h - 0.5);
      }
    }
    return image;
  }, [rectangles, width, height]);

  const grid = useMemo(() => {
    const cells = new Map<string, number[]>();
    rectangles.forEach((r, index) => {
      for (let x = Math.floor(r.x0 / 48); x <= Math.floor(r.x1 / 48); x++) {
        for (let y = Math.floor(r.y0 / 48); y <= Math.floor(r.y1 / 48); y++) {
          const key = x + ":" + y;
          const cell = cells.get(key) || [];
          cell.push(index);
          cells.set(key, cell);
        }
      }
    });
    return cells;
  }, [rectangles]);
  useEffect(() => {
    const element = canvas.current;
    const ctx = element?.getContext("2d");
    if (!element || !ctx) return;
    element.width = base.width;
    element.height = base.height;
    ctx.drawImage(base, 0, 0);
    const rect = rectangles[hovered];
    if (rect) {
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.strokeRect(
        rect.x0 + 1,
        rect.y0 + 1,
        Math.max(1, rect.x1 - rect.x0 - 2),
        Math.max(1, rect.y1 - rect.y0 - 2),
      );
    }
  }, [base, hovered, rectangles]);
  const at = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) * width) / bounds.width;
    const y = ((event.clientY - bounds.top) * height) / bounds.height;
    const candidates =
      grid.get(Math.floor(x / 48) + ":" + Math.floor(y / 48)) || [];
    for (let i = candidates.length - 1; i >= 0; i--) {
      const r = rectangles[candidates[i]];
      if (x >= r.x0 && x < r.x1 && y >= r.y0 && y < r.y1) return candidates[i];
    }
    return -1;
  };
  return (
    <div className="canvas-host">
      <canvas
        ref={canvas}
        tabIndex={0}
        style={{ width, height }}
        aria-label="Disk treemap. Click a rectangle for details, or press Enter to browse folder contents."
        onMouseMove={(event) => {
          setHovered(at(event));
        }}
        onMouseLeave={() => setHovered(-1)}
        onClick={(event) => {
          const selected = rectangles[at(event)];
          if (selected)
            onNodeClick(selected.node, selected.ancestors, {
              x: event.clientX,
              y: event.clientY,
            });
        }}
      />
      {(error || layout.pending.length > 0) && (
        <div className="load-status" role="status">
          {error || "Loading…"}
        </div>
      )}
    </div>
  );
}
