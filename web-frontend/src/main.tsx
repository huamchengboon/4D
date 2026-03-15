import "./index.css";
import "./syncfusion-license";
/* Syncfusion Tailwind 3.4 theme (see appearance/theme + appearance/css-variables docs) */
import "@syncfusion/ej2-base/styles/tailwind3.css";
import "@syncfusion/ej2-buttons/styles/tailwind3.css";
import "@syncfusion/ej2-inputs/styles/tailwind3.css";
import "@syncfusion/ej2-popups/styles/tailwind3.css";
import "@syncfusion/ej2-calendars/styles/tailwind3.css";
import "@syncfusion/ej2-react-calendars/styles/tailwind3.css";
import "@syncfusion/ej2-react-inputs/styles/tailwind3.css";
import "@syncfusion/ej2-react-popups/styles/tailwind3.css";
/* Customize theme via official CSS variables (ej2.syncfusion.com/react/documentation/appearance/css-variables) */
import "./syncfusion-theme-vars.css";
/* Design-system tweaks (radius, font) not covered by theme variables */
import "./syncfusion-overrides.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import { queryClient } from "./lib/queryClient";
import { routeTree } from "./routeTree.gen";

const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
