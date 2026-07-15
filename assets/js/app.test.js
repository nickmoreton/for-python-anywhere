import test from "node:test";
import assert from "node:assert/strict";

import {
  STATUS_MESSAGES,
  nextStatusIndex,
  shouldAnimate,
} from "./app.js";

test("status messages use the approved sequence", () => {
  assert.deepEqual(STATUS_MESSAGES, ["Planning", "Building", "Refining"]);
});

test("nextStatusIndex advances and wraps", () => {
  assert.equal(nextStatusIndex(0), 1);
  assert.equal(nextStatusIndex(1), 2);
  assert.equal(nextStatusIndex(2), 0);
});

test("animation is disabled when reduced motion is preferred", () => {
  assert.equal(shouldAnimate(true), false);
  assert.equal(shouldAnimate(false), true);
});
