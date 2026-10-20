export interface TreeNode {
  name: string;
  value: number;
  children?: TreeNode[];
  kind?: "directory" | "file" | "excluded";
  chunkId?: string;
  logicalSize?: number;
  reason?: string;
  partial?: boolean;
  isSymlink?: boolean;
  isHardlink?: boolean;
}
export interface LayoutRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  name: string;
  value: number;
  parentPath: string;
  depth: number;
  hasChildren: boolean;
  node: TreeNode;
  ancestors: TreeNode[];
}
export interface TreeMeta {
  root: string;
  generatedAt: string;
  files: number;
  directories: number;
  unreadable: number;
  excluded: number;
  chunks: number;
  chunkDirectory: string;
  freeBytes: number | null;
  method: string;
  sizeMode?: "allocated" | "logical";
  pathSeparator?: string;
}
declare global {
  interface Window {
    __TREE_DATA__: TreeNode | string;
    __TREE_META__: TreeMeta | string;
    __TREE_CHUNKS__?: Record<string, TreeNode[]>;
  }
}
