import type { TreeNode } from "./types";

const pending = new Map<string, Promise<void>>();
export function loadChildren(node: TreeNode): Promise<void> {
  if (!node.chunkId || node.children) return Promise.resolve();
  const id = node.chunkId;
  const meta = window.__TREE_META__;
  if (
    !/^c\d{7,}$/.test(id) ||
    typeof meta !== "object" ||
    !/^disk-treemap-data-[a-f0-9]{12}$/.test(meta.chunkDirectory)
  )
    return Promise.reject(new Error("Invalid report data reference"));
  const existing = pending.get(id);
  if (existing) return existing;
  const promise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "./" + meta.chunkDirectory + "/" + id + ".js";
    script.onload = () => {
      const children = window.__TREE_CHUNKS__?.[id];
      if (!children) {
        script.remove();
        reject(new Error("Missing data block: " + id));
        return;
      }
      node.children = children;
      delete window.__TREE_CHUNKS__?.[id];
      script.remove();
      resolve();
    };
    script.onerror = () => {
      script.remove();
      reject(
        new Error(
          "Cannot load " +
            id +
            ".js. Keep the HTML and its data folder together.",
        ),
      );
    };
    document.head.appendChild(script);
  });
  pending.set(id, promise);
  promise.catch(() => pending.delete(id));
  return promise;
}
