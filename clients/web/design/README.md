# Juris AI design handoff

This directory is the versioned fallback for the **Juris AI — Web v1** Figma
deliverable. It can generate the design document locally and reproduce UI
reference images from the real Next.js application.

## Generate the Figma document

Use Figma Desktop:

1. Create a dedicated empty Figma Design file.
2. Choose **Plugins → Development → Import plugin from manifest…**.
3. Select `design/figma-plugin/manifest.json`.
4. Run **Juris AI Web v1 Generator** from the Development plugins menu.
5. Confirm the file contains the seven pages listed in
   `screen-manifest.json`.

Rerunning is idempotent and destructive within that dedicated file: the plugin
rebuilds generated pages, matching local variable collections, and matching
text styles.

## Import tokens with Tokens Studio

1. Install/open the Tokens Studio plugin in the generated Figma file.
2. In Tokens Studio, choose **Import → JSON**.
3. Select `design/tokens.json`.
4. Enable DTCG (`$type`/`$value`) parsing if prompted.
5. Import as local tokens. Preserve aliases such as
   `{color.primitive.paper.50}` rather than resolving them to duplicate values.

The Figma generator also creates the same primitive, semantic, spacing, and
radius values directly, so Tokens Studio is optional for viewing the file and
useful for token round-tripping.

## Reference renders

Run:

```bash
npm run design:capture
```

The dedicated Playwright configuration uses installed Google Chrome, fixed
1440×900 and 390×844 viewports, deterministic clocks/data, and intercepted BFF
responses. It writes stable PNG files to `design/reference/` and never calls
FastAPI or includes credentials.

`screen-manifest.json` maps routes and states to Figma frame names and reference
filenames. `prototype-connections.json` is the source-of-truth connection list
when a Figma Plugin API version cannot attach a reaction.

## Account-dependent limitations

Without a connected Figma account/API, this repository cannot:

- create or return a Figma cloud file URL;
- publish **Juris AI / Web** as a team library;
- configure organization/team permissions or library analytics.

Those are publishing operations only. The local plugin generates the actual
pages, variables, text styles, components, screens, and supported prototype
reactions when imported into Figma Desktop.
