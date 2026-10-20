import { useCallback, useEffect, useRef, useState } from "react";
import type { TreeMeta, TreeNode } from "./types";
import { DiskTreemap } from "./DiskTreemap";
import { useResizeObserver } from "./useResizeObserver";
import { loadChildren } from "./treeLoader";
import { demo } from "./demo";
import "./app.css";

const data =
  typeof window.__TREE_DATA__ === "object" ? window.__TREE_DATA__ : demo;
const meta: TreeMeta | null =
  typeof window.__TREE_META__ === "object" ? window.__TREE_META__ : null;
const isDirectory = (node: TreeNode) =>
  node.kind === "directory" || !!node.chunkId || !!node.children;
export function formatSize(bytes: number): string {
  for (const [size, unit] of [
    [1024 ** 4, "TiB"],
    [1024 ** 3, "GiB"],
    [1024 ** 2, "MiB"],
    [1024, "KiB"],
  ] as const) {
    if (bytes >= size)
      return (
        (bytes / size).toLocaleString(undefined, { maximumFractionDigits: 1 }) +
        " " +
        unit
      );
  }
  return bytes + " B";
}
type Selection = {
  node: TreeNode;
  ancestors: TreeNode[];
  x: number;
  y: number;
};

export default function App() {
  const [stack, setStack] = useState<TreeNode[]>([data]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [, setRevision] = useState(0);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(100);
  const onDataChange = useCallback(() => setRevision((v) => v + 1), []);
  const [containerRef, { width, height }] = useResizeObserver();
  const infoRef = useRef<HTMLElement>(null);
  const current = stack[stack.length - 1];
  const separator = meta?.pathSeparator || "/";
  const path = (nodes: TreeNode[]) =>
    nodes.length
      ? data.name.replace(/[\\/]$/, "") +
        separator +
        nodes.map((n) => n.name).join(separator)
      : data.name;
  const currentPath = path(stack.slice(1));
  const back = useCallback(() => {
    setSelection(null);
    setError("");
    setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));
  }, []);
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (selection) setSelection(null);
        else back();
      }
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "Backspace") {
        event.preventDefault();
        back();
      }
      if (
        event.key === "Enter" &&
        !selection &&
        event.target instanceof HTMLCanvasElement
      ) {
        setSelection({ node: current, ancestors: [], x: 20, y: 20 });
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [selection, back, current]);
  useEffect(() => {
    setQuery("");
    setLimit(100);
    if (!selection) return;
    infoRef.current?.focus();
    if (selection.node.chunkId && !selection.node.children) {
      let active = true;
      loadChildren(selection.node)
        .then(() => {
          if (active) onDataChange();
        })
        .catch((cause) => {
          if (active) setError(String(cause));
        });
      return () => {
        active = false;
      };
    }
  }, [selection, onDataChange]);
  const explore = async () => {
    if (!selection || loading) return;
    setLoading(true);
    try {
      if (isDirectory(selection.node)) await loadChildren(selection.node);
      setStack((s) => [
        ...s,
        ...selection.ancestors,
        ...(isDirectory(selection.node) && selection.node !== current
          ? [selection.node]
          : []),
      ]);
      setSelection(null);
      setError("");
    } catch (cause) {
      setError(String(cause));
    } finally {
      setLoading(false);
    }
  };
  const children =
    selection?.node.children?.filter((n) =>
      n.name.toLowerCase().includes(query.toLowerCase()),
    ) || [];
  const directory = selection && isDirectory(selection.node);
  return (
    <main className="disk-map" ref={containerRef}>
      {width > 0 && height > 0 && (
        <DiskTreemap
          key={currentPath}
          data={current}
          width={width}
          height={height}
          onDataChange={onDataChange}
          onNodeClick={(node, ancestors = [], point) => {
            setSelection({
              node,
              ancestors,
              x: point?.x ?? width / 2,
              y: point?.y ?? height / 2,
            });
            setError("");
          }}
        />
      )}
      {stack.length > 1 && (
        <nav className="navigation">
          <button
            className="back-button"
            aria-label="Parent folder"
            title={currentPath}
            onClick={back}
          >
            ←
          </button>
          <button
            className="root-button"
            aria-label="Scan root"
            onClick={() => {
              setStack([data]);
              setSelection(null);
            }}
          >
            ⌂
          </button>
        </nav>
      )}
      {selection && (
        <section
          className="file-info"
          role="dialog"
          tabIndex={-1}
          aria-labelledby="file-name"
          ref={infoRef}
          style={{
            left: Math.max(8, Math.min(selection.x + 12, width - 368)),
            top: Math.max(8, Math.min(selection.y + 12, height - 380)),
          }}
        >
          <button
            className="close-info"
            aria-label="Close details"
            onClick={() => setSelection(null)}
          >
            ×
          </button>
          <small>
            {directory
              ? "Folder"
              : selection.node.kind === "excluded"
                ? "Not scanned"
                : selection.node.isSymlink
                  ? "Symbolic link"
                  : "File"}
          </small>
          <h1 id="file-name">{selection.node.name}</h1>
          <strong className="file-bytes">
            {formatSize(selection.node.value)}
          </strong>
          <p className="file-path">
            {selection.node === current
              ? currentPath
              : path([
                  ...stack.slice(1),
                  ...selection.ancestors,
                  selection.node,
                ])}
          </p>
          {selection.node.logicalSize != null &&
            selection.node.logicalSize !== selection.node.value && (
              <p className="secondary">
                Logical size: {formatSize(selection.node.logicalSize)}
              </p>
            )}
          {selection.node.isHardlink && (
            <p className="secondary">
              Hard link: its bytes are counted under another filename.
            </p>
          )}
          {selection.node.partial && (
            <p className="secondary">
              Some entries were excluded or could not be read.
            </p>
          )}
          {selection.node.reason && (
            <p className="secondary">{selection.node.reason}</p>
          )}
          {((directory && selection.node !== current) ||
            selection.ancestors.length > 0) && (
            <button
              className="explore-button"
              disabled={loading}
              onClick={explore}
            >
              {loading
                ? "Loading…"
                : directory
                  ? "Explore this folder →"
                  : "Zoom to parent folder →"}
            </button>
          )}
          {directory && (
            <details className="folder-contents">
              <summary>
                Folder contents ({selection.node.children?.length ?? "…"})
              </summary>
              <input
                aria-label="Filter folder contents"
                placeholder="Filter filenames…"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setLimit(100);
                }}
              />
              {children.slice(0, limit).map((child, index) => (
                <button
                  className="child-row"
                  key={index}
                  onClick={() =>
                    setSelection({
                      node: child,
                      ancestors: [
                        ...selection.ancestors,
                        ...(selection.node === current ? [] : [selection.node]),
                      ],
                      x: selection.x,
                      y: selection.y,
                    })
                  }
                >
                  <span>{child.name}</span>
                  <span>
                    {child.kind === "excluded" ? "—" : formatSize(child.value)}
                  </span>
                </button>
              ))}
              {children.length > limit && (
                <button
                  className="show-more"
                  onClick={() => setLimit((n) => n + 100)}
                >
                  Show 100 more
                </button>
              )}
            </details>
          )}
          <details>
            <summary>About this report</summary>
            <p>
              {meta
                ? `${meta.files.toLocaleString()} files · ${new Date(meta.generatedAt).toLocaleString()}. ${meta.unreadable} unreadable · ${meta.excluded} excluded.`
                : "Synthetic demonstration. No real filesystem data."}{" "}
              Rectangle area uses {meta?.sizeMode || "allocated"} size. Tiny
              files become visible when you explore their folder. Zero-byte and
              excluded entries are available in folder contents. APFS clones,
              snapshots and shared blocks can make totals differ from your OS
              storage view. This is a static snapshot; nothing is deleted from
              this page.
            </p>
          </details>
          {error && (
            <p className="secondary" role="alert">
              {error}
            </p>
          )}
        </section>
      )}
    </main>
  );
}
