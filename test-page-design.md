Yes, this should be achievable with pure HTML/CSS — no JavaScript required.

The trick is to make the navigation links into large block-level elements that cover most of the screen, positioned where you want the tap targets. Something like:

```
<a href="next" style="position: fixed; top: 0; right: 0; bottom: 0; left: 20%; display: block;"></a>
<a href="prev" style="position: fixed; top: 0; left: 0; bottom: 0; width: 20%; display: block;"></a>
```

The content would need to sit on top of these, so you’d have your actual page content in a container with `position: relative` and a higher `z-index`, but with `pointer-events: none` so taps pass through to the navigation links beneath — except for actual links within the content, which would need `pointer-events: auto` restored.

```
<body>
    <a class="tap-next" href="next"></a>
    <a class="tap-prev" href="prev"></a>
    <article>
        [content with links having pointer-events: auto]
    </article>
</body>
```

## The Uncertainty

I don’t know whether the Kindle browser supports `pointer-events` or whether `position: fixed` behaves correctly. These are CSS features that older/limited browsers sometimes lack or implement incorrectly.

Worth testing:

1. Does `position: fixed` actually fix to viewport, or does it behave like `absolute`?
1. Does the browser honor `pointer-events: none` on the content container?
1. Do taps on the transparent overlay links register as link activations?

If any of these fail, you’d fall back to visible navigation links at the bottom of each page — less elegant but reliable. You could make them larger and more finger-friendly (big padded block elements rather than inline text links) even if you can’t do the full-screen tap zones.

Make a minimal test page with just the overlay structure and one link in the content area before investing in integrating this with the rest of the implementation.​​​​​​​​​​​​​​​​
