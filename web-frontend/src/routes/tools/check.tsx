import { lazy } from "react";
import { createFileRoute } from "@tanstack/react-router";

const NumberChecker = lazy(() =>
  import("@/components/tools/NumberChecker").then((m) => ({ default: m.NumberChecker }))
);

export const Route = createFileRoute("/tools/check")({
  component: NumberChecker,
});
