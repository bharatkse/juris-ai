/* Juris AI Web v1 — deterministic local Figma generator. No network access. */
"use strict";

(async function generateJurisDesignFile() {
  const FILE_NAME = "Juris AI — Web v1";
  const PAGE_NAMES = [
    "00 Cover",
    "01 Foundation",
    "02 Components",
    "03 Screens / Desktop",
    "04 Screens / Mobile",
    "05 Prototype",
    "06 Do not design",
  ];
  const C = {
    ink950: "#0F1C2E",
    ink800: "#1A2B44",
    ink600: "#3D4F66",
    ink400: "#7A8BA1",
    paper50: "#F7F4EE",
    paper0: "#FFFCF7",
    line200: "#E4DDD0",
    gold600: "#B8860B",
    gold100: "#F4E8C4",
    danger600: "#9B2C2C",
    danger50: "#FDECEC",
    success600: "#276749",
    success50: "#E6F4EA",
    info600: "#2B4C7E",
    grey: "#A8ADB4",
    greyDark: "#5E6670",
  };
  const DISCLAIMER =
    "Juris AI provides legal information, not legal advice, and does not create an attorney–client relationship.";
  const fonts = {};

  function rgb(hex) {
    const value = hex.replace("#", "");
    return {
      r: parseInt(value.slice(0, 2), 16) / 255,
      g: parseInt(value.slice(2, 4), 16) / 255,
      b: parseInt(value.slice(4, 6), 16) / 255,
    };
  }

  /** @returns {SolidPaint} */
  function solid(hex, opacity) {
    return {
      type: "SOLID",
      color: rgb(hex),
      opacity: opacity === undefined ? 1 : opacity,
    };
  }

  async function loadFirst(candidates) {
    for (const candidate of candidates) {
      try {
        await figma.loadFontAsync(candidate);
        return candidate;
      } catch {
        // Continue to a bundled Figma font.
      }
    }
    throw new Error("No compatible local font was available in Figma.");
  }

  async function loadFonts() {
    fonts.regular = await loadFirst([
      { family: "Inter", style: "Regular" },
      { family: "Geist", style: "Regular" },
      { family: "Roboto", style: "Regular" },
    ]);
    fonts.medium = await loadFirst([
      { family: "Inter", style: "Medium" },
      { family: "Geist", style: "Medium" },
      { family: "Roboto", style: "Medium" },
      fonts.regular,
    ]);
    fonts.semibold = await loadFirst([
      { family: "Inter", style: "Semi Bold" },
      { family: "Geist", style: "SemiBold" },
      { family: "Roboto", style: "Bold" },
      fonts.medium,
    ]);
    fonts.serif = await loadFirst([
      { family: "Source Serif 4", style: "Regular" },
      { family: "Fraunces", style: "Regular" },
      { family: "Georgia", style: "Regular" },
      fonts.regular,
    ]);
  }

  const TYPE = {
    Display: { font: "medium", size: 28, line: 36 },
    H1: { font: "semibold", size: 22, line: 28 },
    H2: { font: "semibold", size: 16, line: 24 },
    Body: { font: "regular", size: 14, line: 22 },
    "Body Serif": { font: "serif", size: 16, line: 26 },
    Caption: { font: "regular", size: 12, line: 16 },
    Label: {
      font: "medium",
      size: 12,
      line: 16,
      tracking: 4,
      textCase: "UPPER",
    },
  };

  function text(value, styleName, color, options) {
    const optionsValue = options || {};
    const spec = TYPE[styleName || "Body"] || TYPE.Body;
    const node = figma.createText();
    node.name = optionsValue.name || "Text";
    node.fontName = fonts[spec.font];
    node.fontSize = spec.size;
    node.lineHeight = { unit: "PIXELS", value: spec.line };
    node.letterSpacing = {
      unit: "PERCENT",
      value: spec.tracking || 0,
    };
    if (spec.textCase) node.textCase = spec.textCase;
    node.characters = value;
    node.fills = [solid(color || C.ink950)];
    node.textAlignHorizontal = optionsValue.align || "LEFT";
    node.autoRename = false;
    node.textAutoResize = "WIDTH_AND_HEIGHT";
    if (optionsValue.width) {
      node.textAutoResize = "HEIGHT";
      node.resize(optionsValue.width, Math.max(spec.line, node.height));
    }
    if (optionsValue.opacity !== undefined) {
      node.opacity = optionsValue.opacity;
    }
    return node;
  }

  function autoFrame(name, options) {
    const value = options || {};
    const node = value.component
      ? figma.createComponent()
      : figma.createFrame();
    node.name = name;
    node.layoutMode = value.direction === "HORIZONTAL" ? "HORIZONTAL" : "VERTICAL";
    node.primaryAxisSizingMode = "AUTO";
    node.counterAxisSizingMode = "AUTO";
    node.primaryAxisAlignItems = value.primary || "MIN";
    node.counterAxisAlignItems = value.counter || "MIN";
    node.itemSpacing = value.gap === undefined ? 8 : value.gap;
    const padding = value.padding === undefined ? 0 : value.padding;
    node.paddingTop = value.paddingTop === undefined ? padding : value.paddingTop;
    node.paddingRight =
      value.paddingRight === undefined ? padding : value.paddingRight;
    node.paddingBottom =
      value.paddingBottom === undefined ? padding : value.paddingBottom;
    node.paddingLeft =
      value.paddingLeft === undefined ? padding : value.paddingLeft;
    node.fills =
      value.fill === null
        ? []
        : [solid(value.fill || C.paper0, value.fillOpacity)];
    node.strokes = value.stroke ? [solid(value.stroke)] : [];
    node.strokeWeight = value.stroke ? value.strokeWeight || 1 : 0;
    node.cornerRadius = value.radius || 0;
    node.clipsContent = Boolean(value.clip);
    if (value.wrap) {
      node.layoutWrap = "WRAP";
      node.counterAxisSpacing = value.counterGap || node.itemSpacing;
    }
    if (value.width || value.height) {
      node.resize(value.width || node.width, value.height || node.height);
      if (value.width) node.counterAxisSizingMode = "FIXED";
      if (value.height) node.primaryAxisSizingMode = "FIXED";
    }
    return node;
  }

  function append(parent, children) {
    for (const child of Array.isArray(children) ? children : [children]) {
      if (child) parent.appendChild(child);
    }
    return parent;
  }

  function spacer(grow) {
    const node = autoFrame("Spacer", {
      width: 1,
      height: 1,
      fill: null,
    });
    node.layoutGrow = grow === undefined ? 1 : grow;
    return node;
  }

  function divider(width) {
    const node = figma.createRectangle();
    node.name = "Divider";
    node.resize(width || 240, 1);
    node.fills = [solid(C.line200)];
    return node;
  }

  function pill(label, fill, foreground) {
    const node = autoFrame("Pill / " + label, {
      direction: "HORIZONTAL",
      paddingTop: 4,
      paddingBottom: 4,
      paddingLeft: 8,
      paddingRight: 8,
      gap: 4,
      fill: fill || C.gold100,
      radius: 999,
      counter: "CENTER",
    });
    append(node, text(label, "Caption", foreground || C.ink950));
    return node;
  }

  function iconLabel(icon, label, color) {
    const node = autoFrame("Icon label / " + label, {
      direction: "HORIZONTAL",
      gap: 8,
      fill: null,
      counter: "CENTER",
    });
    append(node, [
      text(icon, "Body", color || C.ink600),
      text(label, "Body", color || C.ink950),
    ]);
    return node;
  }

  function logo(inverse, component) {
    const node = autoFrame("Logo", {
      component: Boolean(component),
      direction: "HORIZONTAL",
      gap: 10,
      fill: null,
      counter: "CENTER",
    });
    const mark = autoFrame("Scale and balance mark", {
      direction: "HORIZONTAL",
      width: 28,
      height: 28,
      fill: inverse ? C.paper0 : C.ink950,
      radius: 6,
      primary: "CENTER",
      counter: "CENTER",
    });
    append(mark, text("⚖", "Caption", inverse ? C.ink950 : C.paper0));
    const word = autoFrame("Wordmark", {
      direction: "HORIZONTAL",
      gap: 4,
      fill: null,
      counter: "CENTER",
    });
    const juris = text("JURIS", "Label", inverse ? C.paper0 : C.ink950);
    juris.letterSpacing = { unit: "PERCENT", value: 12 };
    const ai = text("AI", "Label", C.gold600);
    ai.letterSpacing = { unit: "PERCENT", value: 12 };
    append(word, [juris, ai]);
    append(node, [mark, word]);
    return node;
  }

  function button(label, variant, size, state, hotspot) {
    const palette = {
      primary: [C.ink950, C.paper0, C.ink950],
      ghost: [C.paper0, C.ink950, C.paper0],
      outline: [C.paper0, C.ink950, C.line200],
      destructive: [C.danger600, C.paper0, C.danger600],
      gold: [C.gold600, C.ink950, C.gold600],
    };
    const colors = palette[variant || "primary"];
    const disabled = state === "disabled";
    const loading = state === "loading";
    const node = autoFrame(
      hotspot ? "Hotspot / " + hotspot : "Button / " + label,
      {
        direction: "HORIZONTAL",
        gap: 8,
        paddingTop: size === "sm" ? 8 : 10,
        paddingBottom: size === "sm" ? 8 : 10,
        paddingLeft: size === "sm" ? 12 : 16,
        paddingRight: size === "sm" ? 12 : 16,
        fill: variant === "ghost" ? null : colors[0],
        stroke: variant === "outline" ? colors[2] : null,
        radius: 10,
        counter: "CENTER",
        primary: "CENTER",
      },
    );
    if (state === "hover") node.opacity = 0.88;
    if (disabled) node.opacity = 0.4;
    if (loading) append(node, text("◌", "Body", colors[1]));
    append(node, text(loading ? label + "…" : label, "Body", colors[1]));
    return node;
  }

  function field(label, placeholder, state, width) {
    const group = autoFrame("Field / " + label, {
      gap: 6,
      fill: null,
      width: width || 320,
    });
    append(group, text(label, "Label", C.ink600));
    const box = autoFrame("Input / " + state, {
      direction: "HORIZONTAL",
      width: width || 320,
      height: 40,
      paddingLeft: 12,
      paddingRight: 12,
      fill: state === "disabled" ? C.paper50 : C.paper0,
      stroke: state === "error" ? C.danger600 : state === "focus" ? C.gold600 : C.line200,
      strokeWeight: state === "focus" ? 2 : 1,
      radius: 6,
      counter: "CENTER",
    });
    append(box, text(placeholder, "Body", C.ink400));
    append(group, box);
    if (state === "error") {
      append(group, text("Please review this field.", "Caption", C.danger600));
    } else {
      append(group, text("Helper text", "Caption", C.ink400));
    }
    if (state === "disabled") group.opacity = 0.55;
    return group;
  }

  function textareaBlock(value, width) {
    const node = autoFrame("Textarea", {
      width: width || 520,
      padding: 12,
      gap: 12,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    append(node, [
      text(value || "Ask a legal question or attach a contract…", "Body", C.ink400, {
        width: (width || 520) - 24,
      }),
      text("0 / 10000", "Caption", C.ink400),
    ]);
    return node;
  }

  function alertBox(tone, titleValue, bodyValue, width) {
    const toneMap = {
      error: [C.danger50, C.danger600, "⚠"],
      warning: [C.gold100, C.ink950, "△"],
      info: [C.paper0, C.info600, "ⓘ"],
      success: [C.success50, C.success600, "✓"],
    };
    const colors = toneMap[tone] || toneMap.info;
    const node = autoFrame("Alert / " + tone, {
      direction: "HORIZONTAL",
      width: width || 360,
      padding: 12,
      gap: 10,
      fill: colors[0],
      stroke: colors[1],
      radius: 6,
    });
    append(node, text(colors[2], "Body", colors[1]));
    const copy = autoFrame("Alert copy", { gap: 2, fill: null });
    append(copy, [
      text(titleValue || tone, "H2", colors[1]),
      text(bodyValue || "Supporting information.", "Caption", colors[1], {
        width: (width || 360) - 54,
      }),
    ]);
    append(node, copy);
    return node;
  }

  function legalDisclaimer(width) {
    return text(DISCLAIMER, "Caption", C.ink400, {
      width: width || 520,
      name: "LegalDisclaimer",
    });
  }

  function conversationRow(titleValue, time, state, hotspot) {
    const active = state === "active";
    const node = autoFrame(
      hotspot ? "Hotspot / " + hotspot : "ConversationRow / " + state,
      {
        direction: "HORIZONTAL",
        width: 228,
        padding: 10,
        gap: 8,
        fill: active ? C.gold100 : state === "hover" ? C.ink800 : C.ink950,
        radius: 6,
        counter: "CENTER",
      },
    );
    const copy = autoFrame("Conversation copy", { gap: 2, fill: null });
    append(copy, [
      text(titleValue, "Body", active ? C.ink950 : C.paper0, { width: 162 }),
      text(time, "Caption", active ? C.ink600 : C.ink400),
    ]);
    append(node, [copy, spacer()]);
    if (state === "hover") append(node, text("⌫", "Body", C.paper0));
    return node;
  }

  function starterCard(titleValue, preview, hotspot) {
    const node = autoFrame(
      hotspot ? "Hotspot / " + hotspot : "StarterCard / " + titleValue,
      {
        width: 196,
        height: 160,
        padding: 16,
        gap: 12,
        fill: C.paper0,
        stroke: C.line200,
        radius: 10,
      },
    );
    append(node, [
      pill("§", C.gold100, C.gold600),
      text(titleValue, "H2", C.ink950),
      text(preview, "Caption", C.ink600, { width: 164 }),
    ]);
    return node;
  }

  function fileChip(name, kind) {
    const node = autoFrame("FileChip", {
      direction: "HORIZONTAL",
      paddingTop: 6,
      paddingBottom: 6,
      paddingLeft: 10,
      paddingRight: 10,
      gap: 8,
      fill: C.paper50,
      stroke: C.line200,
      radius: 6,
      counter: "CENTER",
    });
    append(node, [
      text("▤", "Body", C.gold600),
      text(name, "Caption", C.ink950),
      pill(kind || "PDF", C.gold100, C.ink950),
      text("×", "Body", C.ink400),
    ]);
    return node;
  }

  function citationChip(index, titleValue, hotspot) {
    const node = autoFrame(
      hotspot ? "Hotspot / " + hotspot : "CitationChip",
      {
        direction: "HORIZONTAL",
        paddingTop: 6,
        paddingBottom: 6,
        paddingLeft: 10,
        paddingRight: 10,
        fill: C.gold100,
        stroke: C.gold600,
        radius: 999,
        counter: "CENTER",
      },
    );
    append(node, text("[" + index + "] " + titleValue, "Caption", C.ink950));
    return node;
  }

  function userMessage(copy, withFile) {
    const node = autoFrame("Message / User", {
      width: 520,
      padding: 16,
      gap: 10,
      fill: C.ink800,
      radius: 10,
      counter: "MAX",
    });
    if (withFile) append(node, fileChip("service-agreement.pdf", "PDF"));
    append(node, text(copy, "Body", C.paper0, { width: 488 }));
    return node;
  }

  function assistantMessage(copy, citations) {
    const node = autoFrame("Message / Assistant", {
      width: 680,
      padding: 20,
      gap: 14,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    append(node, text(copy, "Body Serif", C.ink950, { width: 640 }));
    if (citations !== false) {
      const row = autoFrame("Citation row", {
        direction: "HORIZONTAL",
        gap: 8,
        fill: null,
        wrap: true,
      });
      append(row, [
        citationChip("1", "Constitution of India", "citation chip"),
        citationChip("2", "Maneka Gandhi"),
      ]);
      append(node, row);
    }
    append(node, text("legal agent · 1.2s · 842 tokens", "Caption", C.ink400));
    return node;
  }

  function workingIndicator() {
    const node = autoFrame("WorkingIndicator", {
      direction: "HORIZONTAL",
      padding: 12,
      gap: 12,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
      counter: "CENTER",
    });
    append(node, [
      text("● ● ●", "Caption", C.gold600),
      text("Researching and drafting…", "Body", C.ink600),
      text("0:24", "Caption", C.ink400),
    ]);
    return node;
  }

  function approvalCard(status, hotspotApprove, hotspotReject) {
    const palette =
      status === "approved"
        ? [C.success50, C.success600]
        : status === "rejected" || status === "expired"
          ? [C.danger50, C.danger600]
          : [C.gold100, C.gold600];
    const node = autoFrame("ApprovalCard / " + status, {
      width: 600,
      padding: 16,
      gap: 12,
      fill: palette[0],
      stroke: palette[1],
      strokeWeight: status === "waiting" ? 3 : 1,
      radius: 10,
    });
    append(node, text("Approval required", "H2", C.ink950));
    if (status === "waiting") {
      append(node, [
        text(
          "The assistant wants to send an email via Gmail about this conversation.",
          "Body",
          C.ink600,
          { width: 568 },
        ),
        text("Gmail · expires in 14:32", "Caption", C.ink600),
      ]);
      const actions = autoFrame("Approval actions", {
        direction: "HORIZONTAL",
        gap: 8,
        fill: null,
      });
      append(actions, [
        button("Approve", "gold", "sm", "default", hotspotApprove || "Approve"),
        button("Reject", "outline", "sm", "default", hotspotReject || "Reject"),
      ]);
      append(node, actions);
    } else {
      const message = {
        approved: "Approved. Email sent.",
        rejected: "Rejected. The email was not sent.",
        expired: "This approval expired. Send a new message to retry.",
      };
      append(node, text(message[status], "Body", palette[1], { width: 568 }));
    }
    return node;
  }

  function citationDrawer(width, hotspotClose) {
    const node = autoFrame("CitationDrawer", {
      width: width || 360,
      height: 900,
      padding: 20,
      gap: 16,
      fill: C.paper0,
      stroke: C.line200,
    });
    const header = autoFrame("Drawer header", {
      direction: "HORIZONTAL",
      width: (width || 360) - 40,
      fill: null,
      counter: "CENTER",
    });
    append(header, [
      text("Sources", "H2", C.ink950),
      spacer(),
      button("×", "ghost", "sm", "default", hotspotClose || "close"),
    ]);
    append(node, header);
    const sourceOne = autoFrame("Source / selected", {
      width: (width || 360) - 40,
      padding: 14,
      gap: 8,
      fill: C.gold100,
      stroke: C.gold600,
      radius: 10,
    });
    append(sourceOne, [
      text("1  Constitution of India", "H2", C.ink950),
      text("Article 21 · page —", "Caption", C.ink600),
      text(
        "“No person shall be deprived of his life or personal liberty except according to procedure established by law.”",
        "Body Serif",
        C.ink600,
        { width: (width || 360) - 68 },
      ),
    ]);
    const sourceTwo = autoFrame("Source / default", {
      width: (width || 360) - 40,
      padding: 14,
      gap: 8,
      fill: C.paper50,
      stroke: C.line200,
      radius: 10,
    });
    append(sourceTwo, [
      text("2  Maneka Gandhi v. Union of India", "H2", C.ink950, {
        width: (width || 360) - 68,
      }),
      text("Supreme Court of India · 1978", "Caption", C.ink600),
      text("indiankanoon.org/doc/1766147/", "Caption", C.info600),
    ]);
    append(node, [sourceOne, sourceTwo]);
    return node;
  }

  function quotaBanner(code) {
    const isRate = code === "RATE_LIMIT_EXCEEDED";
    return alertBox(
      "warning",
      isRate ? "Request limit reached" : "Daily usage limit reached",
      isRate
        ? "You have reached the limit of 20 requests per minute. Try again shortly."
        : "Daily token quota reached (200,000). Resets at midnight UTC.",
      720,
    );
  }

  function composer(width, disabled) {
    const node = autoFrame("Composer", {
      width: width,
      padding: 12,
      gap: 8,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    append(node, textareaBlock("Ask a legal question or attach a contract…", width - 24));
    const actions = autoFrame("Composer actions", {
      direction: "HORIZONTAL",
      width: width - 24,
      fill: null,
      counter: "CENTER",
    });
    append(actions, [
      button("Attach", "ghost", "sm", disabled ? "disabled" : "default"),
      spacer(),
      button("Send", "primary", "sm", disabled ? "disabled" : "default", "Send"),
    ]);
    append(node, [actions, legalDisclaimer(width - 24)]);
    return node;
  }

  async function resetPages() {
    if (figma.loadAllPagesAsync) await figma.loadAllPagesAsync();
    const existing = Array.from(figma.root.children);
    const cover = existing[0] || figma.createPage();
    if (figma.setCurrentPageAsync) {
      await figma.setCurrentPageAsync(cover);
    } else {
      figma.currentPage = cover;
    }
    for (const child of Array.from(cover.children)) child.remove();
    cover.name = PAGE_NAMES[0];
    for (const page of existing) {
      if (page !== cover) page.remove();
    }
    const pages = { [PAGE_NAMES[0]]: cover };
    for (const name of PAGE_NAMES.slice(1)) {
      const page = figma.createPage();
      page.name = name;
      pages[name] = page;
    }
    return pages;
  }

  async function createVariables() {
    const names = ["Color / Primitive", "Color / Semantic", "Spacing", "Radius"];
    const existing = figma.variables.getLocalVariableCollectionsAsync
      ? await figma.variables.getLocalVariableCollectionsAsync()
      : figma.variables.getLocalVariableCollections();
    for (const collection of existing) {
      if (names.includes(collection.name) && collection.remove) {
        collection.remove();
      }
    }
    const primitive = figma.variables.createVariableCollection("Color / Primitive");
    const semantic = figma.variables.createVariableCollection("Color / Semantic");
    const spacing = figma.variables.createVariableCollection("Spacing");
    const radius = figma.variables.createVariableCollection("Radius");
    const primitiveValues = {
      "ink/950": C.ink950,
      "ink/800": C.ink800,
      "ink/600": C.ink600,
      "ink/400": C.ink400,
      "paper/50": C.paper50,
      "paper/0": C.paper0,
      "line/200": C.line200,
      "gold/600": C.gold600,
      "gold/100": C.gold100,
      "danger/600": C.danger600,
      "danger/50": C.danger50,
      "success/600": C.success600,
      "success/50": C.success50,
      "info/600": C.info600,
    };
    const primitiveVariables = {};

    function createVariable(name, collection, type, value) {
      let variable;
      try {
        variable = figma.variables.createVariable(name, collection, type);
      } catch {
        variable = figma.variables.createVariable(name, collection.id, type);
      }
      variable.setValueForMode(collection.defaultModeId, value);
      return variable;
    }

    for (const [name, value] of Object.entries(primitiveValues)) {
      primitiveVariables[name] = createVariable(
        name,
        primitive,
        "COLOR",
        rgb(value),
      );
    }
    const semanticValues = {
      "bg/app": "paper/50",
      "bg/sidebar": "ink/950",
      "bg/elevated": "paper/0",
      "text/primary": "ink/950",
      "text/on-dark": "paper/0",
      "text/muted": "ink/600",
      "border/default": "line/200",
      accent: "gold/600",
      focus: "gold/600",
    };
    for (const [name, aliasName] of Object.entries(semanticValues)) {
      const alias = figma.variables.createVariableAlias
        ? figma.variables.createVariableAlias(primitiveVariables[aliasName])
        : rgb(primitiveValues[aliasName]);
      createVariable(name, semantic, "COLOR", alias);
    }
    for (const value of [4, 8, 12, 16, 24, 32, 48]) {
      createVariable(String(value), spacing, "FLOAT", value);
    }
    for (const [name, value] of Object.entries({
      sm: 6,
      md: 10,
      lg: 16,
      pill: 999,
    })) {
      createVariable(name, radius, "FLOAT", value);
    }
  }

  async function createTextStyles() {
    const styleNames = Object.keys(TYPE);
    const existing = figma.getLocalTextStylesAsync
      ? await figma.getLocalTextStylesAsync()
      : figma.getLocalTextStyles();
    for (const style of existing) {
      if (styleNames.includes(style.name)) style.remove();
    }
    for (const name of styleNames) {
      const spec = TYPE[name];
      const style = figma.createTextStyle();
      style.name = name;
      style.fontName = fonts[spec.font];
      style.fontSize = spec.size;
      style.lineHeight = { unit: "PIXELS", value: spec.line };
      style.letterSpacing = { unit: "PERCENT", value: spec.tracking || 0 };
      if (spec.textCase) style.textCase = spec.textCase;
      style.description =
        name === "Body Serif" && fonts.serif.family !== "Source Serif 4"
          ? "Source Serif 4 unavailable; generated with " + fonts.serif.family + "."
          : "Juris AI Web v1";
    }
  }

  function place(page, node, index, width, columns, gap) {
    const count = columns || 3;
    const gutter = gap || 120;
    node.x = (index % count) * (width + gutter);
    node.y = Math.floor(index / count) * (node.height + gutter);
    page.appendChild(node);
    return node;
  }

  function coverPage(page) {
    const cover = autoFrame("Juris AI — Web v1", {
      width: 1440,
      height: 900,
      padding: 64,
      gap: 24,
      fill: C.ink950,
    });
    append(cover, [
      logo(true),
      spacer(1),
      text("Juris AI — Web v1", "Display", C.paper0),
      text("Individual legal assistant — not a firm OS", "H1", C.gold100),
      text(
        "Versioned local generator · Design system, desktop, mobile, prototype, and explicit v2+ boundaries.",
        "Body",
        C.paper0,
        { width: 760 },
      ),
      pill("WEB V1 · 2026-09-15", C.gold600, C.ink950),
      spacer(1),
      text("Generated locally in Figma Desktop — no cloud publishing implied.", "Caption", C.ink400),
    ]);
    page.appendChild(cover);
    return cover;
  }

  function foundationPage(page) {
    const root = autoFrame("Foundation / Web v1", {
      width: 1440,
      padding: 48,
      gap: 32,
      fill: C.paper50,
    });
    append(root, [
      text("Foundation", "Display", C.ink950),
      text("Color variables · type styles · 8px grid · Lucide-compatible 16/20 icons", "Body", C.ink600),
    ]);
    const swatches = autoFrame("Primitive color swatches", {
      direction: "HORIZONTAL",
      wrap: true,
      width: 1344,
      gap: 12,
      counterGap: 12,
      fill: null,
    });
    const colors = [
      ["ink/950", C.ink950],
      ["ink/800", C.ink800],
      ["ink/600", C.ink600],
      ["ink/400", C.ink400],
      ["paper/50", C.paper50],
      ["paper/0", C.paper0],
      ["line/200", C.line200],
      ["gold/600", C.gold600],
      ["gold/100", C.gold100],
      ["danger/600", C.danger600],
      ["danger/50", C.danger50],
      ["success/600", C.success600],
      ["success/50", C.success50],
      ["info/600", C.info600],
    ];
    for (const [name, value] of colors) {
      const swatch = autoFrame("Swatch / " + name, {
        width: 180,
        padding: 12,
        gap: 24,
        fill: value,
        stroke: C.line200,
        radius: 10,
      });
      const darkText = name.startsWith("paper") || name.endsWith("/50") || name.endsWith("/100") || name === "line/200";
      append(swatch, [
        text(name, "Label", darkText ? C.ink950 : C.paper0),
        text(value, "Caption", darkText ? C.ink600 : C.paper0),
      ]);
      append(swatches, swatch);
    }
    append(root, swatches);
    const specimens = autoFrame("Type specimens", {
      width: 1344,
      padding: 24,
      gap: 16,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    for (const name of Object.keys(TYPE)) {
      append(
        specimens,
        text(
          name + " — Legal research with sources you can open.",
          name,
          C.ink950,
        ),
      );
    }
    const rhythm = autoFrame("Spacing, radius, icons", {
      direction: "HORIZONTAL",
      gap: 24,
      fill: null,
    });
    append(rhythm, [
      text("Spacing  4 · 8 · 12 · 16 · 24 · 32 · 48", "Body", C.ink600),
      text("Radius  sm 6 · md 10 · lg 16 · pill 999", "Body", C.ink600),
      text("Icons  ☰  ⚖  ⌕  ＋  ×  ⚠", "H2", C.ink950),
    ]);
    append(root, rhythm);
    page.appendChild(root);
  }

  function componentFrom(name, builder) {
    const component = autoFrame(name, {
      component: true,
      padding: 12,
      gap: 8,
      fill: null,
    });
    builder(component);
    return component;
  }

  function createVariantSet(page, name, variants) {
    for (const variant of variants) page.appendChild(variant);
    try {
      const set = figma.combineAsVariants(variants, page);
      set.name = name;
      set.layoutMode = "HORIZONTAL";
      set.layoutWrap = "WRAP";
      set.itemSpacing = 12;
      set.counterAxisSpacing = 12;
      set.paddingTop = 16;
      set.paddingRight = 16;
      set.paddingBottom = 16;
      set.paddingLeft = 16;
      set.fills = [solid(C.paper50)];
      set.primaryAxisSizingMode = "FIXED";
      set.resize(1600, set.height);
      return set;
    } catch {
      const fallback = autoFrame(name + " / variants", {
        direction: "HORIZONTAL",
        wrap: true,
        padding: 16,
        gap: 12,
        fill: C.paper50,
      });
      for (const variant of variants) fallback.appendChild(variant);
      page.appendChild(fallback);
      return fallback;
    }
  }

  function componentsPage(page) {
    const nodes = [];
    nodes.push(logo(false, true));

    const buttonVariants = [];
    for (const variant of ["primary", "ghost", "outline", "destructive", "gold"]) {
      for (const size of ["sm", "md"]) {
        for (const state of ["default", "hover", "disabled", "loading"]) {
          buttonVariants.push(
            componentFrom(
              "Variant=" + variant + ", Size=" + size + ", State=" + state,
              (component) => append(component, button("Action", variant, size, state)),
            ),
          );
        }
      }
    }
    nodes.push(createVariantSet(page, "Button", buttonVariants));

    nodes.push(
      createVariantSet(
        page,
        "Input",
        ["default", "focus", "error", "disabled"].map((state) =>
          componentFrom("State=" + state, (component) =>
            append(component, field("Email", "name@example.com", state, 300)),
          ),
        ),
      ),
    );
    nodes.push(
      componentFrom("Textarea", (component) =>
        append(component, textareaBlock("Ask a legal question…", 420)),
      ),
    );
    nodes.push(
      createVariantSet(
        page,
        "Alert",
        ["error", "warning", "info"].map((tone) =>
          componentFrom("Tone=" + tone, (component) =>
            append(component, alertBox(tone, "Alert title", "Useful supporting copy.", 360)),
          ),
        ),
      ),
    );
    nodes.push(
      componentFrom("Toast", (component) =>
        append(component, alertBox("success", "Conversation archived", "Your sidebar is up to date.", 360)),
      ),
    );
    nodes.push(
      componentFrom("LegalDisclaimer", (component) =>
        append(component, legalDisclaimer(520)),
      ),
    );
    nodes.push(
      createVariantSet(
        page,
        "ConversationRow",
        ["idle", "hover", "active"].map((state) =>
          componentFrom("State=" + state, (component) =>
            append(component, conversationRow("Article 21 research", "2h", state)),
          ),
        ),
      ),
    );
    nodes.push(
      componentFrom("StarterCard", (component) =>
        append(component, starterCard("Legal research", "What does the law say about …")),
      ),
    );
    nodes.push(componentFrom("FileChip", (component) => append(component, fileChip("agreement.pdf", "PDF"))));
    nodes.push(componentFrom("Message User", (component) => append(component, userMessage("Explain Article 21.", false))));
    nodes.push(componentFrom("Message Assistant", (component) => append(component, assistantMessage("Article 21 protects life and personal liberty.", true))));
    nodes.push(componentFrom("CitationChip", (component) => append(component, citationChip("1", "Constitution of India"))));
    nodes.push(componentFrom("WorkingIndicator", (component) => append(component, workingIndicator())));
    nodes.push(
      createVariantSet(
        page,
        "ApprovalCard",
        ["waiting", "approved", "rejected", "expired"].map((status) =>
          componentFrom("Status=" + status, (component) =>
            append(component, approvalCard(status)),
          ),
        ),
      ),
    );
    nodes.push(componentFrom("CitationDrawer", (component) => append(component, citationDrawer(360))));
    nodes.push(
      createVariantSet(
        page,
        "QuotaBanner",
        ["RATE_LIMIT_EXCEEDED", "TOKEN_QUOTA_EXCEEDED"].map((code) =>
          componentFrom("Code=" + code, (component) => append(component, quotaBanner(code))),
        ),
      ),
    );
    nodes.push(
      componentFrom("EmptyState", (component) =>
        append(component, [
          text("◇", "Display", C.gold600),
          text("Start your first research thread.", "H2", C.ink950),
          text("Ask a legal question to begin.", "Body", C.ink600),
        ]),
      ),
    );
    nodes.push(
      componentFrom("ErrorState", (component) =>
        append(component, [
          text("Could not load conversations", "H2", C.ink950),
          button("Retry", "outline", "sm"),
        ]),
      ),
    );
    nodes.push(
      componentFrom("Skeleton", (component) => {
        for (const width of [220, 180, 204]) {
          const bar = autoFrame("Skeleton bar", {
            width,
            height: 18,
            fill: C.line200,
            radius: 6,
          });
          append(component, bar);
        }
      }),
    );
    nodes.push(
      componentFrom("UserMenu", (component) =>
        append(component, [
          iconLabel("AV", "Amit Vishvakarma", C.ink950),
          divider(220),
          iconLabel("⚙", "Settings"),
          iconLabel("↪", "Log out", C.danger600),
        ]),
      ),
    );
    nodes.push(
      componentFrom("Modal Archive", (component) =>
        append(component, [
          text("Archive this conversation?", "H1", C.ink950),
          text("It will leave your sidebar. You cannot reopen it in v1.", "Body", C.ink600, { width: 420 }),
          autoFrame("Archive actions", { direction: "HORIZONTAL", gap: 8, fill: null }),
        ]),
      ),
    );
    const modal = nodes[nodes.length - 1];
    append(modal.children[2], [
      button("Cancel", "outline", "md"),
      button("Archive", "destructive", "md"),
    ]);
    nodes.push(
      componentFrom("AppShell", (component) => {
        const shell = autoFrame("AppShell anatomy", {
          direction: "HORIZONTAL",
          width: 800,
          height: 500,
          fill: C.paper50,
          stroke: C.line200,
        });
        const side = autoFrame("Sidebar 260", {
          width: 260,
          height: 500,
          padding: 16,
          gap: 16,
          fill: C.ink950,
        });
        append(side, [logo(true), button("+ New chat", "gold", "md"), conversationRow("Article 21 research", "2h", "active")]);
        const main = autoFrame("Main", {
          width: 540,
          height: 500,
          padding: 24,
          gap: 16,
          fill: C.paper50,
        });
        append(main, [
          text("Article 21 research", "H2", C.ink950),
          assistantMessage("Answer body with real citations.", true),
        ]);
        append(shell, [side, main]);
        append(component, shell);
      }),
    );

    const gallery = autoFrame("Juris AI component library", {
      width: 1800,
      padding: 48,
      gap: 40,
      fill: C.paper0,
    });
    append(gallery, [
      text("Components", "Display", C.ink950),
      text(
        "Reusable Web v1 components and exhaustive state variants.",
        "Body",
        C.ink600,
      ),
    ]);
    nodes.forEach((node) => {
      const specimen = autoFrame("Specimen / " + node.name, {
        width: 1704,
        padding: 16,
        gap: 12,
        fill: C.paper50,
        stroke: C.line200,
        radius: 10,
      });
      append(specimen, [text(node.name, "Label", C.ink600), node]);
      append(gallery, specimen);
    });
    page.appendChild(gallery);
  }

  function topBar(width, titleValue) {
    const node = autoFrame("Top bar", {
      direction: "HORIZONTAL",
      width,
      height: 72,
      paddingLeft: 24,
      paddingRight: 24,
      fill: C.paper50,
      stroke: C.line200,
      counter: "CENTER",
    });
    append(node, [
      text(titleValue, "H2", C.ink950),
      spacer(),
      iconLabel("AV", "Amit", C.ink950),
    ]);
    const settings = node.children[node.children.length - 1];
    settings.name = "Hotspot / UserMenu Settings";
    return node;
  }

  function sidebar(state) {
    const node = autoFrame("Sidebar", {
      width: 260,
      height: 900,
      padding: 16,
      gap: 14,
      fill: C.ink950,
    });
    append(node, [
      logo(true),
      button("+ New chat", "gold", "md", "default", "New chat"),
    ]);
    const search = autoFrame("Search conversations", {
      direction: "HORIZONTAL",
      width: 228,
      height: 40,
      paddingLeft: 12,
      fill: C.ink800,
      stroke: C.ink600,
      radius: 6,
      counter: "CENTER",
    });
    append(search, text("⌕  Search conversations", "Caption", C.ink400));
    append(node, [search, text("Recent", "Label", C.ink400)]);
    if (state === "error") {
      append(node, [
        text("Could not load conversations", "Body", C.paper0, { width: 220 }),
        button("Retry", "outline", "sm"),
      ]);
    } else if (state === "empty") {
      append(node, text("No threads yet", "Caption", C.ink400));
    } else {
      const rows = [
        ["Article 21 research", "2h", state === "active" ? "active" : "idle"],
        ["NDA review — Acme", "2h", state === "hover" ? "hover" : "idle"],
        ["Service agreement risks", "1d", "idle"],
        ["IT Act research", "2d", "idle"],
        ["Employment clauses", "4d", "idle"],
        ["Privacy policy review", "Sep 8", "idle"],
      ];
      rows.forEach((row, index) =>
        append(
          node,
          conversationRow(
            row[0],
            row[1],
            row[2],
            index === 0 ? "conversation row" : index === 1 ? "archive icon" : null,
          ),
        ),
      );
    }
    append(node, [
      spacer(),
      divider(228),
      iconLabel("AV", "Amit Vishvakarma", C.paper0),
    ]);
    return node;
  }

  function authScreen(name, kind, state) {
    const screen = autoFrame(name, {
      width: 1440,
      height: 900,
      padding: 32,
      gap: 16,
      fill: C.paper50,
      primary: "CENTER",
      counter: "CENTER",
    });
    const card = autoFrame("Auth card", {
      width: 420,
      padding: 32,
      gap: 16,
      fill: C.paper0,
      stroke: C.line200,
      radius: 16,
    });
    append(card, [
      logo(false),
      text(kind === "login" ? "Sign in" : "Create account", "H1", C.ink950),
      text(
        kind === "login"
          ? "Continue to your workspace"
          : "Start your legal research workspace",
        "Caption",
        C.ink600,
      ),
    ]);
    if (state === "error") {
      append(
        card,
        alertBox(
          "error",
          "Could not continue",
          kind === "login"
            ? "Invalid email or password."
            : "An account with this email already exists.",
          356,
        ),
      );
    }
    if (state === "inactive") {
      append(card, alertBox("error", "Account inactive", "This account is inactive.", 356));
    }
    if (kind === "register") {
      const row = autoFrame("Name fields", {
        direction: "HORIZONTAL",
        gap: 12,
        fill: null,
      });
      append(row, [
        field("First name", "Optional", "default", 172),
        field("Last name", "Optional", "default", 172),
      ]);
      append(card, row);
    }
    append(card, field("Email", "name@example.com", state === "loading" ? "disabled" : "default", 356));
    append(card, field("Password", "••••••••", state === "loading" ? "disabled" : "default", 356));
    if (kind === "register") {
      append(card, [
        text("At least 8 characters.", "Caption", C.ink400),
        field("Confirm password", "••••••••", "default", 356),
      ]);
    }
    append(
      card,
      button(
        state === "loading"
          ? "Signing in"
          : kind === "login"
            ? "Sign in"
            : "Create account",
        "primary",
        "md",
        state === "loading" ? "loading" : "default",
        kind === "login" ? "Sign in" : "Create account",
      ),
    );
    const authLink = text(
      kind === "login"
        ? "New here?  Create an account"
        : "Already have an account?  Sign in",
      "Caption",
      C.info600,
    );
    authLink.name =
      "Hotspot / " + (kind === "login" ? "Create an account" : "Sign in");
    append(card, [authLink, legalDisclaimer(356)]);
    append(screen, card);
    return screen;
  }

  function landingScreen() {
    const screen = autoFrame("D01 Landing", {
      width: 1440,
      height: 900,
      paddingLeft: 64,
      paddingRight: 64,
      paddingTop: 32,
      paddingBottom: 32,
      gap: 36,
      fill: C.paper50,
    });
    const nav = autoFrame("Landing navigation", {
      direction: "HORIZONTAL",
      width: 1312,
      fill: null,
      counter: "CENTER",
    });
    append(nav, [
      logo(false),
      spacer(),
      button("Log in", "ghost", "md", "default", "Log in"),
      button("Get started", "primary", "md", "default", "Get started"),
    ]);
    const hero = autoFrame("Hero", {
      width: 920,
      paddingTop: 48,
      paddingBottom: 32,
      gap: 20,
      fill: null,
    });
    append(hero, [
      pill("INDIVIDUAL LEGAL ASSISTANT", C.gold100, C.gold600),
      text("Legal research with sources you can open.", "Display", C.ink950, {
        width: 780,
      }),
      text(
        "Ask questions, review contracts, and inspect citations. Juris AI is not a lawyer and does not create an attorney–client relationship.",
        "Body",
        C.ink600,
        { width: 720 },
      ),
      button("Start researching", "primary", "md", "default", "Get started"),
    ]);
    const features = autoFrame("Capabilities", {
      direction: "HORIZONTAL",
      gap: 16,
      fill: null,
    });
    [
      ["Legal research", "Ground questions in Indian legal materials."],
      ["Contract review", "Inspect clauses, obligations, and risks."],
      ["Cited answers", "Open sources and review exact snippets."],
    ].forEach(([titleValue, body]) => {
      const card = autoFrame("Capability / " + titleValue, {
        width: 320,
        padding: 20,
        gap: 10,
        fill: C.paper0,
        stroke: C.line200,
        radius: 10,
      });
      append(card, [
        text("§", "H1", C.gold600),
        text(titleValue, "H2", C.ink950),
        text(body, "Body", C.ink600, { width: 280 }),
      ]);
      append(features, card);
    });
    append(screen, [nav, hero, features, spacer(), legalDisclaimer(920)]);
    return screen;
  }

  function coverScreen() {
    const screen = autoFrame("D00 Cover", {
      width: 1440,
      height: 900,
      padding: 64,
      gap: 24,
      fill: C.ink950,
    });
    append(screen, [
      logo(true),
      spacer(),
      text("Juris AI Web v1", "Display", C.paper0),
      text("Legal information assistant", "H1", C.gold100),
    ]);
    const thumbs = autoFrame("Screen thumbnails", {
      direction: "HORIZONTAL",
      gap: 16,
      fill: null,
    });
    ["Login", "Empty app", "Thread + citations"].forEach((label) => {
      const thumb = autoFrame("Thumbnail / " + label, {
        width: 300,
        height: 180,
        padding: 20,
        gap: 12,
        fill: C.paper50,
        radius: 10,
      });
      append(thumb, [
        text(label, "H2", C.ink950),
        divider(250),
        text("Warm paper · dark ink · source-led trust", "Caption", C.ink600),
      ]);
      append(thumbs, thumb);
    });
    append(screen, [thumbs, spacer(), text("Individual workspace · Web v1", "Caption", C.ink400)]);
    return screen;
  }

  function emptyBody(width) {
    const body = autoFrame("Empty workspace", {
      width,
      padding: 32,
      gap: 16,
      fill: C.paper50,
      primary: "CENTER",
      counter: "CENTER",
    });
    append(body, [
      text("What do you want to work on?", "Display", C.ink950),
      text(
        "Answers are legal information, not advice. Name a jurisdiction when it matters.",
        "Body",
        C.ink600,
      ),
    ]);
    const starters = autoFrame("Starter cards", {
      direction: "HORIZONTAL",
      width: Math.min(width - 64, 1044),
      wrap: true,
      gap: 12,
      counterGap: 12,
      fill: null,
      primary: "CENTER",
    });
    append(starters, [
      starterCard("Legal research", "What does the law say about …", "starter card"),
      starterCard("Review contract", "Review this contract", "Review this contract"),
      starterCard("Analyze agreement", "Analyze this agreement"),
      starterCard("Extract clauses", "Extract important clauses"),
      starterCard("Identify risks", "Identify contractual risks"),
    ]);
    append(body, starters);
    body.layoutGrow = 1;
    return body;
  }

  function messageBody(width, state) {
    const body = autoFrame("Message list / " + state, {
      width,
      padding: 24,
      gap: 20,
      fill: C.paper50,
    });
    body.layoutGrow = 1;
    if (state === "404") {
      append(body, [
        spacer(),
        text("Conversation not found", "H1", C.ink950),
        text("This conversation was archived or does not exist.", "Body", C.ink600),
        button("Back to workspace", "outline", "md"),
        spacer(),
      ]);
      return body;
    }
    append(body, userMessage("Explain Article 21 of the Constitution of India.", state === "files"));
    append(
      body,
      assistantMessage(
        state === "files"
          ? "The service agreement creates broad indemnity obligations and a one-sided termination right. Review the limitation-of-liability clause before signing."
          : "Article 21 protects life and personal liberty. The Supreme Court reads its procedure requirement as fair, just, and reasonable rather than merely formal.",
        true,
      ),
    );
    if (state === "working") {
      append(body, [
        userMessage("How does proportionality apply?", false),
        workingIndicator(),
      ]);
    }
    if (state.startsWith("hitl-")) {
      const status = state.replace("hitl-", "");
      append(body, approvalCard(status));
      if (status === "approved") {
        append(body, assistantMessage("Email sent.", false));
      }
      if (status === "rejected") {
        append(body, assistantMessage("The email was not sent.", false));
      }
    }
    if (state === "files") {
      const gated = pill("Gated external action", C.gold100, C.gold600);
      gated.name = "Hotspot / gated tool";
      append(body, gated);
    }
    return body;
  }

  function settingsBody(width) {
    const body = autoFrame("Settings content", {
      width,
      padding: 32,
      gap: 20,
      fill: C.paper50,
    });
    body.layoutGrow = 1;
    append(body, [
      text("Settings", "H1", C.ink950),
      text("Review your profile, service limits, and current session.", "Body", C.ink600),
    ]);
    const profile = autoFrame("Profile section", {
      width: width - 64,
      padding: 20,
      gap: 12,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    append(profile, text("Profile", "H2", C.ink950));
    const rowOne = autoFrame("Profile names", { direction: "HORIZONTAL", gap: 12, fill: null });
    append(rowOne, [
      field("First name", "Amit", "default", 260),
      field("Last name", "Vishvakarma", "default", 260),
    ]);
    const rowTwo = autoFrame("Profile details", { direction: "HORIZONTAL", gap: 12, fill: null });
    append(rowTwo, [
      field("Phone", "+91 98765 43210", "default", 260),
      field("Date of birth", "1990-01-02", "default", 260),
      field("Gender", "Not provided ▾", "default", 260),
    ]);
    append(profile, [rowOne, rowTwo, button("Save profile", "primary", "md")]);
    const usage = autoFrame("Usage section", {
      width: width - 64,
      padding: 20,
      gap: 8,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    append(usage, [
      text("Usage", "H2", C.ink950),
      text("20 requests / minute · 200,000 tokens / day", "Body", C.ink950),
      text("Remaining usage is not yet API-backed.", "Caption", C.ink600),
    ]);
    const library = autoFrame("Library section", {
      width: width - 64,
      padding: 20,
      gap: 8,
      fill: C.paper0,
      stroke: C.line200,
      radius: 10,
    });
    append(library, [
      text("Library", "H2", C.ink950),
      text("Document library is not available in v1. Attach files in chat.", "Body", C.ink600),
    ]);
    const logout = button("Log out", "destructive", "md", "default", "Log out");
    append(body, [profile, usage, library, logout]);
    return body;
  }

  function appScreen(name, state) {
    const drawerOpen = state === "citations";
    const screen = autoFrame(name, {
      direction: "HORIZONTAL",
      width: 1440,
      height: 900,
      gap: 0,
      fill: C.paper50,
      clip: true,
    });
    append(
      screen,
      sidebar(
        state === "list-error"
          ? "error"
          : state === "empty"
            ? "empty"
            : state === "sidebar"
              ? "hover"
              : "active",
      ),
    );
    const mainWidth = drawerOpen ? 820 : 1180;
    const main = autoFrame("Main", {
      width: mainWidth,
      height: 900,
      gap: 0,
      fill: C.paper50,
    });
    const titleValue =
      state === "settings"
        ? "Settings"
        : state === "empty" || state === "sidebar" || state === "list-error"
          ? "New conversation"
          : "Article 21 research";
    append(main, topBar(mainWidth, titleValue));
    if (state === "empty" || state === "sidebar" || state === "list-error") {
      append(main, emptyBody(mainWidth));
      append(main, composer(Math.min(800, mainWidth - 48), false));
    } else if (state === "settings") {
      append(main, settingsBody(mainWidth));
    } else if (state === "archive") {
      const body = messageBody(mainWidth, "thread");
      const modal = autoFrame("Archive modal overlay", {
        width: 520,
        padding: 24,
        gap: 16,
        fill: C.paper0,
        stroke: C.line200,
        radius: 16,
      });
      append(modal, [
        text("Archive this conversation?", "H1", C.ink950),
        text("It will leave your sidebar. You cannot reopen it in v1.", "Body", C.ink600, { width: 472 }),
      ]);
      const actions = autoFrame("Modal actions", { direction: "HORIZONTAL", gap: 8, fill: null });
      append(actions, [
        button("Cancel", "outline", "md"),
        button("Archive", "destructive", "md", "default", "Archive"),
      ]);
      append(modal, actions);
      const modalRow = autoFrame("Centered modal", {
        direction: "HORIZONTAL",
        width: mainWidth - 48,
        fill: null,
        counter: "CENTER",
      });
      append(modalRow, [spacer(), modal, spacer()]);
      append(body, modalRow);
      append(main, body);
    } else {
      if (state === "quota") {
        const body = messageBody(mainWidth, "thread");
        append(body, [quotaBanner("RATE_LIMIT_EXCEEDED"), quotaBanner("TOKEN_QUOTA_EXCEEDED")]);
        append(main, body);
      } else if (state === "toasts") {
        const body = messageBody(mainWidth, "thread");
        const toastStack = autoFrame("Toast examples", {
          width: 360,
          gap: 8,
          fill: null,
        });
        toastStack.name = "Hotspot / toast";
        append(toastStack, [
          alertBox("success", "Conversation archived", "Your sidebar is up to date.", 360),
          alertBox("error", "Something went wrong.", "Request ID abc-123", 360),
        ]);
        const toastRow = autoFrame("Top-right toast position", {
          direction: "HORIZONTAL",
          width: mainWidth - 48,
          fill: null,
        });
        append(toastRow, [spacer(), toastStack]);
        append(body, toastRow);
        append(main, body);
      } else {
        append(main, messageBody(mainWidth, state));
      }
      append(main, composer(Math.min(800, mainWidth - 48), state === "working" || state === "quota"));
    }
    append(screen, main);
    if (drawerOpen) append(screen, citationDrawer(360));
    return screen;
  }

  function desktopScreens(page) {
    /** @type {Array<[string, () => FrameNode | ComponentNode]>} */
    const definitions = [
      ["D00 Cover", () => coverScreen()],
      ["D01 Landing", () => landingScreen()],
      ["D02 Login", () => authScreen("D02 Login", "login", "default")],
      ["D02a Login / loading", () => authScreen("D02a Login / loading", "login", "loading")],
      ["D02b Login / error", () => authScreen("D02b Login / error", "login", "error")],
      ["D02c Login / inactive", () => authScreen("D02c Login / inactive", "login", "inactive")],
      ["D03 Register", () => authScreen("D03 Register", "register", "default")],
      ["D03b Register / error", () => authScreen("D03b Register / error", "register", "error")],
      ["D04 App / empty", () => appScreen("D04 App / empty", "empty")],
      ["D05 App / sidebar populated", () => appScreen("D05 App / sidebar populated", "sidebar")],
      ["D06 App / thread", () => appScreen("D06 App / thread", "thread")],
      ["D07 App / working", () => appScreen("D07 App / working", "working")],
      ["D08 App / with files", () => appScreen("D08 App / with files", "files")],
      ["D09 App / citations open", () => appScreen("D09 App / citations open", "citations")],
      ["D10 App / HITL waiting", () => appScreen("D10 App / HITL waiting", "hitl-waiting")],
      ["D10b App / HITL approved", () => appScreen("D10b App / HITL approved", "hitl-approved")],
      ["D10c App / HITL rejected", () => appScreen("D10c App / HITL rejected", "hitl-rejected")],
      ["D10d App / HITL expired", () => appScreen("D10d App / HITL expired", "hitl-expired")],
      ["D11 App / quota", () => appScreen("D11 App / quota", "quota")],
      ["D12 App / list error", () => appScreen("D12 App / list error", "list-error")],
      ["D13 App / thread 404", () => appScreen("D13 App / thread 404", "404")],
      ["D14 Settings", () => appScreen("D14 Settings", "settings")],
      ["D15 Modal / archive", () => appScreen("D15 Modal / archive", "archive")],
      ["D16 Toast examples", () => appScreen("D16 Toast examples", "toasts")],
    ];
    const map = {};
    definitions.forEach(([name, factory], index) => {
      const node = factory();
      node.name = name;
      place(page, node, index, 1440, 3, 120);
      map[name] = node;
    });
    return map;
  }

  function mobileAuth(name, register) {
    const screen = autoFrame(name, {
      width: 390,
      height: 844,
      padding: 20,
      gap: 16,
      fill: C.paper50,
      primary: "CENTER",
    });
    append(screen, [
      logo(false),
      text(register ? "Create account" : "Sign in", "H1", C.ink950),
      text(register ? "Start your workspace" : "Continue to your workspace", "Caption", C.ink600),
    ]);
    if (register) {
      append(screen, [
        field("First name", "Optional", "default", 350),
        field("Last name", "Optional", "default", 350),
      ]);
    }
    append(screen, [
      field("Email", "name@example.com", "default", 350),
      field("Password", "••••••••", "default", 350),
    ]);
    if (register) append(screen, field("Confirm password", "••••••••", "default", 350));
    append(screen, [
      button(register ? "Create account" : "Sign in", "primary", "md"),
      legalDisclaimer(350),
    ]);
    return screen;
  }

  function mobileScreen(name, state) {
    if (state === "login") return mobileAuth(name, false);
    if (state === "register") return mobileAuth(name, true);
    const screen = autoFrame(name, {
      width: 390,
      height: 844,
      gap: 0,
      fill: C.paper50,
      clip: true,
    });
    const header = autoFrame("Mobile top bar", {
      direction: "HORIZONTAL",
      width: 390,
      height: 64,
      paddingLeft: 16,
      paddingRight: 16,
      fill: C.paper50,
      stroke: C.line200,
      counter: "CENTER",
    });
    append(header, [
      text(state === "empty" ? "☰" : "‹", "H1", C.ink950),
      text(
        state === "settings"
          ? "Settings"
          : state === "empty"
            ? "New conversation"
            : "Article 21 research",
        "H2",
        C.ink950,
      ),
      spacer(),
      text("AV", "Caption", C.ink950),
    ]);
    append(screen, header);
    if (state === "settings") {
      const settings = settingsBody(390);
      settings.paddingLeft = 16;
      settings.paddingRight = 16;
      append(screen, settings);
      return screen;
    }
    if (state === "empty") {
      const body = autoFrame("Mobile empty", {
        width: 390,
        padding: 16,
        gap: 12,
        fill: C.paper50,
      });
      body.layoutGrow = 1;
      append(body, [
        text("What do you want to work on?", "H1", C.ink950, { width: 358 }),
        starterCard("Legal research", "What does the law say about …"),
        starterCard("Review contract", "Review this contract"),
        starterCard("Analyze agreement", "Analyze this agreement"),
      ]);
      append(screen, [body, composer(358, false)]);
      return screen;
    }
    const body = autoFrame("Mobile thread", {
      width: 390,
      padding: 16,
      gap: 16,
      fill: C.paper50,
    });
    body.layoutGrow = 1;
    const mobileUser = userMessage("Explain Article 21 of the Constitution of India.", false);
    mobileUser.resize(330, mobileUser.height);
    const mobileAssistant = assistantMessage("Article 21 protects life and personal liberty. Its procedure must be fair, just, and reasonable.", true);
    mobileAssistant.resize(358, mobileAssistant.height);
    append(body, [mobileUser, mobileAssistant]);
    if (state === "hitl") {
      const hitl = approvalCard("waiting", "Approve", "Reject");
      hitl.resize(358, hitl.height);
      append(body, hitl);
    }
    append(screen, body);
    if (state === "citations") {
      const sheet = citationDrawer(390, "close");
      sheet.name = "Citation bottom sheet / 70%";
      sheet.resize(390, 591);
      append(screen, sheet);
    } else {
      append(screen, composer(358, false));
    }
    return screen;
  }

  function mobileScreens(page) {
    const definitions = [
      ["M02 Login", "login"],
      ["M03 Register", "register"],
      ["M04 Empty", "empty"],
      ["M06 Thread", "thread"],
      ["M09 Citations", "citations"],
      ["M10 HITL", "hitl"],
      ["M14 Settings", "settings"],
    ];
    const map = {};
    definitions.forEach(([name, state], index) => {
      const node = mobileScreen(name, state);
      place(page, node, index, 390, 4, 80);
      map[name] = node;
    });
    return map;
  }

  const CONNECTIONS = [
    ["D01 Landing", "Log in", "D02 Login", "INSTANT"],
    ["D01 Landing", "Get started", "D03 Register", "INSTANT"],
    ["D02 Login", "Sign in", "D04 App / empty", "INSTANT"],
    ["D02 Login", "Create an account", "D03 Register", "INSTANT"],
    ["D02 Login", "error", "D02b Login / error", "INSTANT"],
    ["D02 Login", "401 session", "D02 Login", "INSTANT"],
    ["D03 Register", "Create account", "D02 Login", "INSTANT"],
    ["D04 App / empty", "New chat", "D06 App / thread", "INSTANT"],
    ["D04 App / empty", "Review this contract", "D08 App / with files", "INSTANT"],
    ["D04 App / empty", "starter card", "D07 App / working", "INSTANT"],
    ["D05 App / sidebar populated", "conversation row", "D06 App / thread", "INSTANT"],
    ["D05 App / sidebar populated", "archive icon", "D15 Modal / archive", "DISSOLVE"],
    ["D15 Modal / archive", "Archive", "D05 App / sidebar populated", "INSTANT"],
    ["D06 App / thread", "Send", "D07 App / working", "INSTANT"],
    ["D07 App / working", "response", "D06 App / thread", "INSTANT"],
    ["D07 App / working", "429", "D11 App / quota", "INSTANT"],
    ["D06 App / thread", "citation chip", "D09 App / citations open", "SMART_ANIMATE"],
    ["D09 App / citations open", "close", "D06 App / thread", "SMART_ANIMATE"],
    ["D08 App / with files", "gated tool", "D10 App / HITL waiting", "INSTANT"],
    ["D10 App / HITL waiting", "Approve", "D10b App / HITL approved", "INSTANT"],
    ["D10 App / HITL waiting", "Reject", "D10c App / HITL rejected", "INSTANT"],
    ["D06 App / thread", "UserMenu Settings", "D14 Settings", "INSTANT"],
    ["D14 Settings", "Log out", "D02 Login", "INSTANT"],
    ["D16 Toast examples", "toast", "D06 App / thread", "DISSOLVE"],
  ];

  function transition(type) {
    if (type === "SMART_ANIMATE") {
      return {
        type: "SMART_ANIMATE",
        easing: { type: "EASE_OUT" },
        duration: 0.2,
      };
    }
    if (type === "DISSOLVE") {
      return {
        type: "DISSOLVE",
        easing: { type: "LINEAR" },
        duration: 0.12,
      };
    }
    return null;
  }

  async function addReaction(source, target, type) {
    if (!source || !target) return false;
    const reaction = {
      trigger: { type: "ON_CLICK" },
      actions: [
        {
          type: "NODE",
          destinationId: target.id,
          navigation: "NAVIGATE",
          transition: transition(type),
          preserveScrollPosition: false,
        },
      ],
    };
    try {
      if (source.setReactionsAsync) {
        await source.setReactionsAsync([reaction]);
      } else {
        source.reactions = [reaction];
      }
      return true;
    } catch {
      return false;
    }
  }

  async function prototypePage(page, desktopMap, mobileMap) {
    const root = autoFrame("Prototype connection map", {
      width: 1800,
      padding: 48,
      gap: 24,
      fill: C.paper50,
    });
    append(root, [
      text("Prototype map", "Display", C.ink950),
      text(
        "Hotspots are applied when supported by the installed Figma Plugin API. This annotated map remains canonical when reactions are unavailable.",
        "Body",
        C.ink600,
        { width: 1100 },
      ),
      pill("Smart Animate drawers 200ms · Dissolve toasts 120ms · Auth instant", C.gold100, C.ink950),
    ]);
    let applied = 0;
    for (const [from, hotspot, to, type] of CONNECTIONS) {
      const sourceFrame = desktopMap[from] || mobileMap[from];
      const target = desktopMap[to] || mobileMap[to];
      const source = sourceFrame
        ? sourceFrame.findOne((node) => node.name === "Hotspot / " + hotspot)
        : null;
      if (await addReaction(source, target, type)) applied += 1;
      const row = autoFrame("Connection / " + from + " / " + hotspot, {
        direction: "HORIZONTAL",
        width: 1500,
        padding: 12,
        gap: 12,
        fill: C.paper0,
        stroke: C.line200,
        radius: 6,
        counter: "CENTER",
      });
      append(row, [
        pill(from, C.ink950, C.paper0),
        text("— " + hotspot + " →", "Body", C.ink600),
        pill(to, C.gold100, C.ink950),
        spacer(),
        text(type === "SMART_ANIMATE" ? "Smart Animate · 200ms ease-out" : type === "DISSOLVE" ? "Dissolve · 120ms" : "Instant", "Caption", C.ink400),
      ]);
      append(root, row);
    }
    append(root, alertBox("info", "Prototype reactions", applied + " supported click reactions were applied. All connections are documented above.", 760));
    page.appendChild(root);
  }

  function doNotDesignPage(page) {
    const root = autoFrame("Do not design / v2+", {
      width: 1440,
      padding: 48,
      gap: 24,
      fill: C.paper50,
    });
    append(root, [
      text("Do not design in Web v1", "Display", C.greyDark),
      text("Explicit product boundaries. These are not hidden roadmap commitments.", "Body", C.greyDark),
    ]);
    const grid = autoFrame("Out of scope frames", {
      direction: "HORIZONTAL",
      width: 1344,
      wrap: true,
      gap: 16,
      counterGap: 16,
      fill: null,
    });
    [
      "Organization",
      "Matters",
      "Knowledge admin",
      "Usage live API",
      "Streaming tokens",
      "Approval edit",
    ].forEach((name) => {
      const card = autoFrame("v2+ / " + name, {
        width: 400,
        height: 220,
        padding: 24,
        gap: 16,
        fill: C.grey,
        stroke: C.greyDark,
        radius: 10,
      });
      card.opacity = 0.4;
      append(card, [
        pill("v2+", C.greyDark, C.paper0),
        text(name, "H1", C.ink950),
        text("OUT OF SCOPE — do not imply this exists in Web v1.", "Label", C.ink950, { width: 340 }),
      ]);
      append(grid, card);
    });
    append(root, grid);
    page.appendChild(root);
  }

  try {
    figma.notify("Generating Juris AI — Web v1…", { timeout: 2000 });
    await loadFonts();
    const pages = await resetPages();
    await createVariables();
    await createTextStyles();
    const cover = coverPage(pages["00 Cover"]);
    foundationPage(pages["01 Foundation"]);
    componentsPage(pages["02 Components"]);
    const desktopMap = desktopScreens(pages["03 Screens / Desktop"]);
    const mobileMap = mobileScreens(pages["04 Screens / Mobile"]);
    await prototypePage(pages["05 Prototype"], desktopMap, mobileMap);
    doNotDesignPage(pages["06 Do not design"]);
    await (figma.setCurrentPageAsync
      ? figma.setCurrentPageAsync(pages["00 Cover"])
      : Promise.resolve((figma.currentPage = pages["00 Cover"])));
    figma.viewport.scrollAndZoomIntoView([cover]);
    figma.notify(
      FILE_NAME + " generated: 7 pages, variables, styles, components, screens, and prototype map.",
      { timeout: 5000 },
    );
    figma.closePlugin();
  } catch (error) {
    const message =
      error && error.message ? error.message : String(error || "Unknown error");
    console.error("Juris AI generator failed", error);
    figma.notify("Juris AI generator failed: " + message, {
      error: true,
      timeout: 10000,
    });
    figma.closePlugin("Generation failed: " + message);
  }
})();
