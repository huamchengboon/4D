import { lazy } from "react";
import { createFileRoute } from "@tanstack/react-router";

const GapAnalysis = lazy(() =>
  import("@/components/tools/GapAnalysis").then((m) => ({ default: m.GapAnalysis }))
);

export const Route = createFileRoute("/tools/gap")({
  component: GapAnalysis,
});
