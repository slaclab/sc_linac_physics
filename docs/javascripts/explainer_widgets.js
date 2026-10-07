// Shows explainer widgets inline on the docs site.
//
// In an explainer page, a paragraph that is only a link to
// docs/explainers/widgets/<name>.html becomes that widget, in a frame sized to
// its content, with an "open on its own" link under it. On GitHub and anywhere
// this script does not run, the link stays a plain link to the widget.
//
// Widgets are same-origin pages, so the frame can read their height and set
// data-theme on them to follow the site's light/dark toggle.
(function () {
  const WIDGET = /\/explainers\/widgets\/[^/]+\.html$/;

  function theme() {
    const scheme = document.body.getAttribute("data-md-color-scheme");
    return scheme === "slate" ? "dark" : "light";
  }

  function embed(paragraph, link) {
    const frame = document.createElement("iframe");
    frame.src = link.href;
    frame.title = link.textContent;
    frame.className = "explainer-widget";
    frame.addEventListener("load", () => {
      const doc = frame.contentDocument;
      if (!doc) return;
      doc.documentElement.dataset.theme = theme();
      const fit = () => {
        frame.style.height =
          Math.ceil(doc.body.getBoundingClientRect().height) + "px";
      };
      fit();
      new ResizeObserver(fit).observe(doc.body);
    });

    const open = document.createElement("p");
    open.className = "explainer-widget-open";
    const again = link.cloneNode(false);
    again.textContent = "Open on its own";
    open.append(again);
    paragraph.replaceWith(frame, open);
  }

  for (const paragraph of document.querySelectorAll(".md-content p")) {
    const link = paragraph.querySelector("a");
    if (!link || !WIDGET.test(new URL(link.href).pathname)) continue;
    if (paragraph.textContent.trim() !== link.textContent.trim()) continue;
    embed(paragraph, link);
  }

  new MutationObserver(() => {
    for (const frame of document.querySelectorAll("iframe.explainer-widget")) {
      if (frame.contentDocument) {
        frame.contentDocument.documentElement.dataset.theme = theme();
      }
    }
  }).observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-scheme"],
  });
})();
