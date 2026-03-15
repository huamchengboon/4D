import { lazy } from "react";
import { createFileRoute } from "@tanstack/react-router";

const Optimizer = lazy(() =>
  import("@/components/tools/Optimizer").then((m) => ({ default: m.Optimizer }))
);

export const Route = createFileRoute("/tools/optimize")({
  component: Optimizer,
});
