import { hierarchy, treemap, treemapSquarify } from "d3-hierarchy";
import type { TreeNode, LayoutRect } from "./types";

export function computeLayout(data: TreeNode, width: number, height: number) {
  const rectangles: LayoutRect[] = [];
  const pending: TreeNode[] = [];
  const visit = (
    node: TreeNode,
    x: number,
    y: number,
    w: number,
    h: number,
    ancestors: TreeNode[],
  ) => {
    const directory =
      node.kind === "directory" || !!node.chunkId || !!node.children;
    const area = w * h;
    if (directory && node.chunkId && !node.children && area >= 1024)
      pending.push(node);
    if (!directory && area < 1) return;
    const rectangle: LayoutRect = {
      x0: x,
      y0: y,
      x1: x + w,
      y1: y + h,
      name: node.name,
      value: node.value,
      parentPath: ancestors.map((n) => n.name).join("/"),
      depth: ancestors.length + 1,
      hasChildren: directory,
      node,
      ancestors,
    };
    // Subpixel branches remain navigable; individual files appear on zoom.
    if (
      directory &&
      node.children?.length &&
      area >= 1 &&
      w >= 0.3 &&
      h >= 0.3
    ) {
      const children = node.children.filter((child) => child.value > 0);
      if (children.length) {
        // A folder backdrop keeps subpixel files selectable as a group.
        rectangles.push(rectangle);
        const root = hierarchy(node, (n) => (n === node ? children : undefined))
          .sum((n) => (n === node ? 0 : n.value))
          .sort((a, b) => (b.value || 0) - (a.value || 0));
        const laid = treemap<TreeNode>()
          .size([w, h])
          .tile(treemapSquarify)
          .round(false)(root);
        const trail = node === data ? ancestors : [...ancestors, node];
        for (const child of laid.children || [])
          visit(
            child.data,
            x + child.x0,
            y + child.y0,
            child.x1 - child.x0,
            child.y1 - child.y0,
            trail,
          );
        return;
      }
    }
    if (area <= 0) return;
    rectangles.push(rectangle);
  };
  visit(data, 0, 0, width, height, []);
  return { rectangles, pending };
}
