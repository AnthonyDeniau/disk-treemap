import type { TreeNode } from "./types";

// Entirely synthetic. Never replace this with the output of a real disk scan.
let seed = 1097;
function random() {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 2 ** 32;
}
const extensions = ["ts", "png", "mp4", "json", "pdf", "wasm", "bin", "zip"];
function folder(name: string, depth: number): TreeNode {
  const children: TreeNode[] = [];
  for (let i = 0; i < (depth > 0 ? 7 : 25); i++) {
    if (depth > 0 && i < 5)
      children.push(folder("folder-" + (i + 1), depth - 1));
    else {
      const value = Math.round((0.1 + random() ** 4 * 20) * 1024 ** 2);
      children.push({
        name: "sample-" + (i + 1) + "." + extensions[i % extensions.length],
        kind: "file",
        value,
        logicalSize: value,
      });
    }
  }
  return {
    name,
    kind: "directory",
    value: children.reduce((sum, child) => sum + child.value, 0),
    children,
  };
}
export const demo = folder("Example disk (synthetic data)", 3);
