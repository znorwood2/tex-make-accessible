# Alt text for math graphics

Alt text tells a student who can't see the figure what they need from it, in the context where it appears.

Ally only checks that alt text exists and isn't a filename. Quality is up to you and the author, so always show the author your draft.

## How to write it

1. **Read the context first:** the caption, the paragraph that refers to the figure, and the problem it belongs to. The same graph needs different alt text in a lesson ("shows that the curve has a minimum near x = 1.2") and in an exam question that asks the student to find the minimum (describe the curve without giving the answer away).
2. **Look at the image** if you can: render EPS/PDF to PNG if needed. Never describe an image you haven't seen; ask instead.
3. **Say what kind of figure it is,** then the essentials:
   - **Graph or plot:** the axes (quantity and range), each curve or series, the overall trend, and key values (intercepts, maxima, where curves cross or diverge). Say how curves compare.
   - **Histogram or bar chart:** what's counted, the shape (decreasing, bell-shaped, skewed), centre and spread, and notable values.
   - **Geometric figure:** the shapes, the labelled points, sides and angles with their labels, and which elements are marked equal or highlighted.
   - **Diagram (graph theory, commutative diagram, flowchart):** the objects and the connections between them. For a small graph, list vertices and edges; for a commutative diagram, list the maps.
   - **Several panels:** say how many, and how they differ.
4. **Complement the caption; don't repeat it.** If the caption says what the figure is, the alt text says what it shows.
5. **Write math in words or plain symbols** (Unicode Greek is fine: "μ = 1.2"; "x squared" or "x^2"). Don't use LaTeX markup.
6. **Keep it short:** usually 1–4 sentences. If a student needs more than that (a complex diagram, a data plot they must read values from), put a fuller description or the data in the text or a table, and keep the alt text short.
7. **Decorative graphics** (logos, ornaments, page decorations) get `artifact` instead of alt text.
8. **Check boxes and other form elements** drawn with TikZ: a short alt text such as "check box".
9. **An image of a table is not a figure.** Replace it with a real table.

## Syntax

```latex
\includegraphics[width=.6\linewidth, alt={A parabola opening upward with y-intercept (0, 3) and vertex (3, -6).}]{parabola}
\includegraphics[artifact]{department-logo}
\begin{tikzpicture}[alt={The Petersen graph: an outer 5-cycle, an inner 5-pointed star, and five edges joining them.}]
```

Braces around the alt text are needed when it contains commas.

## Examples

**Function graph.** Weak: "graph of f". Better: "Graph of f(x) = x³ − 3x on −2 ≤ x ≤ 2. The curve rises to a local maximum of 2 at x = −1, falls to a local minimum of −2 at x = 1, and rises again; it crosses the x-axis at −√3, 0 and √3."

**Comparison plot.** "Line graph of two population models over 0 to 50 years (vertical axis: population in thousands, 0 to 12). The exponential model rises ever faster to about 12; the logistic model rises in an S-shape and levels off near 8. The two agree for the first 10 years."

**Geometry.** "Triangle ABC with a right angle at C. Side a is opposite A, side b is opposite B, and the hypotenuse c is opposite C. The altitude from C to the hypotenuse is drawn and labelled h."

**Exam figure (don't give the answer away).** "A graph of a function on the interval [0, 4], with a jump at x = 2: the left piece ends with an open circle at (2, 1) and the right piece starts with a filled circle at (2, 3)." (It doesn't say "discontinuous at 2" if that is what the question asks.)
