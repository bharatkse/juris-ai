# Juris AI Web v1 local generator

This development plugin creates the complete **Juris AI — Web v1** design
document without network access or a Figma API token.

## Run in Figma Desktop

1. Create a new, empty Figma Design file.
2. Open **Plugins → Development → Import plugin from manifest…**.
3. Select `clients/web/design/figma-plugin/manifest.json`.
4. Run **Plugins → Development → Juris AI Web v1 Generator**.
5. Wait for the success notification; the plugin returns to `00 Cover`.

The generator intentionally rebuilds the document and leaves exactly seven
specified pages. Run it in a dedicated file: rerunning clears generated page
content, variables, and matching text styles before rebuilding.

The plugin first tries Inter and Source Serif 4. It falls back to Geist/Roboto
for UI text and Fraunces/Georgia/Roboto for answer text when fonts are not
installed. The `Body Serif` style description records the fallback.

## Output and safety

- All frames and components created by layout helpers use Auto Layout.
- Desktop screens are 1440×900; mobile screens are 390×844.
- Supported prototype reactions are attached to named hotspots. The complete
  annotated map is still generated if the installed Figma API rejects a
  reaction shape.
- Errors are caught, logged in the plugin console, and shown in a Figma
  notification.
- The plugin does not upload, publish, or contact any service.
