import { registerLicense } from "@syncfusion/ej2-base";

/**
 * Syncfusion license must be registered before any Syncfusion component loads.
 * Fallback key is the same one from this repo's git history (web/templates, commit 3e9445c).
 * Override with VITE_SYNCFUSION_LICENSE in .env if needed; key must match your Syncfusion account and package version.
 */
const licenseKey =
  import.meta.env.VITE_SYNCFUSION_LICENSE ??
  "Ngo9BigBOggjHTQxAR8/V1JGaF5cXGpCf1FpRmJGdld5fUVHYVZUTXxaS00DNHVRdkdlWXxfdHVWRWdfVEN2XERWYEs=";

registerLicense(licenseKey);

