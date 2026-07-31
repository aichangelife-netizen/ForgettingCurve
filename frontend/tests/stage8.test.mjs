import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import ts from "typescript";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function source(path) {
  return readFileSync(resolve(root, path), "utf8");
}

function loadTsModule(path, sandboxExtras = {}) {
  const fileSource = source(path);
  const transpiled = ts.transpileModule(fileSource, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const sandbox = {
    exports: {},
    module: { exports: {} },
    require(name) {
      throw new Error(`Unexpected require: ${name}`);
    },
    process: { env: {} },
    ...sandboxExtras,
  };
  sandbox.exports = sandbox.module.exports;
  vm.runInNewContext(transpiled, sandbox, { filename: path });
  return sandbox.module.exports;
}

test("participant session save, read, clear, and corruption handling", () => {
  const store = new Map();
  const sessionModule = loadTsModule("lib/participant-session.ts", {
    window: {
      localStorage: {
        getItem: (key) => store.get(key) ?? null,
        setItem: (key, value) => store.set(key, value),
        removeItem: (key) => store.delete(key),
      },
    },
  });
  sessionModule.saveParticipantSession({ participantId: 7, participantCode: "P-ABC12345" });
  assert.equal(JSON.stringify(sessionModule.readParticipantSession()), JSON.stringify({ participantId: 7, participantCode: "P-ABC12345" }));
  sessionModule.clearParticipantSession();
  assert.equal(sessionModule.readParticipantSession(), null);
  store.set(sessionModule.participantSessionStorageKey, "{broken");
  assert.equal(sessionModule.readParticipantSession(), null);
  assert.equal(store.has(sessionModule.participantSessionStorageKey), false);
});

test("API error parsing maps backend errors and network failures", async () => {
  const apiModule = loadTsModule("lib/api/client.ts", {
    Response,
    Headers,
    DOMException,
    fetch: async () =>
      new Response(JSON.stringify({ detail: { code: "unfinished_design_exists", message: "Already active." } }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
  });
  await assert.rejects(() => apiModule.apiRequest("/api/test-designs"), {
    name: "ApiError",
    kind: "conflict",
    code: "unfinished_design_exists",
  });

  const networkModule = loadTsModule("lib/api/client.ts", {
    Response,
    Headers,
    DOMException,
    fetch: async () => {
      throw new Error("offline");
    },
  });
  await assert.rejects(() => networkModule.apiRequest("/api/test-designs"), {
    name: "ApiError",
    kind: "network",
  });
});

test("interval formatting covers seconds, minutes, hours, days, percentages, and countdown", () => {
  const timeModule = loadTsModule("lib/time-format.ts");
  assert.equal(timeModule.formatDuration(60), "1 minute");
  assert.equal(timeModule.formatDuration(3600), "1 hour");
  assert.equal(timeModule.formatDuration(21600), "6 hours");
  assert.equal(timeModule.formatDuration(86400), "1 day");
  assert.equal(timeModule.formatDuration(604800), "7 days");
  assert.equal(timeModule.formatDuration(95), "1.6 minutes");
  assert.equal(timeModule.formatPercentage(0.66), "66%");
  assert.equal(timeModule.formatCountdown("2026-01-01T00:01:00Z", new Date("2026-01-01T00:00:00Z")), "1 minute remaining");
});

test("UTC timestamps render in browser-local time with timezone details", () => {
  const timeModule = loadTsModule("lib/time-format.ts");
  const withSuffix = timeModule.parseUtcTimestamp("2026-07-30T23:31:47Z");
  const withoutSuffix = timeModule.parseUtcTimestamp("2026-07-30T23:31:47");
  const rendered = timeModule.formatDateTime("2026-07-30T23:31:47Z", {
    locale: "en-CA",
    timeZone: "Asia/Tokyo",
  });

  assert.equal(withSuffix.toISOString(), "2026-07-30T23:31:47.000Z");
  assert.equal(withoutSuffix.toISOString(), "2026-07-30T23:31:47.000Z");
  assert.match(rendered, /^2026-07-31 08:31:47/);
  assert.match(rendered, /(GMT\+9|UTC\+9|JST)/);
  assert.equal(
    timeModule.formatCountdown("2026-07-30T23:31:47", new Date("2026-07-30T23:30:47Z")),
    "1 minute remaining",
  );
  assert.equal(timeModule.formatCountdown("2026-07-30T23:31:47Z", new Date("2026-07-30T23:31:47Z")), "Due now");
});

test("design validation calculates required items and rejects duplicates", () => {
  const validationModule = loadTsModule("lib/design-validation.ts");
  const valid = validationModule.validateDesignInput(3, "60, 180, 300");
  assert.equal(valid.valid, true);
  assert.equal(valid.groupCount, 3);
  assert.equal(valid.requiredItemCount, 9);
  const duplicate = validationModule.validateDesignInput(3, "60, 60");
  assert.equal(duplicate.valid, false);
  assert.match(duplicate.errors.join(" "), /duplicates/);
});

test("learning page does not expose answer before submission and shows feedback after submission", () => {
  const page = source("app/experiment/[testDesignId]/learn/page.tsx");
  const checkSection = page.slice(page.indexOf("<h2>Learning Check</h2>"), page.indexOf("{feedback ?"));
  assert.doesNotMatch(checkSection, /canonical_answer|english_answer/);
  assert.match(page, /Canonical English answer/);
  assert.match(page, /feedback\.canonical_answer/);
});

test("delayed page never reveals correctness or canonical answers and prevents double submission", () => {
  const page = source("app/experiment/[testDesignId]/delayed/page.tsx");
  assert.doesNotMatch(page, /canonical_answer|english_answer|is_correct|Incorrect/);
  assert.match(page, /disabled=\{submitting\}/);
  assert.match(page, /Response recorded\./);
});

test("no-due delayed state displays next scheduled time", () => {
  const page = source("app/experiment/[testDesignId]/delayed/page.tsx");
  assert.match(page, /No test is due right now\./);
  assert.match(page, /formatDateTime\(next\?\.next_scheduled_at/);
  assert.match(page, /formatCountdown\(next\?\.next_scheduled_at/);
});

test("results page displays insufficient-data message below five time points", () => {
  const page = source("app/experiment/[testDesignId]/results/page.tsx");
  assert.match(page, /summary\.complete_time_point_count < 5/);
  assert.match(page, /Insufficient data for an official personal curve/);
  assert.match(page, /Five complete time points are required/);
});

test("results page enables curve generation only when eligible and not existing", () => {
  const page = source("app/experiment/[testDesignId]/results/page.tsx");
  assert.match(page, /eligibility\.eligible && !eligibility\.has_existing_curve/);
  assert.match(page, /Generate Personal Curve/);
  assert.match(page, /disabled=\{submitting\}/);
});

test("curve component renders observed markers, predicted line, empty state, and log positioning", () => {
  const component = source("components/curve/CurveChart.tsx");
  assert.match(component, /className="observed-point"/);
  assert.match(component, /className="curve-line"/);
  assert.match(component, /No curve data is available yet/);
  assert.match(component, /Math\.log10/);
  assert.match(component, /timeSeconds <= 0/);
  assert.match(component, /tabIndex=\{0\}/);
  assert.match(component, /Observed Point Details|Observed retention/);
});

test("curve history selection requests the selected version", () => {
  const page = source("app/experiment/[testDesignId]/results/page.tsx");
  assert.match(page, /getCurveModelVersion\(session\.participantId, version\)/);
  assert.match(page, /onChange=\{\(event\) => void selectVersion\(Number\(event\.target\.value\)\)\}/);
});

test("loading and expected error states are rendered", () => {
  const dashboard = source("app/experiment/page.tsx");
  const panels = source("components/ui/StatusPanels.tsx");
  assert.match(dashboard, /Loading participant state/);
  assert.match(dashboard, /current_test_design_not_found/);
  assert.match(dashboard, /participant_not_found/);
  assert.match(panels, /role="alert"/);
});
