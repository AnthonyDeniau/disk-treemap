import test from "node:test";
import assert from "node:assert/strict";
import { computeLayout } from "../src/treemapLayout.ts";

const file = (name, value) => ({ name, value, kind: "file" });
const folder = (name, children) => ({
  name,
  kind: "directory",
  children,
  value: children.reduce((sum, child) => sum + child.value, 0),
});

test("individual files fill the surface and retain their ancestor paths", () => {
  const data = folder("/", [
    folder("nested", [
      folder("deeper", [file("a.bin", 20), file("b.bin", 30)]),
    ]),
    file("c.bin", 50),
  ]);
  const { rectangles } = computeLayout(data, 1200, 700);
  const leaves = rectangles.filter((r) => !r.hasChildren);
  assert.equal(leaves.length, 3);
  assert.ok(
    Math.abs(
      leaves.reduce((sum, r) => sum + (r.x1 - r.x0) * (r.y1 - r.y0), 0) -
        840000,
    ) < 0.001,
  );
  assert.deepEqual(
    leaves.find((r) => r.name === "a.bin").ancestors.map((n) => n.name),
    ["nested", "deeper"],
  );
});

test("unloaded branches request data only when large enough to show", () => {
  const lazy = {
    name: "lazy",
    kind: "directory",
    value: 1,
    chunkId: "c0000001",
  };
  assert.equal(computeLayout(lazy, 100, 100).pending[0], lazy);
  assert.equal(computeLayout(lazy, 2, 2).pending.length, 0);
});

test("zero-size entries stay in the data and do not create invalid rectangles", () => {
  const data = folder("/", [file("empty", 0), file("nonempty", 10)]);
  const { rectangles } = computeLayout(data, 100, 100);
  assert.equal(data.children.length, 2);
  assert.ok(
    rectangles.every((r) => [r.x0, r.x1, r.y0, r.y1].every(Number.isFinite)),
  );
  assert.ok(!rectangles.some((r) => r.name === "empty"));
});

test("an empty or zero-width view is well-defined", () => {
  assert.equal(computeLayout(folder("/", []), 0, 100).rectangles.length, 0);
  assert.equal(computeLayout(folder("/", []), 100, 100).rectangles.length, 1);
});

test("many subpixel files retain a folder backdrop for zooming", () => {
  const data = folder(
    "/",
    Array.from({ length: 10000 }, (_, i) => file("f" + i, 1)),
  );
  const result = computeLayout(data, 10, 10);
  assert.equal(result.rectangles.length, 1);
  assert.equal(result.rectangles[0].node, data);
});
